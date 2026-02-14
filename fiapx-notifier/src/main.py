"""
FIAP X Notification Service - Sends email notifications.
"""

import json
import signal
import time

import pika
import structlog

from src.core.config import settings
from src.tasks.notification import send_notification

logger = structlog.get_logger()

shutdown_requested = False


def signal_handler(signum, frame):
    global shutdown_requested
    logger.info("shutdown_requested", signal=signum)
    shutdown_requested = True


def on_message(channel, method, properties, body):
    """Handle incoming notification request."""
    try:
        message = json.loads(body)
        job_id = message["job_id"]
        user_id = message["user_id"]
        notification_type = message["type"]

        logger.info("notification_received", job_id=job_id, type=notification_type)

        send_notification(job_id, user_id, notification_type)

        channel.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        logger.error("invalid_message", error=str(e))
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        logger.error("notification_error", error=str(e))
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def main():
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("notifier_starting")

    while not shutdown_requested:
        try:
            params = pika.URLParameters(settings.rabbitmq_url)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()

            channel.queue_declare(queue="notification.send", durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue="notification.send", on_message_callback=on_message)

            logger.info("notifier_ready", queue="notification.send")

            while not shutdown_requested:
                connection.process_data_events(time_limit=1)

            connection.close()

        except pika.exceptions.AMQPConnectionError as e:
            logger.error("rabbitmq_error", error=str(e))
            if not shutdown_requested:
                time.sleep(5)

        except Exception as e:
            logger.error("notifier_error", error=str(e))
            if not shutdown_requested:
                time.sleep(5)

    logger.info("notifier_stopped")


if __name__ == "__main__":
    main()
