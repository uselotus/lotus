from collections import namedtuple

from dateutil.relativedelta import relativedelta
from jinja2 import Template
from metering_billing.utils import now_utc
from metering_billing.utils.enums import EVENT_TYPE, METRIC_AGGREGATION

STATEFUL_GET_CURRENT_USAGE_DELTA = """
SELECT 
    "metering_billing_usageevent"."customer_id" AS customer_id
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
    , SUM(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    ) AS usage_qty
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."customer_id" = {{ customer_id }}
    AND "metering_billing_usageevent"."event_name" = '{{ event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= '{{ current_time }}'::timestamp
    AND "metering_billing_usageevent"."time_created" <= '{{ end_time }}'::timestamp
    {%- for property_name, property_values in filter_properties.items() %}
    AND ("metering_billing_usageevent"."properties" ->> '{{ property_name }}') IN ( {%- for pval in property_values %} '{{ pval }}' {%- if not loop.last %}, {% endif %} {%- endfor %} )
    {%- endfor %}
GROUP BY
    "metering_billing_usageevent"."customer_id"
    {%- for group_by_field in group_by %}
    , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
    {%- endfor %}
"""

STATEFUL_GET_CURRENT_USAGE_TOTAL = """
WITH recent_rows AS (
    SELECT 
        "metering_billing_usageevent"."customer_id" AS customer_id
        {%- for group_by_field in group_by %}
        ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
        {%- endfor %}
        , ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal AS usage_qty
        , ROW_NUMBER() OVER (
            PARTITION BY "metering_billing_usageevent"."customer_id"
            {%- for group_by_field in group_by %}
            ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
            {%- endfor %}
            ORDER BY "metering_billing_usageevent"."time_created" DESC
        ) AS row_num
    FROM
        "metering_billing_usageevent"
    WHERE
        "metering_billing_usageevent"."customer_id" = {{ customer_id }}
        AND "metering_billing_usageevent"."event_name" = '{{ event_name }}'
        AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
        AND "metering_billing_usageevent"."time_created" <= '{{ current_time }}'::timestamp
        AND "metering_billing_usageevent"."time_created" <= '{{ end_time }}'::timestamp
        {%- for property_name, property_values in filter_properties.items() %}
        AND ("metering_billing_usageevent"."properties" ->> '{{ property_name }}') IN ( {%- for pval in property_values %} '{{ pval }}' {%- if not loop.last %}, {% endif %} {%- endfor %} )
        {%- endfor %}
)
SELECT
    "recent_rows"."customer_id" AS customer_id
    {%- for group_by_field in group_by %}
    , "recent_rows"."{{ group_by_field }}" AS {{ group_by_field }}
    {%- endfor %}
    , "recent_rows"."usage_qty" AS usage_qty
FROM
    "recent_rows"
WHERE
    "recent_rows"."row_num" = 1
"""

STATEFUL_GET_USAGE_WITH_GRANULARITY = """
SELECT 
    "metering_billing_usageevent"."customer_id" AS customer_id
    {%- for group_by_field in group_by %}
    ,"metering_billing_usageevent"."properties" ->> '{{ group_by_field }}' AS {{ group_by_field }}
    {%- endfor %}
    , time_bucket_gapfill('1 {{ granularity }}', "metering_billing_usageevent"."time_created") AS time_created_truncated
    , locf(MAX(
        ("metering_billing_usageevent"."properties" ->> '{{ property_name }}')::text::decimal
    )) AS usage_qty
FROM
    "metering_billing_usageevent"
WHERE
    "metering_billing_usageevent"."customer_id" = {{ customer_id }}
    AND "metering_billing_usageevent"."event_name" = '{{ event_name }}'
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }}
    AND "metering_billing_usageevent"."time_created" <= '{{ current_time }}'::timestamp
    AND "metering_billing_usageevent"."time_created" <= '{{ end_time }}'::timestamp
    AND "metering_billing_usageevent"."time_created" >= '{{ start_time }}'::timestamp
    {%- for property_name, property_values in filter_properties.items() %}
    AND ("metering_billing_usageevent"."properties" ->> '{{ property_name }}') IN ( {%- for pval in property_values %} '{{ pval }}' {%- if not loop.last %}, {% endif %} {%- endfor %} )
    {%- endfor %}
GROUP BY
    "metering_billing_usageevent"."customer_id"
    {%- for group_by_field in group_by %}
    , "metering_billing_usageevent"."properties" ->> '{{ group_by_field }}'
    {%- endfor %}
    , time_created_truncated
"""


data = {
    "customer_id": 1,
    "event_name": "generate_text",
    "organization_id": 1,
    "current_time": now_utc(),
    "start_time": now_utc() - relativedelta(months=1),
    "end_time": now_utc(),
    "group_by": ["language", "test"],
    "filter_properties": {"language": ["en"], "test": ["test"]},
    "query_type": METRIC_AGGREGATION.MAX,
    "property_name": "test",
    "lookback_qty": 15,
    "lookback_units": "minutes",
    "event_type": EVENT_TYPE.DELTA,
    "granularity": "day",
}

query = Template(STATEFUL_GET_USAGE_WITH_GRANULARITY).render(**data)
print(query)
