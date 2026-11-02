import json
import logging
from typing import Optional, Dict, Any
from aiokafka import AIOKafkaProducer
from fashion_pipeline.config.settings import settings

logger = logging.getLogger(__name__)


class KafkaProducerService:
    def __init__(self, bootstrap_servers: Optional[str] = None):
        self.bootstrap_servers = bootstrap_servers or settings.KAFKA_BOOTSTRAP_SERVERS
        self.producer: Optional[AIOKafkaProducer] = None

    async def start(self) -> None:
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self.producer.start()
            logger.info("AIOKafkaProducer started successfully.")
        except Exception as e:
            logger.warning(f"Could not connect to Kafka at {self.bootstrap_servers}: {e}. Mock/offline mode enabled.")
            self.producer = None

    async def stop(self) -> None:
        if self.producer:
            await self.producer.stop()

    async def publish_event(self, topic: str, event_data: Dict[str, Any]) -> None:
        if self.producer:
            await self.producer.send_and_wait(topic, event_data)
            logger.info(f"Published event to topic '{topic}': {event_data}")
        else:
            logger.info(f"[Offline Mode] Event to '{topic}': {event_data}")


kafka_service = KafkaProducerService()
