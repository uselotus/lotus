# Generated by Django 4.0.5 on 2023-01-06 20:03

import django.db.models.expressions
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "metering_billing",
            "0138_customer_tax_rate_historicalcustomer_tax_rate_and_more",
        ),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="organizationsetting",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="historicalsubscriptionrecord",
            name="status",
        ),
        migrations.RemoveField(
            model_name="subscriptionrecord",
            name="status",
        ),
        migrations.AlterField(
            model_name="historicalinvoice",
            name="invoice_pdf",
            field=models.URLField(blank=True, max_length=300, null=True),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="invoice_pdf",
            field=models.URLField(blank=True, max_length=300, null=True),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("start_date__lte", django.db.models.expressions.F("end_date"))
                ),
                name="start_date_less_than_end_date",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                fields=("subscription_id", "organization"),
                name="unique_subscription_id",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                fields=("customer", "start_date", "end_date"),
                name="unique_customer_start_end_date",
            ),
        ),
    ]