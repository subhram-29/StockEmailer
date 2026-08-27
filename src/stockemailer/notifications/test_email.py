import os
import html

from dotenv import load_dotenv

from stockemailer.notifications.gmail import send_email


load_dotenv()


recipient = os.getenv("EMAIL_RECIPIENT")

if not recipient:
    raise ValueError(
        "EMAIL_RECIPIENT is missing from .env"
    )


send_email(
    recipient=recipient,
    subject="Stock Agent - Gmail Test",
    html_body=(
        "<html><body><p>"
        + html.escape(
            "This is a test email from your "
            "Indian Stock Momentum Agent."
        )
        + "</p></body></html>"
    ),
)