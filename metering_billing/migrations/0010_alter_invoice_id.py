# Generated by Django 4.0.5 on 2022-08-15 08:14

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('metering_billing', '0009_alter_invoice_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='id',
            field=models.CharField(default=uuid.UUID('de0c9e45-e2b5-444e-bd3b-1a2adb2f93b2'), max_length=36, primary_key=True, serialize=False),
        ),
    ]
