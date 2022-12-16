RATE_COUNT_GET_CURRENT_USAGE = """
SELECT 
    "metering_billing_usageevent"."customer_id" AS "customer_id", 
    COUNT(
        "metering_billing_usageevent"."idempotency_id"
    ) AS "usage_qty" 
    { % if group_by % } { % for group_by_field in group_by % }, 
    (
        "metering_billing_usageevent"."properties" ->> {{ group_by_field }}
    ) { % endfor % } { % endif % } 
FROM 
    "metering_billing_usageevent" 
WHERE 
    "metering_billing_usageevent"."customer_id" = {{ customer_id }} 
    AND "metering_billing_usageevent"."event_type" = {{ event_type }} 
    AND "metering_billing_usageevent"."organization_id" = {{ organization_id }} 
    AND "metering_billing_usageevent"."time_created" <= {{ current_time }} 
    AND "metering_billing_usageevent"."time_created" >= {{ start_time }} 
    AND "metering_billing_usageevent"."time_created" <= {{ end_time }} { % if filter_properties % } { % for property_name, 
    property_value in filter_properties.items() % } 
    AND (
        "metering_billing_usageevent"."properties" -> {{ property_name | sqlsafe }}
    ) = {{ property_value }}{ % endfor % } { % endif % } 
GROUP BY 
    "metering_billing_usageevent"."customer_id" AS "customer_id" { % if group_by % } { % for group_by_field in group_by % }, 
    , (
        "metering_billing_usageevent"."properties" ->> {{ group_by_field }}
    ) { % endfor % } { % endif % }
"""
