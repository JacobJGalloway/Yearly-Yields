import logging

logger = logging.getLogger(__name__)

# v1.2: replace stubs with real SendGrid calls using SENDGRID_API_KEY,
# SENDGRID_FROM_EMAIL, and SENDGRID_FROM_NAME from settings.


async def send_password_reset_email(to_email: str, reset_url: str) -> None:
    logger.info("PASSWORD RESET EMAIL (stub) → %s | url: %s", to_email, reset_url)
