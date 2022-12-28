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
        PARTITION BY BY "metering_billing_usageevent"."customer_id"
        {%- for group_by_field in group_by %}
        ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
        {%- endfor %}
        ORDER BY "metering_billing_usageevent"."time_created"
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_usage_qty
    , "metering_billing_usageevent"."time_created" AS time_created
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
"""

# we make this table so that downstream queries don't have to refer to tables with
# different schemas
# THIS IS A MATERIALIZED VIEW
STATEFUL_TOTAL_CUMULATIVE_SUM = """
SELECT 
    "metering_billing_usageevent"."customer_id" AS customer_id
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
    , "metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal AS cumulative_usage_qty
    , "metering_billing_usageevent"."time_created" AS time_created
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
"""

# This table keeps track of the latest value of a stateful metric per day. Even though
# we could do the calculation every time, it's easier in other downstream queries to
# just get a single row instead of doing an expensive calculation every time
# THIS IS A MATERIALIZED VIEW
STATEFUL_GET_LAST_PER_DAY = """
SELECT 
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
    , time_bucket_gapfill(INTERVAL '1 day', time_created) AS day_bucket,
    , last(
        value => cumulative_usage_qty,
        time => time_created
    ) AS day_last_usage_qty
FROM
    {{ table_name }}
WHERE
    time_created <= NOW()
GROUP BY
    customer_id
    {%- for group_by_field in group_by %}
    , group_by_field
    {%- endfor %}
    , day_bucket
"""

# this table lets us easily query the granularity levels we want. It breaks down the usage per
# second, minute, hour, etc., uses lcof and time_bucket_gapfill to give us values for each
# granularity period, and then sums them up to get the total usage for that period and normalizes
# it to the number of periods in a day.
# THIS IS A MATERIALIZED VIEW
STATEFUL_PRORATED_TOTAL_USAGE_PER_DAY = """
SELECT
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
    , time_bucket(INTERVAL 'day', time_created) AS day_bucket
    {%- for granularity in granularities %}
    , SELECT SUM(granularity_period_usage_qty)::decimal / 
        {% if granularity == 'second' %}
        86400
        {% elif granularity == 'minute' %}
        1440
        {% elif granularity == 'hour' %}
        24
        {% elif granularity == 'day' %}
        1
        {% endif %}
        FROM (
            SELECT 
                time_bucket_gapfill(
                    bucket_width => INTERVAL '{{ granularity }}', 
                    time => inner_table.time_created,
                ) AS {{ granularity }}_bucket,
                locf(
                    value => MAX(cumulative_usage_qty), 
                    prev => (
                        SELECT day_last_usage_qty 
                        FROM {{ last_per_day_view_name }} AS inner_prev
                        WHERE inner_prev.customer_id = outer_table.customer_id 
                            {%- for group_by_field in group_by %}
                            AND inner_prev.{{ group_by_field }} = outer_table.{{ group_by_field }}
                            {%- endfor %}
                            AND inner_prev.day_bucket < outer_table.day_bucket
                        ORDER BY day_bucket DESC
                        LIMIT 1
                    ),
                    treat_null_as_missing => true
                ) AS granularity_period_usage_qty
            FROM {{ table_name }} inner_table
            WHERE
                inner_table.customer_id = outer_table.customer_id
                {%- for group_by_field in group_by %}
                AND inner_table.{{ group_by_field }} = outer_table.{{ group_by_field }}
                {%- endfor %}
            GROUP BY {{ granularity }}_bucket
        ) AS {{ granularity }}_normalized_usage_qty
    {%- endfor %}
FROM
    {{ table_name }} outer_table
WHERE
    time_created <= NOW()
GROUP BY
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}

"""

# this is a simple one, just gets the current usage by querying the
# materialized views with the latest that we've set up so far
STATEFUL_GET_CURRENT_USAGE = """
SELECT 
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
    , cumulative_usage_qty AS usage_qty
FROM
    {{ table_name }}
WHERE
    time_created <= NOW()
    {%- for property_name, property_values in filter_properties.items() %}
    AND ("metering_billing_usageevent"."properties" ->> '{{ property_name }}') 
        IN ( 
            {%- for pval in property_values %} 
            '{{ pval }}' 
            {%- if not loop.last %},{% endif %} 
            {%- endfor %} 
        )
    {%- endfor %}
GROUP BY
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
"""

# this one isn't the end all be all because we need to take into consideration the
# edge effects (i.e. if a subscription goes from 2PM Jan 1 to 2PM Jan 31, then we can use the
# materialized view to get the usage for the days in between (Jan 2 - Jan 30), but we need to
# calculate the usage for Jan 1 and Jan 31 separately. This is because the materialized view
# summarizes the usage for the day, so we need to calculate the usage for the partial days
STATEFUL_GET_TOTAL_USAGE_FULL_DAYS = """
SELECT 
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
    , SUM({{ granularity }}_normalized_usage_qty) AS usage_qty
FROM
    {{ table_name }}
WHERE
    day_bucket <= NOW()
    {%- for property_name, property_values in filter_properties.items() %}
    AND ("metering_billing_usageevent"."properties" ->> '{{ property_name }}') 
        IN ( 
            {%- for pval in property_values %} 
            '{{ pval }}' 
            {%- if not loop.last %},{% endif %} 
            {%- endfor %} 
        )
    {%- endfor %}
    AND day_bucket >= date_trunc('day', {{ start_date }} + interval '1 day')
    AND day_bucket < date_trunc('day', {{ end_date }})
GROUP BY
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
"""

# for partial days, the policy is a lot trickier, too tricky to handle at the sql level.
# so what we'll do is get all these statistics per second and let them be handled in the
# python code. Some of the complications include weighting the usage by the number of
# granularity periods in the day chunk
STATEFUL_SECOND_GAPFILLS_PER_DAY = """
SELECT
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
    , time_bucket_gapfill("1 second", time_created) AS second_bucket
    , locf(
        MAX(cumulative_usage_qty),
        prev => (
                    SELECT day_last_usage_qty 
                    FROM {{ last_per_day_view_name }} AS inner_prev
                    WHERE inner_prev.customer_id = outer_table.customer_id 
                        {%- for group_by_field in group_by %}
                        AND inner_prev.{{ group_by_field }} = outer_table.{{ group_by_field }}
                        {%- endfor %}
                        AND inner_prev.day_bucket < date_trunc('day', {{ second_bucket }})
                    ORDER BY day_bucket DESC
                    LIMIT 1
                ),
        treat_null_as_missing => true
    ) AS second_usage_qty
FROM
    {{ table_name }} outer_table
WHERE
    time_created <= NOW()
    AND time_created >= date_trunc('day', {{ start_date }})
    AND time_created < date_trunc('day', {{ end_date }})
    {%- for property_name, property_values in filter_properties.items() %}
    AND ("metering_billing_usageevent"."properties" ->> '{{ property_name }}') 
        IN ( 
            {%- for pval in property_values %} 
            '{{ pval }}' 
            {%- if not loop.last %},{% endif %} 
            {%- endfor %} 
        )
    {%- endfor %}
GROUP BY
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
    , second_bucket
HAVING
    second_bucket >= date_trunc('second', {{ start_date }})
"""


## If there's no proration then we just use this.
STATEFUL_GET_USAGE_NO_PRORATION = """
SELECT 
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
    , MAX(cumulative_usage_qty) AS usage_qty
FROM 
    {{ cumulative_usage_view_name }} AS c
WHERE
    c.customer_id = {{ customer_id }}
    {%- for property_name, property_values in filter_properties.items() %}
    AND ("metering_billing_usageevent"."properties" ->> '{{ property_name }}') 
        IN ( 
            {%- for pval in property_values %} 
            '{{ pval }}' 
            {%- if not loop.last %},{% endif %} 
            {%- endfor %} 
        )
    {%- endfor %}
    AND c.time_created >= {{ start_date }}
    AND c.time_created < {{ end_date }}
    AND c.time_created < NOW()
"""


# data = {
#     "customer_id": 1,
#     "event_name": "generate_text",
#     "organization_id": 1,
#     "current_time": now_utc(),
#     "start_time": now_utc() - relativedelta(months=1),
#     "end_time": now_utc(),
#     "group_by": ["language", "test"],
#     "filter_properties": {"language": ["en"], "test": ["test"]},
#     "query_type": METRIC_AGGREGATION.MAX,
#     "property_name": "test",
#     "lookback_qty": 15,
#     "lookback_units": "minutes",
#     "event_type": EVENT_TYPE.DELTA,
#     "granularity": "day",
# }

# query = Template(STATEFUL_GET_USAGE_WITH_GRANULARITY).render(**data)
