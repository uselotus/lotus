# Generated by Django 4.0.5 on 2023-02-24 23:57

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("metering_billing", "0214_auto_20230224_2354"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="planversion",
            name="description",
        ),
    ]
