"""
=============================================================================
SLACK/EMAIL ALERTS FOR SCRAPE FAILURES
=============================================================================

PURPOSE:
    Send notifications when scrapes fail or complete successfully.
    Helps you know if your automated daily scrapes are working.

SETUP:

    FOR SLACK:
    1. Create a Slack webhook:
       - Go to https://api.slack.com/messaging/webhooks
       - Create a new app for your workspace
       - Enable "Incoming Webhooks"
       - Create a webhook URL for your channel
    2. Set the SLACK_WEBHOOK_URL environment variable or add to config

    FOR EMAIL:
    1. For Gmail, you'll need an "App Password":
       - Go to Google Account > Security > 2-Step Verification > App Passwords
       - Generate a password for "Mail"
    2. Set environment variables:
       - EMAIL_SMTP_SERVER (default: smtp.gmail.com)
       - EMAIL_SMTP_PORT (default: 587)
       - EMAIL_USERNAME (your email)
       - EMAIL_PASSWORD (your app password)
       - EMAIL_TO (recipient email)

HOW TO USE:
    In your scraper scripts, import and call the alert functions:

        from alerts import send_success_alert, send_failure_alert

        try:
            # ... your scrape code ...
            send_success_alert("Daily Scrape", {"players": 100, "games": 20})
        except Exception as e:
            send_failure_alert("Daily Scrape", str(e))
            raise

    Or use as a decorator:

        from alerts import alert_on_completion

        @alert_on_completion("Daily Scrape")
        def main():
            # ... your scrape code ...
"""

import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================
# These can be overridden by environment variables

# Slack configuration
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')

# Email configuration
EMAIL_SMTP_SERVER = os.environ.get('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
EMAIL_SMTP_PORT = int(os.environ.get('EMAIL_SMTP_PORT', '587'))
EMAIL_USERNAME = os.environ.get('EMAIL_USERNAME', '')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
EMAIL_TO = os.environ.get('EMAIL_TO', '')

# Enable/disable alerts
ALERTS_ENABLED = os.environ.get('ALERTS_ENABLED', 'true').lower() == 'true'


# =============================================================================
# SLACK ALERTS
# =============================================================================

def send_slack_message(message, webhook_url=None):
    """
    Send a message to Slack via webhook.

    PARAMETERS:
        message (str): The message text to send
        webhook_url (str, optional): Slack webhook URL. Uses env var if not provided.

    RETURNS:
        bool: True if sent successfully, False otherwise

    EXAMPLE:
        >>> send_slack_message("Scrape completed successfully!")
    """
    url = webhook_url or SLACK_WEBHOOK_URL

    if not url:
        logger.warning("Slack webhook URL not configured")
        return False

    try:
        import requests

        payload = {'text': message}
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            logger.info("Slack message sent successfully")
            return True
        else:
            logger.error(f"Slack error: {response.status_code} - {response.text}")
            return False

    except ImportError:
        logger.error("requests library not installed. Run: pip install requests")
        return False
    except Exception as e:
        logger.error(f"Slack error: {e}")
        return False


def format_slack_success(job_name, stats=None):
    """
    Format a success message for Slack.

    PARAMETERS:
        job_name (str): Name of the job (e.g., "Daily Scrape")
        stats (dict, optional): Statistics to include

    RETURNS:
        str: Formatted message
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = f":white_check_mark: *{job_name} Completed*\n"
    message += f"_Time: {timestamp}_\n"

    if stats:
        message += "\n*Stats:*\n"
        for key, value in stats.items():
            message += f"  - {key}: {value}\n"

    return message


def format_slack_failure(job_name, error):
    """
    Format a failure message for Slack.

    PARAMETERS:
        job_name (str): Name of the job
        error (str): Error message or description

    RETURNS:
        str: Formatted message
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = f":x: *{job_name} Failed*\n"
    message += f"_Time: {timestamp}_\n"
    message += f"\n*Error:*\n```{error}```"
    return message


# =============================================================================
# EMAIL ALERTS
# =============================================================================

def send_email(subject, body, to_address=None):
    """
    Send an email notification.

    PARAMETERS:
        subject (str): Email subject line
        body (str): Email body (plain text)
        to_address (str, optional): Recipient email. Uses env var if not provided.

    RETURNS:
        bool: True if sent successfully, False otherwise

    EXAMPLE:
        >>> send_email("Scrape Complete", "All 330 games processed successfully.")
    """
    to_addr = to_address or EMAIL_TO

    if not all([EMAIL_USERNAME, EMAIL_PASSWORD, to_addr]):
        logger.warning("Email not configured. Set EMAIL_USERNAME, EMAIL_PASSWORD, EMAIL_TO")
        return False

    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USERNAME
        msg['To'] = to_addr
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Connect and send
        with smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT) as server:
            server.starttls()  # Enable TLS encryption
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            server.send_message(msg)

        logger.info(f"Email sent to {to_addr}")
        return True

    except Exception as e:
        logger.error(f"Email error: {e}")
        return False


def format_email_success(job_name, stats=None):
    """
    Format a success email body.

    PARAMETERS:
        job_name (str): Name of the job
        stats (dict, optional): Statistics to include

    RETURNS:
        tuple: (subject, body)
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    subject = f"[SUCCESS] {job_name}"

    body = f"{job_name} completed successfully.\n\n"
    body += f"Time: {timestamp}\n"

    if stats:
        body += "\nStatistics:\n"
        for key, value in stats.items():
            body += f"  - {key}: {value}\n"

    return subject, body


def format_email_failure(job_name, error):
    """
    Format a failure email body.

    PARAMETERS:
        job_name (str): Name of the job
        error (str): Error message

    RETURNS:
        tuple: (subject, body)
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    subject = f"[FAILED] {job_name}"

    body = f"{job_name} failed!\n\n"
    body += f"Time: {timestamp}\n"
    body += f"\nError:\n{error}\n"
    body += "\nPlease investigate and fix the issue."

    return subject, body


# =============================================================================
# HIGH-LEVEL ALERT FUNCTIONS
# =============================================================================

def send_success_alert(job_name, stats=None):
    """
    Send a success notification via all configured channels.

    PARAMETERS:
        job_name (str): Name of the job
        stats (dict, optional): Statistics about what was completed

    EXAMPLE:
        >>> send_success_alert("Daily Scrape", {
        ...     "Players processed": 100,
        ...     "Games scraped": 20,
        ...     "New hometowns found": 5
        ... })
    """
    if not ALERTS_ENABLED:
        logger.info("Alerts disabled")
        return

    # Send Slack alert
    if SLACK_WEBHOOK_URL:
        message = format_slack_success(job_name, stats)
        send_slack_message(message)

    # Send email alert
    if EMAIL_USERNAME and EMAIL_TO:
        subject, body = format_email_success(job_name, stats)
        send_email(subject, body)


def send_failure_alert(job_name, error):
    """
    Send a failure notification via all configured channels.

    PARAMETERS:
        job_name (str): Name of the job
        error (str): Description of what went wrong

    EXAMPLE:
        >>> send_failure_alert("Daily Scrape", "API returned 500 error")
    """
    if not ALERTS_ENABLED:
        logger.info("Alerts disabled")
        return

    # Send Slack alert
    if SLACK_WEBHOOK_URL:
        message = format_slack_failure(job_name, error)
        send_slack_message(message)

    # Send email alert
    if EMAIL_USERNAME and EMAIL_TO:
        subject, body = format_email_failure(job_name, error)
        send_email(subject, body)


# =============================================================================
# DECORATOR FOR AUTOMATIC ALERTS
# =============================================================================

def alert_on_completion(job_name):
    """
    Decorator that sends alerts on job completion or failure.

    USAGE:
        @alert_on_completion("Daily Scrape")
        def main():
            # ... your code ...
            return {'players': 100, 'games': 20}  # Optional: return stats

    If the function returns a dict, it's used as stats in the success alert.
    If the function raises an exception, a failure alert is sent.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)

                # If result is a dict, use it as stats
                stats = result if isinstance(result, dict) else None
                send_success_alert(job_name, stats)

                return result

            except Exception as e:
                send_failure_alert(job_name, str(e))
                raise  # Re-raise the exception

        return wrapper
    return decorator


# =============================================================================
# GITHUB ACTIONS INTEGRATION
# =============================================================================

def github_actions_alert():
    """
    Send alert using GitHub Actions workflow annotations.

    This creates visible warnings/errors in the GitHub Actions UI.
    Only works when running inside GitHub Actions.
    """
    # Check if we're in GitHub Actions
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        return

    # GitHub Actions uses special syntax for annotations
    # ::warning:: creates a warning
    # ::error:: creates an error
    print("::warning::Scrape completed - check the summary for details")


# =============================================================================
# TEST/DEMO
# =============================================================================

if __name__ == '__main__':
    print("Testing alert system...")
    print()

    # Check configuration
    print("Configuration:")
    print(f"  Slack webhook configured: {'Yes' if SLACK_WEBHOOK_URL else 'No'}")
    print(f"  Email configured: {'Yes' if EMAIL_USERNAME and EMAIL_TO else 'No'}")
    print(f"  Alerts enabled: {ALERTS_ENABLED}")
    print()

    # Test success alert
    print("Sending test success alert...")
    send_success_alert("Test Job", {
        "Items processed": 100,
        "Duration": "5 seconds"
    })

    # Test failure alert
    print("Sending test failure alert...")
    send_failure_alert("Test Job", "This is a test error message")

    print()
    print("Done! Check your Slack/email for test messages.")
