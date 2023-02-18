# this will be our basic materialized view where we keep track of stuff per day
# THIS IS A MATERIALIZED VIEW
COUNTER_CAGG_QUERY = """
CREATE MATERIALIZED VIEW IF NOT EXISTS {{ cagg_name }}
WITH ( timescaledb.continuous ) AS
SELECT
    "metering_billing_usageevent"."uuidv5_customer_id" AS uuidv5_customer_id
    , time_bucket('1 {{bucket_size}}', "metering_billing_usageevent"."time_created") AS bucket
    , COUNT("metering_billing_usageevent"."idempotency_id") AS num_events
    , {%- if query_type == "count" -%}
    COUNT("metering_billing_usageevent"."idempotency_id")
    {%- elif query_type == "sum" -%}
    SUM(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {%- elif query_type == "average" -%}
    AVG(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {%- elif query_type == "unique" -%}
    COUNT( DISTINCT "metering_billing_usageevent"."properties" ->> '{{ property_name }}' )
    {%- elif query_type == "max" -%}
    MAX(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {%- endif %} AS usage_qty
    {%- for group_by_field in group_by %}
    , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."uuidv5_event_name" = '{{ uuidv5_event_name }}'
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
    AND (COALESCE("metering_billing_usageevent"."properties" ->> '{{ property_name }}', ''))
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
    uuidv5_customer_id
    , bucket
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
"""

# this query is used to get all the usage aggregated over the entire time period using the
COUNTER_CAGG_TOTAL = """
SELECT
    uuidv5_customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
    , SUM(num_events) AS num_events
    , {%- if query_type == "count" -%}
    SUM(num_events)
    {%- elif query_type == "sum" -%}
    SUM(usage_qty)
    {%- elif query_type == "average" -%}
    SUM(usage_qty * num_events) / SUM(num_events)
    {%- elif query_type == "max" -%}
    MAX(usage_qty)
    {%- endif %} AS usage_qty
    , bucket
FROM
    {{ cagg_name }}
WHERE
    uuidv5_customer_id = '{{ uuidv5_customer_id }}'
    AND bucket >= '{{ start_date }}'::timestamptz
    AND bucket <= '{{ end_date }}'::timestamptz
    AND bucket <= NOW()
    {%- for property_name, property_values in filter_properties.items() %}
    AND {{ property_name }}
        IN (
            {%- for pval in property_values %}
            '{{ pval }}'
            {%- if not loop.last %},{% endif %}
            {%- endfor %}
        )
    {%- endfor %}
GROUP BY
    uuidv5_customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
    , bucket
"""


COUNTER_UNIQUE_TOTAL = """
SELECT
    "metering_billing_usageevent"."uuidv5_customer_id" AS uuidv5_customer_id
    {%- for group_by_field in group_by %}
    , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
    , COUNT( DISTINCT "metering_billing_usageevent"."properties" ->> '{{ property_name }}' ) AS usage_qty
    , COUNT( * ) AS num_events
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."uuidv5_event_name" = '{{ uuidv5_event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= NOW()
    AND "metering_billing_usageevent"."time_created" >= '{{ start_date }}'::timestamptz
    AND "metering_billing_usageevent"."time_created" <= '{{ end_date }}'::timestamptz
    {%- if uuidv5_customer_id is not none %}
    AND "metering_billing_usageevent"."uuidv5_customer_id" = '{{ uuidv5_customer_id }}'
    {% endif %}
    {%- for property_name, property_values in filter_properties.items() %}
    AND {{ property_name }}
        IN (
            {%- for pval in property_values %}
            '{{ pval }}'
            {%- if not loop.last %},{% endif %}
            {%- endfor %}
        )
    {%- endfor %}
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
    AND (COALESCE("metering_billing_usageevent"."properties" ->> '{{ property_name }}', ''))
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
    "metering_billing_usageevent"."uuidv5_customer_id"
    {%- for group_by_field in group_by %}
    , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}',
    {%- endfor %}
"""


COUNTER_UNIQUE_PER_DAY = """
SELECT DISTINCT ON (
    "metering_billing_usageevent"."uuidv5_customer_id",
    {%- for group_by_field in group_by %}
    "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}',
    {%- endfor %}
    "metering_billing_usageevent"."properties" ->> '{{ property_name }}'
)
    "metering_billing_usageevent"."uuidv5_customer_id" AS uuidv5_customer_id,
    {%- for group_by_field in group_by %}
    "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }},
    {%- endfor %}
    "metering_billing_usageevent"."time_created" AS time_created,
    "metering_billing_usageevent"."properties" ->> '{{ property_name }}' AS unique_value
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."uuidv5_event_name" = '{{ uuidv5_event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= NOW()
    AND "metering_billing_usageevent"."time_created" >= '{{ start_date }}'::timestamptz
    AND "metering_billing_usageevent"."time_created" <= '{{ end_date }}'::timestamptz
    {%- if uuidv5_customer_id is not none %}
    AND "metering_billing_usageevent"."uuidv5_customer_id" = '{{ uuidv5_customer_id }}'
    {% endif %}
ORDER BY
    "metering_billing_usageevent"."uuidv5_customer_id"
    {%- for group_by_field in group_by %}
    , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
    {%- endfor %}
    , "metering_billing_usageevent"."properties" ->> '{{ property_name }}'
    , "metering_billing_usageevent"."time_created" ASC
"""


COUNTER_TOTAL_PER_DAY = """
WITH per_customer AS (
    SELECT
        uuidv5_customer_id
        , time_bucket_gapfill('1 day', bucket) AS time_bucket
        , SUM(usage_qty) AS usage_qty_per_day
    FROM
        {{ cagg_name }}
    WHERE
        bucket <= NOW()
        {% if uuidv5_customer_id is not none %}
        AND uuidv5_customer_id = '{{ uuidv5_customer_id }}'
        {% endif %}
        AND bucket >= '{{ start_date }}'::timestamptz
        AND bucket <=  '{{ end_date }}'::timestamptz
    GROUP BY
        uuidv5_customer_id
        , time_bucket
    ORDER BY
        usage_qty_per_day DESC
), top_n AS (
    SELECT 
        uuidv5_customer_id
        , SUM(usage_qty_per_day) AS total_usage_qty
    FROM
        per_customer
    GROUP BY
        uuidv5_customer_id
    ORDER BY
        total_usage_qty DESC
    LIMIT {{ top_n }}
)
SELECT 
    COALESCE(top_n.uuidv5_customer_id, uuid_nil()) AS uuidv5_customer_id
    , SUM(per_customer.usage_qty_per_day) AS usage_qty
    , per_customer.time_bucket AS time_bucket
FROM 
    per_customer
LEFT JOIN
    top_n
ON
    per_customer.uuidv5_customer_id = top_n.uuidv5_customer_id
GROUP BY
    COALESCE(top_n.uuidv5_customer_id, uuid_nil())
    , per_customer.time_bucket
"""
