from django.db import models
from djmoney.models.fields import MoneyField
from django.contrib.postgres.fields import ArrayField

# Create your models here.

# Customer Model, Attempt 1
class Customer(models.Model):
    """
    Customer object. An explanation of the Customer's fields follows: 
    first_name: self-explanatory
    last_name: self-explanatory
    billing_address: currently set to null, but we will need to set this to an "address" object later
    email_address: self-explanatory
    phone_number: self-explanatory
    balance: An amount of money that the customer owes the company.
             If the number is positive, the customer owes money to the company,
             if negative, then the company owes money to the customer.
    time_created: The time at which the customer object was created
    default_payment_source: The customer's payment method. Currently set to a string,
                            but will probably need to be a full-on 'payment' object in the future.
    discount: The discount that applies to this customer, if any. Will need a "discount" object in the future.
    invoice_prefix: A prefix string to put on the customer's invoice, so that we may generate unique invoice numbers
    invoice_settings: The customer's default invoice settings
    livemode: True if Customer object exists in live mode, False if Customer object exists in test mode
    next_invoice_sequence: Suffix of the customer's next invoice number (i.e. counting number for invoices)
    preferred_locales: Customer's preferred languages, ordered by preference 
    subscriptions: Customer's current subscriptions. Need to make into a list or array of subscription objects
    tax: Tax details for the customer. Will need to expand on later.
    tax_exempt: String that takes 1 of 3 values: 
                1. none
                2. exempt
                3. reverse
    
    tax_ids: Customer's tax IDs.
    test_clock: ID of test_clock this customer belongs to

    """

    first_name = models.CharField(max_length=30) # 30 characters is arbitrary
    last_name = models.CharField(max_length=30)
    billing_address = null
    email_address = models.CharField(max_length=30) # 30 chars is arbitrary
    phone_number = models.CharField(max_length=30) 
    shipping_address = null
    balance = MoneyField(
        decimal_places=2,
        default=0,
        default_currency='USD',
        max_digits=11,
    )

    time_created = models.TimeField()
    default_payment_source = models.CharField(max_length = 60) # 60 characters is arbitrary,  
    delinquent = models.BooleanField()
    discount = null
    invoice_prefix = models.CharField(max_length=30) # 30 chars is arbitrary
    invoice_settings = null 
    livemode = models.BooleanField()
    next_invoice_sequence = models.CharField(max_length=30) # 30 chars arbitrary
    preferred_locales = ArrayField(models.CharField(max_length=30), blank=True, size = 3) # I think 3 is the number of languages, not sure 
    subscriptions = ArrayField(null, size = 10)
    tax = null
    tax_exempt = models.CharField(max_length=30)
    tax_ids = ArrayField(models.CharField(max_length=30))
    test_clock = models.CharField(max_length=30)