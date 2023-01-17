import json
import logging

from django.conf import settings
from kafka import KafkaProducer

from .singleton import Singleton

KAFKA_EVENTS_TOPIC = settings.KAFKA_EVENTS_TOPIC
producer_config = settings.PRODUCER_CONFIG

logger = logging.getLogger("django.server")


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
