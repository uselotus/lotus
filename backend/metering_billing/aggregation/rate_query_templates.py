RATE_GET_CURRENT_USAGE = """
SELECT
    "metering_billing_usageevent"."customer_id" AS customer_id,
    "metering_billing_usageevent"."time_created" AS time_created,
    {% if query_type == "count" -%}
    COUNT(
        "metering_billing_usageevent"."idempotency_id"
    )
    {% elif query_type == "sum" -%}
    SUM(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {% elif query_type == "average" -%}
    AVG(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {% elif query_type == "unique" -%}
    COUNT(
        DISTINCT ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')
    )
    {% elif query_type == "max" -%}
    MAX(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {% endif %} AS usage_qty
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
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
    AND "metering_billing_usageevent"."customer_id" = {{ customer_id }}
    AND "metering_billing_usageevent"."time_created" <= '{{ reference_time }}'::timestamp
    AND "metering_billing_usageevent"."time_created" >= '{{ reference_time }}'::timestamp + INTERVAL '-1 {{ lookback_units }}' * {{ lookback_qty }}
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
    "metering_billing_usageevent"."customer_id"
    {%- for group_by_field in group_by %}
    , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
"""

RATE_CAGG_QUERY = """
CREATE MATERIALIZED VIEW IF NOT EXISTS {{ cagg_name }}
WITH (timescaledb.continuous) AS
SELECT
    "metering_billing_usageevent"."customer_id" AS customer_id,
    time_bucket('1 second', "metering_billing_usageevent"."time_created") AS bucket,
    COUNT(
        "metering_billing_usageevent"."idempotency_id"
    ) AS num_events, 
    {% if query_type == "count" -%}
    COUNT(
        "metering_billing_usageevent"."idempotency_id"
    )
    {% elif query_type == "sum" -%}
    SUM(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {% elif query_type == "average" -%}
    AVG(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {% elif query_type == "unique" -%}
    COUNT(
        DISTINCT ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')
    )
    {% elif query_type == "max" -%}
    MAX(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )
    {% endif %} AS second_usage
    {%- for group_by_field in group_by %}
    , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
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
    "metering_billing_usageevent"."customer_id"
    {%- for group_by_field in group_by %}
    , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
    , bucket
"""

RATE_CAGG_TOTAL = """
WITH rate_per_bucket AS (
    SELECT 
        customer_id
        {%- for group_by_field in group_by %}
        , {{ group_by_field }}
        {%- endfor %}
        , bucket
        {% if query_type == "count" -%}
        , SUM(second_usage)
        {% elif query_type == "sum" -%}
        , SUM(second_usage)
        {% elif query_type == "average" -%}
        , SUM(second_usage*num_events) / NULLIF(SUM(num_events), 0)
        {% elif query_type == "max" -%}
        , MAX(second_usage)
        {% endif %}
        OVER (
            PARTITION BY customer_id
            {%- for group_by_field in group_by %}
            , group_by_field
            {%- endfor %}
            ORDER BY bucket ASC
            RANGE BETWEEN INTERVAL '{{ lookback_qty }} {{ lookback_units }}' PRECEDING AND CURRENT ROW
            ) AS usage_qty
    FROM
        {{ cagg_name }}
    WHERE
        customer_id = {{ customer_id }}
        AND bucket >= '{{ start_date }}'::timestamptz - INTERVAL '{{ lookback_qty }} {{ lookback_units }}'
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
    )
SELECT DISTINCT ON (
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
)
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
    , bucket
    , usage_qty
FROM
    rate_per_bucket
WHERE
    customer_id = {{ customer_id }}
    AND bucket <= NOW()
    AND bucket >= '{{ start_date }}'::timestamptz
    AND bucket <= '{{ end_date }}'::timestamptz
    {%- for property_name, property_values in filter_properties.items() %}
    AND ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')
        IN (
            {%- for pval in property_values %}
            '{{ pval }}'
            {%- if not loop.last %},{% endif %}
            {%- endfor %}
        )
    {%- endfor %}
ORDER BY
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
    , usage_qty DESC
    , bucket ASC
"""
