from collections import namedtuple

from dateutil.relativedelta import relativedelta
from jinja2 import Template
from metering_billing.utils import now_utc
from metering_billing.utils.enums import EVENT_TYPE, METRIC_AGGREGATION

### INFRASTRUCTURE TABLES

# This table is for stateful metrics with delta events, since the cumulative sum since
# the beginning of time is an expensive query, we precompute the cumulative sums so we
# can access them the same way we would a stateful metrics with total event type
# THIS IS A MATERIALIZED VIEW
STATEFUL_DELTA_CUMULATIVE_SUM = """
CREATE MATERIALIZED VIEW {{ cagg_name }}
WITH (timescaledb.continuous) AS
SELECT 
    "metering_billing_usageevent"."customer_id" AS customer_id
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
    , SUM(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    ) OVER (
        PARTITION BY "metering_billing_usageevent"."customer_id"
        {%- for group_by_field in group_by %}
        ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
        {%- endfor %}
        ORDER BY "metering_billing_usageevent"."time_created"
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_usage_qty
    , time_bucket('1 second', "metering_billing_usageevent"."time_created") AS time_bucket
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."event_name" = '{{ event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= NOW()
GROUP BY
    "metering_billing_usageevent"."customer_id"
    {%- for group_by_field in group_by %}
    , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
    {%- endfor %}
    , time_bucket
"""

# we make this table so that downstream queries don't have to refer to tables with
# different schemas
# THIS IS A MATERIALIZED VIEW
STATEFUL_TOTAL_CUMULATIVE_SUM = """
CREATE MATERIALIZED VIEW {{ cagg_name }}
WITH (timescaledb.continuous) AS
SELECT 
    "metering_billing_usageevent"."customer_id" AS customer_id
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
    , MAX(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    ) AS cumulative_usage_qty
    , time_bucket('1 second', "metering_billing_usageevent"."time_created") AS time_bucket
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."event_name" = '{{ event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= NOW()
GROUP BY
    "metering_billing_usageevent"."customer_id"
    {%- for group_by_field in group_by %}
    , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
    {%- endfor %}
    , time_bucket
"""

# get current usage is easy, just pull the latest value from the cumulative sum table
STATEFUL_GET_CURRENT_USAGE = """
SELECT
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
    , last(cumulative_usage_qty, time_bucket) AS usage_qty
FROM
    {{ cumsum_cagg }}
WHERE
    customer_id = {{ customer_id }}
    {%- for property_name, property_values in filter_properties.items() %}
    AND {{ property_name }}
        IN ( 
            {%- for pval in property_values %} 
            '{{ pval }}' 
            {%- if not loop.last %},{% endif %} 
            {%- endfor %} 
        )
    {%- endfor %}
    AND time_bucket <= NOW()
"""

STATEFUL_GET_TOTAL_USAGE_WITH_PRORATION = """
WITH prev_state AS (
    SELECT
        customer_id
        {%- for group_by_field in group_by %}
        , {{ group_by_field }}
        {%- endfor %}
        , last(cumulative_usage_qty, time_bucket) AS prev_usage_qty
    FROM
        {{ cumsum_cagg }}
    WHERE
        customer_id = {{ customer_id }}
        {%- for property_name, property_values in filter_properties.items() %}
        AND {{ property_name }}
            IN (
                {%- for pval in property_values %}
                '{{ pval }}'
                {%- if not loop.last %},{% endif %}
                {%- endfor %}
            )
        {%- endfor %}
        AND time_bucket < '{{ start_date }}'::timestamptz
    GROUP BY
        customer_id
        {%- for group_by_field in group_by %}
        , {{ group_by_field }}
        {%- endfor %}
), 
prev_value AS (
    SELECT 
        COALESCE(
            (select prev_usage_qty from prev_state limit 1), 
            0
        ) AS prev_usage_qty
    FROM
        prev_state
    LIMIT 1
),
proration_level_query AS (
    SELECT
        customer_id
        {%- for group_by_field in group_by %}
        , {{ group_by_field }}
        {%- endfor %}
        {%- if proration_units is none %}
        , MAX(cumulative_usage_qty) AS usage_qty
        {%- else %}
        , time_bucket_gapfill('1 {{ proration_units }}', time_bucket) AS time_bucket
        , locf( 
            value => MAX(cumulative_usage_qty), 
            prev => SELECT prev_usage_qty FROM prev_value LIMIT 1
            )
        ) AS usage_qty
        {%- endif %}
    FROM
        {{ cumsum_cagg }}
    WHERE
        customer_id = {{ customer_id }}
        {%- for property_name, property_values in filter_properties.items() %}
        AND {{ property_name }}
            IN (
                {%- for pval in property_values %}
                '{{ pval }}'
                {%- if not loop.last %},{% endif %}
                {%- endfor %}
            )
        {%- endfor %}
        AND time_bucket <= NOW()
        AND time_bucket >= '{{ start_date }}'::timestamptz
        AND time_bucket <= '{{ end_date }}'::timestamptz
    GROUP BY
        customer_id
        {%- for group_by_field in group_by %}
        , {{ group_by_field }}
        {%- endfor %}
        , time_bucket
)
SELECT
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
    , COALESCE(
        (select SUM(usage_qty) / {{ granularity_ratio }} from proration_level_query), 
        (select prev_usage_qty from prev_value limit 1)
    ) AS usage_qty
FROM
    proration_level_query
GROUP BY
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
"""
