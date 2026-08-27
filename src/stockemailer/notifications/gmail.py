import base64
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# Only permission required:
# send emails from the authenticated Gmail account.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]

BASE_DIR = Path(__file__).resolve().parents[3]

CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"


def get_gmail_service():
    """
    Authenticate with Gmail using OAuth 2.0.

    First run:
        Opens browser for Google authorization.

    Subsequent runs:
        Uses the saved refresh token automatically.
    """

    credentials = None

    # Existing OAuth token
    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES
        )

    # Token expired → refresh it
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    # No valid credentials → start OAuth flow
    elif not credentials or not credentials.valid:

        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE,
            SCOPES
        )

        credentials = flow.run_local_server(
            port=0
        )

        TOKEN_FILE.write_text(
            credentials.to_json()
        )

    service = build(
        "gmail",
        "v1",
        credentials=credentials
    )

    return service


def send_email(
    recipient: str,
    subject: str,
    html_body: str,
):
    """
    Send an HTML email using Gmail API.

    Args:
        recipient: Recipient email address.
        subject: Email subject line.
        html_body: Full HTML markup for the email body. Must be valid
            HTML (e.g. wrapped in a basic document with inline styles),
            not plain text — this is rendered directly by the recipient's
            mail client.
    """

    service = get_gmail_service()

    message = MIMEText(
        html_body,
        "html",
        "utf-8",
    )

    message["to"] = recipient
    message["subject"] = subject

    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    create_message = {
        "raw": encoded_message
    }

    sent_message = (
        service.users()
        .messages()
        .send(
            userId="me",
            body=create_message
        )
        .execute()
    )

    print(
        f"Email sent successfully. "
        f"Message ID: {sent_message['id']}"
    )