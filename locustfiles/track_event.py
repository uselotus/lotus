import uuid
from telnetlib import STATUS

from locust import HttpUser, between, task
from lotus.settings import ADMIN_API_KEY


class UnauthenticatedUser(HttpUser):
    weight = 1
    wait_time = between(0.05, 2)

    def on_start(self):
        self.client.headers = {"X-API-KEY": "invalid_token"}

    @task
    def track_event(self):
        self.client.post(
            "/track",
            json={
                "event_name": "test",
                "customer": "baz",
                "time_created": "2020-01-01T00:00:00Z",
                "properties": {"foo": "bar"},
                "idempotency_id": uuid.uuid4(),
            },
        )


class AuthenticatedUserLowRequests(HttpUser):
    weight = 8
    wait_time = between(1, 2)

    def on_start(self):
        self.client.headers = {"X-API-KEY": ADMIN_API_KEY}

    @task
    def track_event(self):
        self.client.post(
            "/track",
            json={
                "event_name": "test",
                "customer_id": "baz",
                "time_created": "2020-01-01T00:00:00Z",
                "properties": {"foo": "bar"},
                "idempotency_id": str(uuid.uuid4()),
            },
        )


class AuthenticatedUserMidRequests(HttpUser):
    weight = 10
    wait_time = between(0.05, 0.5)

    def on_start(self):
        self.client.headers = {"X-API-KEY": ADMIN_API_KEY}

    @task
    def track_event(self):
        self.client.post(
            "/track",
            json={
                "event_name": "test",
                "customer_id": "baz",
                "time_created": "2020-01-01T00:00:00Z",
                "properties": {"foo": "bar"},
                "idempotency_id": str(uuid.uuid4()),
            },
        )


class AuthenticatedUserHighRequests(HttpUser):
    def on_start(self):
        self.client.headers = {"X-API-KEY": ADMIN_API_KEY}

    @task
    def track_event(self):
        self.client.post(
            "/track",
            json={
                "event_name": "test",
                "customer_id": "baz",
                "time_created": "2020-01-01T00:00:00Z",
                "properties": {"foo": "bar"},
                "idempotency_id": str(uuid.uuid4()),
            },
        )
