# this will be our basic materialized view where we keep track of stuff per day
# THIS IS A MATERIALIZED VIEW
COUNTER_DAILY_AGGREGATE = """
SELECT
    "metering_billing_usageevent"."customer_id" AS customer_id,
    time_bucket_gapfill(
        bucket_width =>'1 day', 
        time => "metering_billing_usageevent"."time_created",
        start => '2020-01-01'::timestamp,
    ) AS day_bucket,
    COUNT(
        "metering_billing_usageevent"."idempotency_id"
    ) AS num_events,
    {%- if query_type == "count" -%}
    num_events
    {%- elif query_type == "sum" -%}
    SUM(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {%- elif query_type == "average" -%}
    AVG(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {%- elif query_type == "max" -%}
    MAX(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {%- endif %}
    AS usage_qty
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %},
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."event_name" = '{{ event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= NOW()
GROUP BY
    "metering_billing_usageevent"."customer_id",
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
    {%- endfor %}
"""

# this query will help us fill in the gaps where we don't want to use a full day's worth of usage
# for example, if a subscription starts halfway through a day, we don't want to use the full day's
# worth of usage, we need to get more granular
COUNTER_NON_AGGREGATE = """
SELECT
    "metering_billing_usageevent"."customer_id" AS customer_id,
    COUNT(
        "metering_billing_usageevent"."idempotency_id"
    ) AS num_events,
    {%- if query_type == "count" -%}
    num_events
    {%- elif query_type == "sum" -%}
    SUM(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {%- elif query_type == "average" -%}
    AVG(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {%- elif query_type == "max" -%}
    MAX(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {%- endif %}
    AS usage_qty
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %},
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."event_name" = '{{ event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= NOW()
    AND "metering_billing_usageevent"."time_created" >= '{{ start_date }}'::timestamptz
    AND "metering_billing_usageevent"."time_created" <= '{{ end_date }}'::timestamptz
GROUP BY
    "metering_billing_usageevent"."customer_id",
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
    {%- endfor %}
"""

# this query is used to get all the usage aggregated over the entire time period using the
# materialized view
COUNTER_USE_DAILY_AGGREGATE = """
SELECT
    customer_id,
    {%- for group_by_field in group_by %}
    {{ group_by_field }},
    SUM(num_events) AS num_events,
    {%- endfor %}
    {%- if query_type == "count" -%}
    SUM(num_events)
    {%- elif query_type == "sum" -%}
    SUM(usage_qty)
    {%- elif query_type == "average" -%}
    SUM(usage_qty) / SUM(num_events)
    {%- elif query_type == "max" -%}
    MAX(usage_qty)
    {%- endif %}
    AS usage_qty
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
FROM
    {{ materialized_view_name }}
WHERE
    customer_id = {{ customer_id }}
    AND day_bucket >= '{{ start_date }}'::timestamptz
    AND day_bucket <= '{{ end_date }}'::timestamptz
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
    customer_id,
    {%- for group_by_field in group_by %}
    {{ group_by_field }},
    {%- endfor %}
    {%- for group_by_field in group_by %}
"""


COUNTER_UNIQUE_TOTAL_PERIOD = """
SELECT
    "metering_billing_usageevent"."customer_id" AS customer_id,
    {%- for group_by_field in group_by %}
    "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }},
    {%- endfor %}
    COUNT( DISTINCT "metering_billing_usageevent"."properties" ->> '{{ property_name }}' ) AS usage_qty
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."event_name" = '{{ event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= NOW()
    AND "metering_billing_usageevent"."time_created" >= '{{ start_date }}'::timestamptz
    AND "metering_billing_usageevent"."time_created" <= '{{ end_date }}'::timestamptz
    AND "metering_billing_usageevent"."customer_id" = {{ customer_id }}
GROUP BY
    "metering_billing_usageevent"."customer_id",
    {%- for group_by_field in group_by %}
    "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}',
    {%- endfor %}
"""


COUNTER_UNIQUE_PER_DAY = """
SELECT DISTINCT ON (
    "metering_billing_usageevent"."customer_id",
    {%- for group_by_field in group_by %}
    "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}',
    {%- endfor %}
    "metering_billing_usageevent"."properties" ->> '{{ property_name }}'
)
    "metering_billing_usageevent"."customer_id" AS customer_id,
    {%- for group_by_field in group_by %}
    "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }},
    {%- endfor %}
    "metering_billing_usageevent"."time_created" AS time_created,
    "metering_billing_usageevent"."properties" ->> '{{ property_name }}' AS unique_value
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."event_name" = '{{ event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= NOW()
    AND "metering_billing_usageevent"."time_created" >= '{{ start_date }}'::timestamptz
    AND "metering_billing_usageevent"."time_created" <= '{{ end_date }}'::timestamptz
    AND "metering_billing_usageevent"."customer_id" = {{ customer_id }}
ORDER BY
    "metering_billing_usageevent"."customer_id",
    {%- for group_by_field in group_by %}
    "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}',
    {%- endfor %}
    "metering_billing_usageevent"."properties" ->> '{{ property_name }}',
    "metering_billing_usageevent"."time_created" ASC
"""
