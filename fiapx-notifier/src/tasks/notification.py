import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from uuid import UUID

import structlog

from src.core.config import settings
from src.models import Job, SessionLocal, User

logger = structlog.get_logger()


def send_notification(job_id: str, user_id: str, notification_type: str) -> dict:
    """Send email notification to user."""
    logger.info("notification_started", job_id=job_id, type=notification_type)

    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == UUID(job_id)).first()
        user = db.query(User).filter(User.id == UUID(user_id)).first()

        if not job or not user:
            logger.error("not_found", job_id=job_id, user_id=user_id)
            return {"status": "error", "reason": "not_found"}

        if notification_type == "completed":
            subject = f"FIAP X: Your video '{job.original_filename}' is ready!"
            body = _completed_body(user.name, job)
        else:
            subject = f"FIAP X: Error processing '{job.original_filename}'"
            body = _failed_body(user.name, job)

        _send_email(user.email, subject, body)

        logger.info("notification_sent", job_id=job_id, email=user.email)
        return {"status": "success"}

    except Exception as e:
        logger.error("notification_failed", job_id=job_id, error=str(e))
        return {"status": "error", "error": str(e)}

    finally:
        db.close()


def _send_email(to_email: str, subject: str, body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = to_email

    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(body.replace("\n", "<br>"), "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_user and settings.smtp_password:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.email_from, to_email, msg.as_string())


def _completed_body(name: str, job: Job) -> str:
    return f"""Hello {name},

Great news! Your video has been processed successfully.

Video: {job.original_filename}
Frames extracted: {job.frame_count}
Processing time: {job.processing_time_seconds} seconds

You can download your frames ZIP file by logging into FIAP X.

The download link will be available for {settings.video_retention_days} days.

Best regards,
FIAP X Team
"""


def _failed_body(name: str, job: Job) -> str:
    return f"""Hello {name},

Unfortunately, we encountered an error processing your video.

Video: {job.original_filename}
Error: {job.error_message or 'Unknown error'}

Please try again or contact support if the problem persists.

Best regards,
FIAP X Team
"""
