"""
FIAP X Video Worker - Consumes jobs from RabbitMQ and processes videos.
"""

import json
import signal
import sys
import time
from functools import partial

import pika
import structlog

from src.core.config import settings
from src.tasks.video import process_video

logger = structlog.get_logger()

shutdown_requested = False


def signal_handler(signum, frame):
    global shutdown_requested
    logger.info("shutdown_requested", signal=signum)
    shutdown_requested = True


def on_message(channel, method, properties, body):
    """Handle incoming video processing job."""
    try:
        message = json.loads(body)
        job_id = message["job_id"]
        video_path = message["video_path"]

        logger.info("job_received", job_id=job_id)

        # Get retry count from headers
        retry_count = 0
        if properties.headers and "x-retry-count" in properties.headers:
            retry_count = properties.headers["x-retry-count"]

        result = process_video(job_id, video_path, retry_count)

        if result.get("status") == "failed" and result.get("retry"):
            # Retry with backoff
            retry_count += 1
            delay = settings.retry_delay * (2 ** (retry_count - 1))  # exponential backoff

            logger.info("job_retry_scheduled", job_id=job_id, retry=retry_count, delay=delay)

            time.sleep(min(delay, 300))  # max 5 min delay

            # Republish with retry count
            channel.basic_publish(
                exchange="",
                routing_key="video.process",
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    headers={"x-retry-count": retry_count},
                ),
            )

        channel.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        logger.error("invalid_message", error=str(e))
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        logger.error("processing_error", error=str(e))
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def main():
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("worker_starting", concurrency=settings.worker_concurrency)

    while not shutdown_requested:
        try:
            params = pika.URLParameters(settings.rabbitmq_url)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()

            # Declare queue
            channel.queue_declare(queue="video.process", durable=True)

            # Prefetch 1 message at a time
            channel.basic_qos(prefetch_count=1)

            # Start consuming
            channel.basic_consume(queue="video.process", on_message_callback=on_message)

            logger.info("worker_ready", queue="video.process")

            while not shutdown_requested:
                connection.process_data_events(time_limit=1)

            connection.close()

        except pika.exceptions.AMQPConnectionError as e:
            logger.error("rabbitmq_connection_error", error=str(e))
            if not shutdown_requested:
                time.sleep(5)

        except Exception as e:
            logger.error("worker_error", error=str(e))
            if not shutdown_requested:
                time.sleep(5)

    logger.info("worker_stopped")


if __name__ == "__main__":
    main()
