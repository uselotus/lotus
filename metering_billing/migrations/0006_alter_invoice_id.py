# Generated by Django 4.0.5 on 2022-08-15 08:09

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('metering_billing', '0005_alter_invoice_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='id',
            field=models.CharField(default=uuid.UUID('3a75ad14-46ae-4c71-a6aa-39713049dcae'), max_length=36, primary_key=True, serialize=False),
        ),
    ]
