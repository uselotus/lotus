# Generated by Django 4.0.5 on 2022-08-15 08:11

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('metering_billing', '0006_alter_invoice_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='id',
            field=models.CharField(default=uuid.UUID('0ddbec1c-4121-426b-969d-ee0e83eba22c'), max_length=36, primary_key=True, serialize=False),
        ),
    ]
