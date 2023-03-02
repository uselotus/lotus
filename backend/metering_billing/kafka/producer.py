import json
import logging
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from kafka import KafkaProducer
from metering_billing.models import Invoice

from .singleton import Singleton

KAFKA_EVENTS_TOPIC = settings.KAFKA_EVENTS_TOPIC
KAFKA_INVOICE_TOPIC = settings.KAFKA_INVOICE_TOPIC
producer_config = settings.PRODUCER_CONFIG

logger = logging.getLogger("django.server")


class InvoiceEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        else:
            return super().default(obj)


class Producer(metaclass=Singleton):
    __connection = None

    def __init__(self):
        self.__connection = KafkaProducer(**producer_config)

    def produce(self, customer_id, stream_events):
        logger.info(f"Producing record. key={customer_id}, value={stream_events}")
        self.__connection.send(
            topic=KAFKA_EVENTS_TOPIC,
            key=customer_id.encode("utf-8"),
            value=json.dumps(stream_events).encode("utf-8"),
        )
        logger.info(f"Produced record to topic {KAFKA_EVENTS_TOPIC}")

    def produce_invoice(self, invoice: Invoice):
        from api.serializers.model_serializers import InvoiceSerializer

        assert isinstance(invoice, Invoice), "invoice must be an instance of Invoice"
        invoice_data = InvoiceSerializer(invoice).data
        message = {
            "messageType": "update",
            "team": invoice.organization.organization_id.hex,
            "payload": invoice_data,
        }
        logger.info(f"Producing invoice. key={invoice.invoice_id.hex}, value={invoice}")
        self.__connection.send(
            topic=KAFKA_INVOICE_TOPIC,
            key=invoice.invoice_id.hex.encode("utf-8"),
            value=json.dumps(message, cls=InvoiceEncoder).encode("utf-8"),
        )
        logger.info(f"Produced invoice to topic {KAFKA_INVOICE_TOPIC}")

    def test(self):
        logger.info("test")
