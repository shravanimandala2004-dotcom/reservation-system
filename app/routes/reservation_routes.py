from flask import Blueprint, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
from app.utils.db import get_db_connection
from .notification_routes import notify_user

reservation_bp = Blueprint('reservation', __name__)

@reservation_bp.route('/reserve', methods=['GET', 'POST'])
def reserve():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        resource_id = request.form['resource_id']
        start_dt = datetime.strptime(request.form['start_datetime'], '%Y-%m-%dT%H:%M')
        end_dt = datetime.strptime(request.form['end_datetime'], '%Y-%m-%dT%H:%M')
        duration = end_dt - start_dt

        # Validation checks
        if duration <= timedelta(0):
            conn.close()
            return "⛔ End time must be after start time"

        elif duration > timedelta(days=15):
            conn.close()
            return "⛔ Reservation cannot be longer than 15 days"

        # Check active reservations
        cursor.execute("""
            SELECT r.id, r.resource_id, r.start_datetime, r.end_datetime,
                   res.name AS resource_name, res.link
            FROM reservations r
            JOIN resources res ON r.resource_id = res.id
            WHERE r.user_id = %s AND r.end_datetime >= NOW()
        """, (user_id,))
        active_reservations = cursor.fetchall()

        if len(active_reservations) >= 2:
            conn.close()
            return "⚠️ You already have 2 active reservations."

        # Insert new reservation
        cursor.execute("""
            INSERT INTO reservations (user_id, resource_id, start_datetime, end_datetime)
            VALUES (%s, %s, %s, %s)
        """, (user_id, resource_id, start_dt, end_dt))

        notify_user(
            to_email=session.get('username'),
            subject="Reservation Confirmed",
            email_body=f"Your reservation for resource ID {resource_id} from {start_dt} to {end_dt} has been confirmed.",
        )

        conn.commit()
        conn.close()
        return redirect(url_for('reservation.reserve'))

    # -------------------------------
    # GET method: Show resources & active reservations
    # -------------------------------
    cursor.execute("SELECT * FROM resources")
    resources = cursor.fetchall()

    cursor.execute("""
        SELECT r.*, res.name AS resource_name, res.link
        FROM reservations r
        JOIN resources res ON r.resource_id = res.id
        WHERE r.user_id = %s AND r.end_datetime >= NOW()
    """, (user_id,))
    active_reservations = cursor.fetchall()

    conn.close()
    return render_template(
        'reserve.html',
        resources=resources,
        active_reservations=active_reservations,
        active_count=len(active_reservations)
    )

@reservation_bp.route('/delete_reservation/<int:id>')
def delete_reservation(id):
    if 'user_id' not in session:
        return redirect(url_for('auth.index'))

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Make sure the reservation belongs to the current user
    cursor.execute("SELECT * FROM reservations WHERE id = %s AND user_id = %s", (id, user_id))
    reservation = cursor.fetchone()

    if reservation:
        cursor.execute("DELETE FROM reservations WHERE id = %s", (id,))
        conn.commit()
        notify_user(
            to_email=session.get('username'),
            subject="Reservation Cancelled",
            email_body=f"Your reservation ID {id} has been cancelled.",
        )

    conn.close()
    return redirect(url_for('reservation.reserve'))