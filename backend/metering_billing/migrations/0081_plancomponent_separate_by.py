# Generated by Django 4.0.5 on 2022-11-23 23:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering_billing", "0080_historicalmetric_is_cost_metric_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="plancomponent",
            name="separate_by",
            field=models.JSONField(blank=True, default=list, null=True),
        ),
    ]
