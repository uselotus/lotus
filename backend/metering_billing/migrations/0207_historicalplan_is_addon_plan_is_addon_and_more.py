# Generated by Django 4.0.5 on 2023-02-24 22:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('metering_billing', '0206_remove_historicalplan_parent_plan_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalplan',
            name='is_addon',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='plan',
            name='is_addon',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='planversion',
            name='addon_spec',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='plan_version', to='metering_billing.addonspecification'),
        ),
    ]
