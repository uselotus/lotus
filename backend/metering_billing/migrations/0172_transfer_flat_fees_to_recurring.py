# Generated by Django 4.0.5 on 2023-02-01 00:02

from django.db import migrations


def transfer_flat_fees_to_recurring(apps, schema_editor):
    PlanVersion = apps.get_model("metering_billing", "PlanVersion")
    RecurringCharge = apps.get_model("metering_billing", "RecurringCharge")
    for plan_version in PlanVersion.objects.all():
        if plan_version.flat_rate is not None and plan_version.flat_rate > 0:
            if plan_version.flat_fee_billing_type == "in_advance":
                charge_timing = 1  # IN_ADVANCE = (1, "in_advance")
            elif plan_version.flat_fee_billing_type == "in_arrears":
                charge_timing = 2  # IN_ARREARS = (2, "in_arrears")
            RecurringCharge.objects.create(
                organization=plan_version.organization,
                name="Flat Fee",
                plan_version=plan_version,
                charge_timing=charge_timing,
                charge_behavior=1,  # PRORATE = (1, "prorate")
                amount=plan_version.flat_rate,
                pricing_unit=plan_version.pricing_unit,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("metering_billing", "0171_recurringcharge_and_more"),
    ]

    operations = [
        migrations.RunPython(
            transfer_flat_fees_to_recurring, reverse_code=migrations.RunPython.noop
        ),
    ]
