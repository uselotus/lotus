# Generated by Django 4.0.5 on 2022-09-27 07:14

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('metering_billing', '0018_alter_subscription_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='subscription_uid',
            field=models.CharField(blank=True, max_length=100, null=True),
        )
    ]
