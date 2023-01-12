CUSTOM_BASE_QUERY = """
WITH events AS
(
    SELECT
        "metering_billing_usageevent"."properties" as properties,
        "metering_billing_usageevent"."time_created"::timestamptz as time_created,
        "metering_billing_usageevent"."event_name" as event_name,
        '{{ start_date }}'::timestamptz as start_date,
        '{{ end_date }}'::timestamptz as end_date
    FROM "metering_billing_usageevent"
    WHERE 
        "metering_billing_usageevent"."organization_id" = {{ organization_id }}
        AND "metering_billing_usageevent"."customer_id" = {{ customer_id }}
        {%- for property_name, property_values in filter_properties.items() %}
            AND {{ property_name }}
                IN ( 
                    {%- for pval in property_values %} 
                    '{{ pval }}' 
                    {%- if not loop.last %},{% endif %} 
                    {%- endfor %} 
                )
        {%- endfor %}
        AND "metering_billing_usageevent"."time_created" <= NOW()
)
"""
