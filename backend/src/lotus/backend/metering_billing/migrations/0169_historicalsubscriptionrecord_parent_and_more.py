# Generated by Django 4.0.5 on 2023-01-25 21:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('metering_billing', '0168_alter_invoicelineitem_billing_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalsubscriptionrecord',
            name='parent',
            field=models.ForeignKey(blank=True, db_constraint=False, help_text='The parent subscription record.', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='metering_billing.subscriptionrecord'),
        ),
        migrations.AddField(
            model_name='invoicelineitem',
            name='associated_plan_version',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='line_items', to='metering_billing.planversion'),
        ),
        migrations.AddField(
            model_name='subscriptionrecord',
            name='parent',
            field=models.ForeignKey(blank=True, help_text='The parent subscription record.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='addon_subscription_records', to='metering_billing.subscriptionrecord'),
        ),
        migrations.AlterField(
            model_name='historicalplan',
            name='plan_duration',
            field=models.CharField(choices=[('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('yearly', 'Yearly')], help_text='Duration of the plan', max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name='historicalplanversion',
            name='flat_fee_billing_type',
            field=models.CharField(blank=True, choices=[('in_arrears', 'In Arrears'), ('in_advance', 'In Advance')], max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name='plan',
            name='plan_duration',
            field=models.CharField(choices=[('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('yearly', 'Yearly')], help_text='Duration of the plan', max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name='planversion',
            name='flat_fee_billing_type',
            field=models.CharField(blank=True, choices=[('in_arrears', 'In Arrears'), ('in_advance', 'In Advance')], max_length=40, null=True),
        ),
        migrations.CreateModel(
            name='AddOnSpecification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('billing_frequency', models.PositiveSmallIntegerField(choices=[(1, 'one_time'), (2, 'recurring')], default=1)),
                ('flat_fee_invoicing_behavior_on_attach', models.PositiveSmallIntegerField(choices=[(1, 'invoice_on_attach'), (2, 'invoice_on_subscription_end')], default=1)),
                ('recurring_flat_fee_timing', models.PositiveSmallIntegerField(blank=True, choices=[(1, 'in_advance'), (2, 'in_arrears')], null=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='metering_billing.organization')),
            ],
        ),
        migrations.AddField(
            model_name='historicalplan',
            name='addon_spec',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='metering_billing.addonspecification'),
        ),
        migrations.AddField(
            model_name='plan',
            name='addon_spec',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='metering_billing.addonspecification'),
        ),
        migrations.AddConstraint(
            model_name='addonspecification',
            constraint=models.CheckConstraint(check=models.Q(models.Q(('billing_frequency', 1), ('recurring_flat_fee_timing__isnull', True)), models.Q(('billing_frequency', 2), ('recurring_flat_fee_timing__isnull', False)), _connector='OR'), name='billing_frequency_one_time_recurring_flat_fee_timing_isnull'),
        ),
    ]