from collections import namedtuple

from dateutil.relativedelta import relativedelta
from jinja2 import Template
from metering_billing.utils import now_utc
from metering_billing.utils.enums import EVENT_TYPE, METRIC_AGGREGATION

### INFRASTRUCTURE TABLES

# This table is for GAUGE metrics with delta events, since the cumulative sum since
# the beginning of time is an expensive query, we precompute the cumulative sums so we
# can access them the same way we would a GAUGE metrics with total event type
# THIS IS A MATERIALIZED VIEW
GAUGE_DELTA_CUMULATIVE_SUM = """
CREATE MATERIALIZED VIEW IF NOT EXISTS {{ cagg_name }} AS
SELECT 
    "metering_billing_usageevent"."customer_id" AS customer_id
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
    , "metering_billing_usageevent"."time_created" AS time_bucket
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
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."event_name" = '{{ event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= NOW()
    {%- for property_name, operator, comparison in numeric_filters %}
    AND ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal 
        {% if operator == "gt" %} 
        > 
        {% elif operator == "gte" %} 
        >= 
        {% elif operator == "lt" %} 
        < 
        {% elif operator == "lte" %} 
        <= 
        {% elif operator == "eq" %}
        =
        {% endif %}
        {{ comparison }}
    {%- endfor %}
    {%- for property_name, operator, comparison in categorical_filters %}
    AND ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')
        {% if operator == "isnotin" %}
        NOT
        {% endif %}
        IN ( 
            {%- for pval in comparison %} 
            '{{ pval }}'
            {%- if not loop.last %},{% endif %} 
            {%- endfor %} 
        )
    {%- endfor %}
"""

GAUGE_DELTA_DROP_TRIGGER = """
DROP TRIGGER IF EXISTS tg_{{ cagg_name }}_insert ON "metering_billing_usageevent";
DROP TRIGGER IF EXISTS tg_{{ cagg_name }}_update ON "metering_billing_usageevent";
DROP TRIGGER IF EXISTS tg_{{ cagg_name }}_delete ON "metering_billing_usageevent";
"""

GAUGE_DELTA_CREATE_TRIGGER_FN = """
CREATE OR REPLACE FUNCTION tg_refresh_{{ cagg_name }}()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        REFRESH MATERIALIZED VIEW {{ cagg_name }};
        RETURN NULL;
    END;
$$;
"""

GAUGE_DELTA_INSERT_TRIGGER = """
CREATE TRIGGER tg_{{ cagg_name }}_insert AFTER INSERT
ON "metering_billing_usageevent"
FOR EACH ROW
WHEN  (
    NEW."organization_id" = {{ organization_id }}
    AND NEW."event_name" = '{{ event_name }}'
    {%- for property_name, operator, comparison in numeric_filters %}
    AND (NEW."properties" ->> '{{ property_name }}')::text::decimal 
        {% if operator == "gt" %} 
        > 
        {% elif operator == "gte" %} 
        >= 
        {% elif operator == "lt" %} 
        < 
        {% elif operator == "lte" %} 
        <= 
        {% elif operator == "eq" %}
        =
        {% endif %}
        {{ comparison }}
    {%- endfor %}
    {%- for property_name, operator, comparison in categorical_filters %}
    AND (NEW."properties" ->> '{{ property_name }}')
        {% if operator == "isnotin" %}
        NOT
        {% endif %}
        IN ( 
            {%- for pval in comparison %} 
            '{{ pval }}'
            {%- if not loop.last %},{% endif %} 
            {%- endfor %} 
        )
    {%- endfor %}
)
EXECUTE PROCEDURE tg_refresh_{{ cagg_name }}();
"""

GAUGE_DELTA_DELETE_TRIGGER = """
CREATE TRIGGER tg_{{ cagg_name }}_delete AFTER DELETE
ON "metering_billing_usageevent"
FOR EACH ROW 
WHEN  (
    OLD."organization_id" = {{ organization_id }}
    AND OLD."event_name" = '{{ event_name }}'
    {%- for property_name, operator, comparison in numeric_filters %}
    AND (OLD."properties" ->> '{{ property_name }}')::text::decimal 
        {% if operator == "gt" %} 
        > 
        {% elif operator == "gte" %} 
        >= 
        {% elif operator == "lt" %} 
        < 
        {% elif operator == "lte" %} 
        <= 
        {% elif operator == "eq" %}
        =
        {% endif %}
        {{ comparison }}
    {%- endfor %}
    {%- for property_name, operator, comparison in categorical_filters %}
    AND (OLD."properties" ->> '{{ property_name }}')
        {% if operator == "isnotin" %}
        NOT
        {% endif %}
        IN ( 
            {%- for pval in comparison %} 
            '{{ pval }}'
            {%- if not loop.last %},{% endif %} 
            {%- endfor %} 
        )
    {%- endfor %}
)
EXECUTE PROCEDURE tg_refresh_{{ cagg_name }}();
"""

GAUGE_DELTA_UPDATE_TRIGGER = """
CREATE TRIGGER tg_{{ cagg_name }}_update AFTER UPDATE
ON "metering_billing_usageevent"
FOR EACH ROW
WHEN  (
    (OLD."organization_id" = {{ organization_id }} OR NEW."organization_id" = {{ organization_id }})
    AND (OLD."event_name" = '{{ event_name }}' OR NEW."event_name" = '{{ event_name }}')
    {%- for property_name, operator, comparison in numeric_filters %}
    AND ( (OLD."properties" ->> '{{ property_name }}')::text::decimal 
        {% if operator == "gt" %} 
        > 
        {% elif operator == "gte" %} 
        >= 
        {% elif operator == "lt" %} 
        < 
        {% elif operator == "lte" %} 
        <= 
        {% elif operator == "eq" %}
        =
        {% endif %}
        {{ comparison }}
        OR (NEW."properties" ->> '{{ property_name }}')::text::decimal
        {% if operator == "gt" %}
        >
        {% elif operator == "gte" %}
        >=
        {% elif operator == "lt" %}
        <
        {% elif operator == "lte" %}
        <=
        {% elif operator == "eq" %}
        =
        {% endif %}
        {{ comparison }}
    )
    {%- endfor %}
    {%- for property_name, operator, comparison in categorical_filters %}
    AND ( (OLD."properties" ->> '{{ property_name }}')
        {% if operator == "isnotin" %}
        NOT
        {% endif %}
        IN ( 
            {%- for pval in comparison %} 
            '{{ pval }}'
            {%- if not loop.last %},{% endif %} 
            {%- endfor %} 
        )
        OR (NEW."properties" ->> '{{ property_name }}')
        {% if operator == "isnotin" %}
        NOT
        {% endif %}
        IN (
            {%- for pval in comparison %}
            '{{ pval }}'
            {%- if not loop.last %},{% endif %}
            {%- endfor %}
        )
    )
    {%- endfor %}
)
EXECUTE PROCEDURE tg_refresh_{{ cagg_name }}();
"""


# we make this table so that downstream queries don't have to refer to tables with
# different schemas
# THIS IS A MATERIALIZED VIEW
GAUGE_TOTAL_CUMULATIVE_SUM = """
CREATE MATERIALIZED VIEW IF NOT EXISTS {{ cagg_name }}
WITH (timescaledb.continuous) AS
SELECT 
    "metering_billing_usageevent"."customer_id" AS customer_id
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
    , MAX(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    ) AS cumulative_usage_qty
    , time_bucket('1 microsecond', "metering_billing_usageevent"."time_created") AS time_bucket
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."event_name" = '{{ event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= NOW()
    {%- for property_name, operator, comparison in numeric_filters %}
    AND ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal 
        {% if operator == "gt" %} 
        > 
        {% elif operator == "gte" %} 
        >= 
        {% elif operator == "lt" %} 
        < 
        {% elif operator == "lte" %} 
        <= 
        {% elif operator == "eq" %}
        =
        {% endif %}
        {{ comparison }}
    {%- endfor %}
    {%- for property_name, operator, comparison in categorical_filters %}
    AND ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')
        {% if operator == "isnotin" %}
        NOT
        {% endif %}
        IN ( 
            {%- for pval in comparison %} 
            '{{ pval }}'
            {%- if not loop.last %},{% endif %} 
            {%- endfor %} 
        )
    {%- endfor %}
GROUP BY
    customer_id
    {%- for group_by_field in group_by %}
    , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
    {%- endfor %}
    , time_bucket
"""

# get current usage is easy, just pull the latest value from the cumulative sum table
GAUGE_GET_CURRENT_USAGE = """
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
GROUP BY
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
"""

GAUGE_GET_TOTAL_USAGE_WITH_PRORATION = """
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
        , '{{ start_date }}'::timestamptz AS time
        {%- else %}
        , time_bucket_gapfill('1 {{ proration_units }}', time_bucket) AS time
        , locf( 
            value => MAX(cumulative_usage_qty), 
            prev => (
                SELECT COALESCE(
                    (select prev_usage_qty from prev_state limit 1), 
                    0
                ) AS prev_usage_qty
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
        , time
),
normalized_query AS (
SELECT
    {%- if proration_units is not none %}
    CASE 
    WHEN time < '{{ start_date }}'::timestamptz
        THEN 
            (
                EXTRACT( EPOCH FROM (time + '1 {{ proration_units }}'::interval)) - 
                EXTRACT( EPOCH FROM '{{ start_date }}'::timestamptz)
            )
            / 
            (
                EXTRACT( EPOCH FROM (time + '1 {{ proration_units }}'::interval)) - 
                EXTRACT( EPOCH FROM time)
            )
    WHEN time > '{{ end_date }}'::timestamptz
        THEN 
            (
                EXTRACT( EPOCH FROM '{{ end_date }}'::timestamptz) - 
                EXTRACT( EPOCH FROM time)
            )
            / 
            (
                EXTRACT( EPOCH FROM (time + '1 {{ proration_units }}'::interval)) - 
                EXTRACT( EPOCH FROM time)
            )
    ELSE 1
    END 
    {%- else %}
    1
    {%- endif %} AS time_ratio,
    time,
    usage_qty
FROM 
    proration_level_query
)
SELECT
    COALESCE(
        (
            select 
                SUM(usage_qty * time_ratio) / {{ granularity_ratio }}
            from normalized_query
        ), 
        (
            select prev_usage_qty 
            from prev_value 
            limit 1
        )
    ) AS usage_qty
"""

GAUGE_GET_TOTAL_USAGE_WITH_PRORATION_PER_DAY = """
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
        , '{{ start_date }}'::timestamptz AS time
        {%- else %}
        , time_bucket_gapfill('1 {{ proration_units }}', time_bucket) AS time
        , locf( 
            value => MAX(cumulative_usage_qty), 
            prev => (
                SELECT COALESCE(
                    (select prev_usage_qty from prev_state limit 1), 
                    0
                ) AS prev_usage_qty
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
        , time
),
normalized_query AS (
SELECT
    {%- if proration_units is not none %}
    CASE 
    WHEN time < '{{ start_date }}'::timestamptz
        THEN 
            (
                EXTRACT( EPOCH FROM (time + '1 {{ proration_units }}'::interval)) - 
                EXTRACT( EPOCH FROM '{{ start_date }}'::timestamptz)
            )
            / 
            (
                EXTRACT( EPOCH FROM (time + '1 {{ proration_units }}'::interval)) - 
                EXTRACT( EPOCH FROM time)
            )
    WHEN time > '{{ end_date }}'::timestamptz
        THEN 
            (
                EXTRACT( EPOCH FROM '{{ end_date }}'::timestamptz) - 
                EXTRACT( EPOCH FROM time)
            )
            / 
            (
                EXTRACT( EPOCH FROM (time + '1 {{ proration_units }}'::interval)) - 
                EXTRACT( EPOCH FROM time)
            )
    ELSE 1
    END 
    {%- else %}
    1
    {%- endif %} AS time_ratio,
    time,
    usage_qty
FROM 
    proration_level_query
)
SELECT
    usage_qty * time_ratio / {{ granularity_ratio }} AS usage_qty
    , time
FROM
    normalized_query
"""
