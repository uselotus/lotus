from collections import namedtuple

from dateutil.relativedelta import relativedelta
from jinja2 import Template
from metering_billing.utils import now_utc
from metering_billing.utils.enums import METRIC_AGGREGATION

RATE_GET_CURRENT_USAGE = """
SELECT
    "metering_billing_usageevent"."customer_id" AS customer_id,
    {%- if query_type == "count" -%}
    COUNT(
        "metering_billing_usageevent"."idempotency_id"
    )
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
    {%- endfor %}
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."customer_id" = {{ customer_id }}
    AND "metering_billing_usageevent"."event_name" = '{{ event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= NOW()
    AND "metering_billing_usageevent"."time_created" >= '{{ start_time }}'::timestamp + INTERVAL '-1 {{ lookback_units }}' * {{ lookback_qty }}
    AND "metering_billing_usageevent"."time_created" <= '{{ end_time }}'::timestamp
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
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
    {%- endfor %}
"""

# we're going to materialize this so that we always have access to the rate per event
# THIS IS A MATERIALIZED VIEW
EVENTS_AUGMENTED_WITH_RATE = """
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
        RANGE BETWEEN INTERVAL '{{ lookback_qty }}' {{ lookback_units }} PRECEDING AND CURRENT ROW
        ) AS usage_qty
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."customer_id" = {{ customer_id }}
    AND "metering_billing_usageevent"."event_name" = '{{ event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= NOW()
GROUP BY
    "metering_billing_usageevent"."customer_id"
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
"""

# This one can be used both to get the billable usage, and to get teh max usage per
# day. Conveniently since it's a max, we only need a single days entry.
RATE_MAX_IN_DATE_RANGE = """
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
    , time_createdß
    , usage_qty
FROM 
    {{ events_augmented_with_rate_table }}
WHERE
    customer_id = {{ customer_id }}
    AND time_created <= NOW()
    AND time_created >= '{{ start_time }}'::timestamptz
    AND time_created <= '{{ end_time }}'::timestamptz
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
    , time_created ASC
"""


# data = {
#     "customer_id": 1,
#     "event_name": "generate_text",
#     "organization_id": 1,
#     "current_time": now_utc(),
#     "start_time": now_utc() - relativedelta(months=1),
#     "end_time": now_utc(),
#     "group_by": ["language", "test"],
#     "filter_properties": {"language": "en", "test": "test"},
#     "query_type": METRIC_AGGREGATION.MAX,
#     "property_name": "test",
#     "lookback_qty": 15,
#     "lookback_units": "minutes",
# }
