import json
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.test import TestCase
from django.urls import reverse
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_api_key.models import APIKey
from stripe import Plan

from ..models import (
    APIToken,
    BillableMetric,
    BillingPlan,
    Customer,
    Event,
    Organization,
    PlanComponent,
    Subscription,
    User,
)


class UserModelTest(TestCase):
    """
    Class to test the model User
    """

    def setUp(self):
        pass
    
    def test_user_creation(self):
        """Checks to make sure we can succesfully create a user. 
        """
        user = baker.make(User)
        self.assertIsNotNone(user)

class OrganizationModelTest(TestCase):
    """
    Class to test the model Organization
    """

    def setUp(self):
        pass
    
    def test_organization_creation_no_connecion(self):
        """Checks to make sure we can succesfully create an organization. 
        """
        organization = baker.make(Organization)
        self.assertIsNotNone(organization)
    
    def test_organization_creation_connect_to_users(self):
        users_set = baker.prepare(User, _quantity=5)
        organization = baker.make(Organization, users=users_set)
        self.assertEquals(organization.users.count(), 5)

class CustomerModelTest(TestCase):
    """
        Class to test the model Customer
    """

    def setUp(self):
        pass

    def test_customer_creation(self):
        """Checks to make sure we can succesfully create an organization. 
        """
        customer = baker.make(Customer)
        self.assertIsNotNone(customer)


