import os
from ..utils.db import get_db_connection
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

# Load environment variables from .env file
load_dotenv()

# Fetch values from environment
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')

scheduler = BackgroundScheduler()
scheduler.start()

def notify_user(to_email, subject, email_body):
    # Send Email
    if not to_email or '@' not in to_email:
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(email_body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Email failed to send to {to_email}: {e}")

# get emails of users who have reserved a particular resource 
def get_emails_by_resource(resource_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT u.username
        FROM reservations r
        JOIN users u ON r.user_id = u.id
        WHERE r.resource_id = %s""", (resource_id,))
    emails = [row[0] for row in cursor.fetchall()]  
    conn.close()
    return emails

# schedule email to be sent at a particular time 
def schedule_email(to_email, subject, email_body, run_datetime):
    def job():
        notify_user(to_email, subject, email_body)

    scheduler.add_job(job, 'date', run_date=run_datetime)