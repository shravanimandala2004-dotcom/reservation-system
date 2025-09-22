from flask import Blueprint, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
from app.utils.db import get_db_connection
from .notification_routes import notify_user
from .permission_routes import get_setting
from datetime import datetime

reservation_bp = Blueprint('reservation', __name__)

@reservation_bp.route('/reserve', methods=['GET', 'POST'])
def reserve():
    if 'user_id' not in session:
        return redirect(url_for('auth.index'))

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

    max_reservations = get_setting('max_reservations', 2)
    max_days = get_setting('max_days', 15)

    conn.close()
    return render_template(
        'reserve.html',
        resources=resources,
        active_reservations=active_reservations,
        active_count=len(active_reservations),
        max_reservations=max_reservations,
        max_days=max_days,
        role=session.get('role')
    )

@reservation_bp.route('/reserve_page')
def reserve_page():
    if 'user_id' not in session:
        return redirect(url_for('auth.index'))

    user_id = session['user_id']
    resource_id = request.args.get('resource_id')
    controller_id = request.args.get('controller_id')

    resource = None
    controller = None

    conn=get_db_connection()
    cursor=conn.cursor(dictionary=True)

    if resource_id:
        cursor.execute("SELECT * FROM resources WHERE id = %s", (resource_id,))
        resource = cursor.fetchone()

    if controller_id:
        cursor.execute("SELECT * FROM controllers WHERE controller_id = %s", (controller_id,))
        controller = cursor.fetchone()

    cursor.execute("""
        SELECT r.*, res.name AS resource_name, res.link, c.name AS controller_name
        FROM reservations r
        LEFT JOIN resources res ON r.resource_id = res.id
        LEFT JOIN controllers c ON r.controller_id = c.controller_id
        WHERE r.user_id = %s AND r.end_datetime >= NOW()
    """, (user_id,))
    active_reservations = cursor.fetchall()
    
    for r in active_reservations:
        r['start_datetime_formatted'] = r['start_datetime'].strftime("%b %d, %Y %H:%M")
        r['end_datetime_formatted'] = r['end_datetime'].strftime("%b %d, %Y %H:%M")

    max_reservations = get_setting('max_reservations', 2)
    max_days = get_setting('max_days', 15)

    conn.close()

    return render_template('reserve_page.html', 
        resource=resource, 
        controller=controller,
        active_reservations=active_reservations,
        active_count=len(active_reservations),
        max_reservations=max_reservations,
        max_days=max_days,
        role=session.get('role'))

@reservation_bp.route('/reserve_page', methods=['POST'])
def handle_reservation():
    if 'user_id' not in session:
        return redirect(url_for('auth.index'))
    
    user_id=session['user_id']
    conn=get_db_connection()
    cursor=conn.cursor(dictionary=True)

    # Check active reservations
    max_reservations = get_setting('max_reservations', 2)
    cursor.execute("""
        SELECT count(res.controller_id) as count
        FROM ap_reservations res
        WHERE res.user_id = %s AND res.end_datetime >= NOW()
    """, (user_id,))
    active = cursor.fetchall()
    active_count = active[0]['count']
    
    ap_id = request.form['ap_id']
    controller_id = request.form['controller_id']
    if(ap_id):
        cursor.execute("SELECT * FROM AP WHERE ap_id = %s", (ap_id,))
    ap = cursor.fetchone()

    cursor.execute("SELECT * FROM controllers WHERE controller_id = %s", (controller_id,))
    controller = cursor.fetchone()

    print("resource:",ap,"controller:",controller)

    start_dt = datetime.strptime(request.form['start_datetime'], '%Y-%m-%dT%H:%M')
    end_dt = datetime.strptime(request.form['end_datetime'], '%Y-%m-%dT%H:%M')
    duration = end_dt - start_dt

    if duration <= timedelta(0):
        conn.close()
        return "⛔ End time must be after start time"

    elif duration > timedelta(days=15):
        conn.close()
        return "⛔ Reservation cannot be longer than 15 days"

    if active_count >= max_reservations:
        conn.close()
        return "⚠️ You already have 2 active reservations."

    if ap_id:
        cursor.execute("""
            INSERT INTO ap_reservations (user_id, ap_id, start_datetime, end_datetime,controller_id)
            VALUES (%s, %s, %s, %s,%s)
        """, (user_id, ap_id, start_dt, end_dt, controller_id))
        notify_user(
            to_email=session.get('username'),
            subject="Reservation Confirmed",
            email_body=f"Your reservation for resource ID {ap['model_name']} and {controller['name']} from {start_dt} to {end_dt} has been confirmed.",
        )
    else:
        cursor.execute("""
            INSERT INTO ap_reservations (user_id, start_datetime, end_datetime,controller_id)
            VALUES (%s, %s, %s, %s)
        """, (user_id, start_dt, end_dt, controller_id))
        notify_user(
            to_email=session.get('username'),
            subject="Reservation Confirmed",
            email_body=f"Your reservation for {controller['name']} from {start_dt} to {end_dt} has been confirmed.",
        )    

    conn.commit()
    conn.close()
    return redirect(url_for('reservation.reserve_page', resource_id=ap_id, controller_id=controller_id))


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