import json
from typing import Any

import pika
import structlog

from .config import settings

logger = structlog.get_logger()


class MessagePublisher:
    """RabbitMQ message publisher."""

    def __init__(self) -> None:
        self._connection: pika.BlockingConnection | None = None
        self._channel: pika.channel.Channel | None = None

    def _connect(self) -> None:
        if self._connection is None or self._connection.is_closed:
            params = pika.URLParameters(settings.rabbitmq_url)
            self._connection = pika.BlockingConnection(params)
            self._channel = self._connection.channel()

            # Declare exchanges and queues
            self._channel.exchange_declare(
                exchange="video", exchange_type="direct", durable=True
            )
            self._channel.exchange_declare(
                exchange="notification", exchange_type="fanout", durable=True
            )

            self._channel.queue_declare(queue="video.process", durable=True)
            self._channel.queue_declare(queue="notification.send", durable=True)

            self._channel.queue_bind(
                queue="video.process", exchange="video", routing_key="process"
            )
            self._channel.queue_bind(
                queue="notification.send", exchange="notification"
            )

    def publish_video_job(self, job_id: str, user_id: str, video_path: str) -> None:
        """Publish a video processing job to the queue."""
        self._connect()

        message = {
            "job_id": job_id,
            "user_id": user_id,
            "video_path": video_path,
        }

        self._channel.basic_publish(
            exchange="video",
            routing_key="process",
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # persistent
                content_type="application/json",
            ),
        )

        logger.info("job_published", job_id=job_id, queue="video.process")

    def close(self) -> None:
        if self._connection and not self._connection.is_closed:
            self._connection.close()


_publisher: MessagePublisher | None = None


def get_publisher() -> MessagePublisher:
    global _publisher
    if _publisher is None:
        _publisher = MessagePublisher()
    return _publisher
