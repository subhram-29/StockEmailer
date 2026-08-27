import html
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from stockemailer.agent.gemini_agent import analyze_market
from stockemailer.notifications.gmail import send_email


load_dotenv()


def report_to_html(report: str) -> str:
    """Convert the plain-text report into safe, whitespace-preserving HTML."""

    escaped_report = html.escape(report)
    return (
        "<html><body>"
        "<pre style=\"font-family: monospace; white-space: pre-wrap;\">"
        f"{escaped_report}"
        "</pre>"
        "</body></html>"
    )


def main():

    print("=" * 60)
    print("INDIAN STOCK MOMENTUM AGENT")
    print("=" * 60)

    result = analyze_market()

    generated_at = datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).strftime("%Y-%m-%d %H:%M:%S %Z")
    result = (
        "REPORT TIMING\n"
        f"Data extraction/report generated at: {generated_at}\n"
        "This is the extraction completion time, not the market-bar time.\n\n"
        + result
    )

    print()
    print(result)

    recipient = os.getenv("EMAIL_RECIPIENT")

    if not recipient:
        raise ValueError(
            "EMAIL_RECIPIENT is missing from .env"
        )

    send_email(
        recipient=recipient,
        subject="Daily Indian Stock Momentum Report",
        html_body=report_to_html(result),
    )

    print()
    print("Daily report emailed successfully.")


if __name__ == "__main__":
    main()