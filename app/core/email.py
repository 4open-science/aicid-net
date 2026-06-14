import logging

from python_posthorn import PosthornClient

from app.config import settings

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body: str) -> None:
    if not settings.POSTHORN_BASE_URL or not settings.POSTHORN_API_KEY:
        logger.info("Email delivery not configured. To=%s Subject=%s Body=%s", to_email, subject, body)
        return

    client = PosthornClient(
        settings.POSTHORN_BASE_URL,
        settings.POSTHORN_API_KEY,
        default_path=settings.POSTHORN_PATH,
    )
    client.send_to_override(
        {"subject_line": subject, "message": body},
        to_email,
    )
