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
WITH ( timescaledb.continuous ) AS
SELECT
    customer_id
    , time_bucket('1 second', time_created) AS bucket
    , MAX(usage_qty) AS usage_qty
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
FROM
    (
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
            {% endif %}
            OVER (
                PARTITION BY "metering_billing_usageevent"."customer_id"
                {%- for group_by_field in group_by %}
                ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
                {%- endfor %}
                ORDER BY "metering_billing_usageevent"."time_created" ASC
                RANGE BETWEEN INTERVAL '{{ lookback_qty }} {{ lookback_units }}' PRECEDING AND CURRENT ROW
                ) AS usage_qty
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
        GROUP BY
            "metering_billing_usageevent"."customer_id"
            {%- for group_by_field in group_by %}
            , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
            {%- endfor %}
    ) AS events_augmented_with_rate
GROUP BY
    customer_id
    , bucket
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
"""

# We use this query to get the total billable usage for a given customer. Since the only billable
# aggregation type is max, then this query also serves to get the billabel usage per day.
RATE_CAGG_TOTAL = """
WITH events_augmented_with_rate AS (
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
    {% endif %}
    OVER (
        PARTITION BY "metering_billing_usageevent"."customer_id"
        {%- for group_by_field in group_by %}
        ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
        {%- endfor %}
        ORDER BY "metering_billing_usageevent"."time_created" ASC
        RANGE BETWEEN INTERVAL '{{ lookback_qty }} {{ lookback_units }}' PRECEDING AND CURRENT ROW
        ) AS usage_qty
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."event_name" = '{{ event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= NOW()
    AND time_created >= '{{ start_date }}'::timestamptz - INTERVAL '{{ lookback_qty }} {{ lookback_units }}'
    AND time_created <= '{{ end_date }}'::timestamptz
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
    , time_created AS bucket
    , usage_qty
FROM
    events_augmented_with_rate
WHERE
    customer_id = {{ customer_id }}
    AND time_created <= NOW()
    AND time_created >= '{{ start_date }}'::timestamptz
    AND time_created <= '{{ end_date }}'::timestamptz
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
