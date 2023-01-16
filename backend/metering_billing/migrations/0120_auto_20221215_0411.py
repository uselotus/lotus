# Generated by Django 4.0.5 on 2022-12-15 04:11

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("metering_billing", "0119_alter_customer_customer_id_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                (
                    "CREATE TABLE public.metering_billing_usageevent ( \
                    event_name varchar(100) NOT NULL, \
                    time_created timestamp with time zone NOT NULL, \
                    properties jsonb, \
                    idempotency_id varchar(255) NOT NULL, \
                    customer_id bigint, \
                    organization_id bigint, \
                    cust_id varchar(50), \
                    inserted_at timestamp with time zone NOT NULL, \
                    CONSTRAINT metering_billing_usageevent_pkey \
                        PRIMARY KEY (idempotency_id, time_created) \
                ); \
                SELECT create_hypertable('metering_billing_usageevent', 'time_created');"
                )
            ],
            reverse_sql=[("DROP TABLE public.metering_billing_usageevent;")],
        )
    ]
