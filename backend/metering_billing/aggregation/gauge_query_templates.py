### INFRASTRUCTURE TABLES

### FIRST ALL DELTA QUERIES
GAUGE_DELTA_CUMULATIVE_SUM = """
CREATE MATERIALIZED VIEW IF NOT EXISTS {{ cagg_name }}
WITH (timescaledb.continuous) AS
SELECT
    "metering_billing_usageevent"."customer_id" AS customer_id
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
    , time_bucket('1 day', "metering_billing_usageevent"."time_created") AS time_bucket
    , SUM(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    ) AS day_net_state_change
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
    , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
    {%- endfor %}
    , time_bucket('1 day', "metering_billing_usageevent"."time_created")
"""

# cumsum_daily_cagg: sum of daily sum of deltas. From cagg so its quick
# current day sum: more delta sums from same day, but not from cagg and before now
# prev_value: the "starting point" for the query
# cumulative_sum_per_event: get cumsum for each event in the time range
GAUGE_DELTA_GET_TOTAL_USAGE_WITH_PRORATION = """
WITH cumsum_cagg_daily AS (
    SELECT
        customer_id
        {%- for group_by_field in group_by %}
        , {{ group_by_field }}
        {%- endfor %}
        , SUM(day_net_state_change) AS prev_days_usage_qty
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
        AND time_bucket < date_trunc('day', '{{ start_date }}'::timestamptz)
        AND time_bucket <= CURRENT_DATE
    GROUP BY
        customer_id
        {%- for group_by_field in group_by %}
        , {{ group_by_field }}
        {%- endfor %}
), current_day_sum AS (
    SELECT
        "metering_billing_usageevent"."customer_id" AS customer_id
        {%- for group_by_field in group_by %}
        , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
        {%- endfor %}
        , SUM(
            ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
        ) AS today_change
    FROM
        "metering_billing_usageevent"
    WHERE
        "metering_billing_usageevent"."event_name" = '{{ event_name }}'
        AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
        AND "metering_billing_usageevent"."time_created" <= NOW()
        AND "metering_billing_usageevent"."time_created" < '{{ start_date }}'::timestamptz
        AND date_trunc('day', "metering_billing_usageevent"."time_created") = date_trunc('day', '{{ start_date }}'::timestamptz)
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
        customer_id
        {%- for group_by_field in group_by %}
        , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
        {%- endfor %}
), prev_value AS (
    SELECT
        customer_id
        {%- for group_by_field in group_by %}
        , {{ group_by_field }}
        {%- endfor %}
        , COALESCE(prev_days_usage_qty, 0) + COALESCE(today_change, 0) AS prev_usage_qty
    FROM
        cumsum_cagg_daily
    LEFT JOIN
        current_day_sum
    USING (customer_id {%- for group_by_field in group_by %}, {{ group_by_field }}{% endfor %})
),
cumulative_sum_per_event AS (
    SELECT
        event_table.customer_id AS customer_id
        {%- for group_by_field in group_by %}
        , event_table.properties ->> '{{ group_by_field }}' AS {{ group_by_field }}
        {%- endfor %}
        , COALESCE(prev_value.prev_usage_qty,0) + SUM(cast(event_table.properties ->> '{{ property_name }}' AS decimal))
            OVER (
                PARTITION BY event_table.customer_id
                {%- for group_by_field in group_by %}
                , event_table.properties ->> '{{ group_by_field }}'
                {%- endfor %}
                ORDER BY event_table.time_created
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cumulative_usage_qty
        , event_table.time_created AS time_bucket
    FROM
        "metering_billing_usageevent" AS event_table
    LEFT JOIN prev_value
        ON event_table.customer_id = prev_value.customer_id
    WHERE
       event_table.event_name = '{{ event_name }}'
        AND event_table.organization_id = {{ organization_id }}
        AND event_table.time_created <= NOW()
        AND event_table.time_created >= '{{ start_date }}'::timestamptz
        AND event_table.time_created <= '{{ end_date }}'::timestamptz
        {%- for property_name, operator, comparison in numeric_filters %}
        AND (event_table.properties ->> '{{ property_name }}')::text::decimal
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
        AND (event_table.properties ->> '{{ property_name }}')
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
                    (select prev_usage_qty from prev_value limit 1),
                    0
                ) AS prev_usage_qty
            )
        ) AS usage_qty
        {%- endif %}
    FROM
        cumulative_sum_per_event
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


GAUGE_DELTA_GET_TOTAL_USAGE_WITH_PRORATION_PER_DAY = """
WITH cumsum_cagg_daily AS (
    SELECT
        customer_id
        {%- for group_by_field in group_by %}
        , {{ group_by_field }}
        {%- endfor %}
        , SUM(day_net_state_change) AS prev_days_usage_qty
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
        AND time_bucket < date_trunc('day', '{{ start_date }}'::timestamptz)
        AND time_bucket <= CURRENT_DATE
    GROUP BY
        customer_id
        {%- for group_by_field in group_by %}
        , {{ group_by_field }}
        {%- endfor %}
), current_day_sum AS (
    SELECT
        "metering_billing_usageevent"."customer_id" AS customer_id
        {%- for group_by_field in group_by %}
        , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
        {%- endfor %}
        , SUM(
            ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
        ) AS today_change
    FROM
        "metering_billing_usageevent"
    WHERE
        "metering_billing_usageevent"."event_name" = '{{ event_name }}'
        AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
        AND "metering_billing_usageevent"."time_created" <= NOW()
        AND "metering_billing_usageevent"."time_created" < '{{ start_date }}'::timestamptz
        AND date_trunc('day', "metering_billing_usageevent"."time_created") = date_trunc('day', '{{ start_date }}'::timestamptz)
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
        customer_id
        {%- for group_by_field in group_by %}
        , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
        {%- endfor %}
), prev_value AS (
    SELECT
        customer_id
        {%- for group_by_field in group_by %}
        , {{ group_by_field }}
        {%- endfor %}
        , COALESCE(prev_days_usage_qty, 0) + COALESCE(today_change, 0) AS prev_usage_qty
    FROM
        cumsum_cagg_daily
    LEFT JOIN
        current_day_sum
    USING (customer_id {%- for group_by_field in group_by %}, {{ group_by_field }}{% endfor %})
),
cumulative_sum_per_event AS (
    SELECT
        event_table.customer_id AS customer_id
        {%- for group_by_field in group_by %}
        , event_table.properties ->> '{{ group_by_field }}' AS {{ group_by_field }}
        {%- endfor %}
        , COALESCE(prev_value.prev_usage_qty,0) + SUM(cast(event_table.properties ->> '{{ property_name }}' AS decimal))
            OVER (
                PARTITION BY event_table.customer_id
                {%- for group_by_field in group_by %}
                , event_table.properties ->> '{{ group_by_field }}'
                {%- endfor %}
                ORDER BY event_table.time_created
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cumulative_usage_qty
        , event_table.time_created AS time_bucket
    FROM
        "metering_billing_usageevent" AS event_table
    LEFT JOIN prev_value
        ON event_table.customer_id = prev_value.customer_id
    WHERE
       event_table.event_name = '{{ event_name }}'
        AND event_table.organization_id = {{ organization_id }}
        AND event_table.time_created <= NOW()
        AND event_table.time_created >= '{{ start_date }}'::timestamptz
        AND event_table.time_created <= '{{ end_date }}'::timestamptz
        {%- for property_name, operator, comparison in numeric_filters %}
        AND (event_table.properties ->> '{{ property_name }}')::text::decimal
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
        AND (event_table.properties ->> '{{ property_name }}')
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
                    (select prev_usage_qty from prev_value limit 1),
                    0
                ) AS prev_usage_qty
            )
        ) AS usage_qty
        {%- endif %}
    FROM
        cumulative_sum_per_event
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


GAUGE_DELTA_DROP_OLD = """
DROP MATERIALIZED VIEW IF EXISTS {{ cagg_name }};
DROP TRIGGER IF EXISTS tg_{{ cagg_name }}_insert ON "metering_billing_usageevent";
DROP TRIGGER IF EXISTS tg_{{ cagg_name }}_update ON "metering_billing_usageevent";
DROP TRIGGER IF EXISTS tg_{{ cagg_name }}_delete ON "metering_billing_usageevent";
DROP FUNCTION IF EXISTS tg_refresh_{{ cagg_name }};
"""

GAUGE_DELTA_GET_CURRENT_USAGE = """
WITH cumsum_cagg_daily AS (
    SELECT
        customer_id
        {%- for group_by_field in group_by %}
        , {{ group_by_field }}
        {%- endfor %}
        , SUM(day_net_state_change) AS prev_days_usage_qty
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
        AND time_bucket < CURRENT_DATE
    GROUP BY
        customer_id
        {%- for group_by_field in group_by %}
        , {{ group_by_field }}
        {%- endfor %}
), current_day_sum AS (
    SELECT
        "metering_billing_usageevent"."customer_id" AS customer_id
        {%- for group_by_field in group_by %}
        ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
        {%- endfor %}
        , "metering_billing_usageevent"."time_created" AS time_bucket
        , SUM(
            ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
        ) AS today_change
    FROM
        "metering_billing_usageevent"
    WHERE
        "metering_billing_usageevent"."event_name" = '{{ event_name }}'
        AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
        AND "metering_billing_usageevent"."time_created" <= NOW()
        AND date_trunc("day", "metering_billing_usageevent"."time_created") = CURRENT_DATE
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
    GROUP BY
        customer_id
        {%- for group_by_field in group_by %}
        , {{ group_by_field }}
        {%- endfor %}
        , "metering_billing_usageevent"."time_created"
)
SELECT
    customer_id
    {%- for group_by_field in group_by %}
    , {{ group_by_field }}
    {%- endfor %}
    , COALESCE(prev_days_usage_qty, 0) + COALESCE(today_change, 0) AS current_usage_qty
FROM
    cumsum_cagg_daily
FULL OUTER JOIN
    current_day_sum
USING (customer_id {%- for group_by_field in group_by %}, {{ group_by_field }}{% endfor %});
"""


### THEN ALL TOTAL QUERIES
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
    customer_id
    {%- for group_by_field in group_by %}
    , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
    {%- endfor %}
    , time_bucket
"""

GAUGE_TOTAL_GET_CURRENT_USAGE = """
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

GAUGE_TOTAL_GET_TOTAL_USAGE_WITH_PRORATION = """
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
                    (select prev_usage_qty from prev_value limit 1),
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

GAUGE_TOTAL_GET_TOTAL_USAGE_WITH_PRORATION_PER_DAY = """
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
                    (select prev_usage_qty from prev_value limit 1),
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
