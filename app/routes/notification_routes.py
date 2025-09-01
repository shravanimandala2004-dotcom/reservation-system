from flask import flash
import os
from ..utils.db import get_db_connection
from ..utils.email import send_email
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Fetch values from environment
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')

def notify_user(to_email, subject, email_body, browser_message=None):
    """
    Sends both an email and flashes a browser notification (if provided).
    """
    # Send Email
    send_email(to_email, subject, email_body)

    # Flash browser notification
    if browser_message:
        flash(browser_message, 'notification')

def get_emails_by_resource(resource_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT user_id FROM reservations WHERE resource_id = %s
    """, (resource_id,))
    emails = [row[0] for row in cursor.fetchall()]  # user_id is email
    conn.close()
    return emails