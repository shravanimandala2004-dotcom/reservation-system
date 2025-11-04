from flask import Blueprint, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
from app.utils.db import get_db_connection
from .notification_routes import notify_user
from .permission_routes import get_setting
from datetime import datetime
from flask import jsonify
from .notification_routes import schedule_email

reservation_bp = Blueprint('reservation', __name__)

# @reservation_bp.route('/reserve', methods=['GET', 'POST'])
# def reserve():
#     if 'user_id' not in session:
#         return redirect(url_for('auth.index'))

#     user_id = session['user_id']
#     conn = get_db_connection()
#     cursor = conn.cursor(dictionary=True)

#     if request.method == 'POST':
#         resource_id = request.form['resource_id']
#         start_dt = datetime.strptime(request.form['start_datetime'], '%Y-%m-%dT%H:%M')
#         end_dt = datetime.strptime(request.form['end_datetime'], '%Y-%m-%dT%H:%M')
#         duration = end_dt - start_dt

#         # Validation checks
#         if duration <= timedelta(0):
#             conn.close()
#             return "⛔ End time must be after start time"

#         elif duration > timedelta(days=15):
#             conn.close()
#             return "⛔ Reservation cannot be longer than 15 days"

#         # Check active reservations
#         cursor.execute("""
#             SELECT r.id, r.resource_id, r.start_datetime, r.end_datetime,
#                    res.name AS resource_name, res.link
#             FROM reservations r
#             JOIN resources res ON r.resource_id = res.id
#             WHERE r.user_id = %s AND r.end_datetime >= NOW()
#         """, (user_id,))
#         active_reservations = cursor.fetchall()

#         if len(active_reservations) >= 2:
#             conn.close()
#             return "⚠️ You already have 2 active reservations."

#         # Insert new reservation
#         cursor.execute("""
#             INSERT INTO reservations (user_id, resource_id, start_datetime, end_datetime)
#             VALUES (%s, %s, %s, %s)
#         """, (user_id, resource_id, start_dt, end_dt))

#         notify_user(
#             to_email=session.get('username'),
#             subject="Reservation Confirmed",
#             email_body=f"Your reservation for resource ID {resource_id} from {start_dt} to {end_dt} has been confirmed.",
#         )

#         conn.commit()
#         conn.close()
#         return redirect(url_for('reservation.reserve'))

#     # -------------------------------
#     # GET method: Show resources & active reservations
#     # -------------------------------
#     cursor.execute("SELECT * FROM resources")
#     resources = cursor.fetchall()

#     cursor.execute("""
#         SELECT r.*, res.name AS resource_name, res.link
#         FROM reservations r
#         JOIN resources res ON r.resource_id = res.id
#         WHERE r.user_id = %s AND r.end_datetime >= NOW()
#     """, (user_id,))
#     active_reservations = cursor.fetchall()

#     max_reservations = get_setting('max_reservations', 2)
#     max_days = get_setting('max_days', 15)

#     conn.close()
#     return render_template(
#         'reserve.html',
#         resources=resources,
#         active_reservations=active_reservations,
#         active_count=len(active_reservations),
#         max_reservations=max_reservations,
#         max_days=max_days,
#         role=session.get('role')
#     )

# @reservation_bp.route('/reserve_page')
# def reserve_page():
#     if 'user_id' not in session:
#         return redirect(url_for('auth.index'))

#     user_id = session['user_id']
#     resource_id = request.args.get('resource_id')
#     controller_id = request.args.get('controller_id')

#     resource = None
#     controller = None

#     conn=get_db_connection()
#     cursor=conn.cursor(dictionary=True)

#     if resource_id:
#         cursor.execute("SELECT * FROM resources WHERE id = %s", (resource_id,))
#         resource = cursor.fetchone()

#     if controller_id:
#         cursor.execute("SELECT * FROM controllers WHERE controller_id = %s", (controller_id,))
#         controller = cursor.fetchone()

#     cursor.execute("""
#         SELECT r.*, res.model_name AS resource_name, c.name AS controller_name
#         FROM reservations r
#         LEFT JOIN ap res ON r.ap_id = res.ap_id
#         LEFT JOIN controllers c ON r.controller_id = c.controller_id
#         WHERE r.user_id = %s AND r.end_datetime >= NOW()
#     """, (user_id,))
#     active_reservations = cursor.fetchall()
    
#     for r in active_reservations:
#         r['start_datetime_formatted'] = r['start_datetime'].strftime("%b %d, %Y %H:%M")
#         r['end_datetime_formatted'] = r['end_datetime'].strftime("%b %d, %Y %H:%M")

#     max_reservations = get_setting('max_reservations', 2)
#     max_days = get_setting('max_days', 15)

#     conn.close()

#     return render_template('reserve_page.html', 
#         resource=resource, 
#         controller=controller,
#         active_reservations=active_reservations,
#         active_count=len(active_reservations),
#         max_reservations=max_reservations,
#         max_days=max_days,
#         role=session.get('role'))

# reserve resources
@reservation_bp.route('/reserve_page', methods=['POST'])
def reserve():
    if 'user_id' not in session:
        return redirect(url_for('auth.index'))
    
    user_id=session['user_id']
    conn=get_db_connection()
    cursor=conn.cursor(dictionary=True)

    # get no. of maximum reservations and max no. of days a resource can be reserved
    max_reservations = get_setting('max_reservations', 2)
    max_days = get_setting('max_days', 15)

    # Check active reservations
    cursor.execute("""
        SELECT count(res.controller_id) as count
        FROM reservations res
        WHERE res.user_id = %s AND res.end_datetime >= NOW()
    """, (user_id,))
    active = cursor.fetchall() # active reservations of the user
    active_count = active[0]['count'] # number of active reservations
    
    
    data = request.get_json()
    ap_id = data.get('ap_id') or None
    controller_id = data.get('controller_id')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    ap=None

    # get AP details 
    if(ap_id):
        cursor.execute("SELECT * FROM AP WHERE ap_id = %s", (ap_id,))
        ap = cursor.fetchone()
    # get controller details 
    cursor.execute("SELECT * FROM controllers WHERE controller_id = %s", (controller_id,))
    controller = cursor.fetchone()

    start_dt = datetime.strptime(start_time, '%Y-%m-%dT%H:%M')
    end_dt = datetime.strptime(end_time, '%Y-%m-%dT%H:%M')
    duration = end_dt - start_dt

    # check validity of start date 
    if start_dt<datetime.now():
        conn.close()
        return jsonify({
            "status": "error",
            "message": "⛔ Invalid start time"
        }), 400
    # check validity of duration
    if duration <= timedelta(0):
        conn.close()        
        return jsonify({
            "status": "error",
            "message": "⛔ End time must be after start time"
        }), 400

    elif duration > timedelta(days=max_days): 
        conn.close()
        return jsonify({
            "status": "error",
            "message": f"⛔ Reservation cannot be longer than {max_days} days"
        }), 400

    if active_count >= max_reservations:
        conn.close()
        return jsonify({
            "status": "error",
            "message": f"⚠️ You already have {max_reservations} active reservations."
        }), 400
    
    # Check for overlapping reservations
    cursor.execute("""
        SELECT * FROM reservations
        WHERE controller_id = %s
        AND (
            (start_datetime <= %s AND end_datetime > %s) OR
            (start_datetime < %s AND end_datetime >= %s) OR
            (start_datetime >= %s AND end_datetime <= %s)
        )
    """, (controller_id, end_dt, start_dt, end_dt, start_dt, start_dt, end_dt))

    controller_conflicts = cursor.fetchall()

    if ap_id:
        cursor.execute("""
            SELECT * FROM reservations
            WHERE ap_id = %s
            AND (
                (start_datetime <= %s AND end_datetime > %s) OR
                (start_datetime < %s AND end_datetime >= %s) OR
                (start_datetime >= %s AND end_datetime <= %s)
            )
        """, (ap_id, end_dt, start_dt, end_dt, start_dt, start_dt, end_dt))

        ap_conflicts = cursor.fetchall()
    else:
        ap_conflicts = []

    if controller_conflicts or ap_conflicts:
        conn.close()
        return jsonify({
            "status": "error",
            "message": "❌ The selected controller or AP is already reserved during the chosen time slot."
        }), 400

    # reserve AP and controller 
    if ap_id:
        cursor.execute("""
            INSERT INTO reservations (user_id, ap_id, start_datetime, end_datetime,controller_id)
            VALUES (%s, %s, %s, %s,%s)
        """, (user_id, ap_id, start_dt, end_dt, controller_id))
        notify_user(
            to_email=session.get('username'),
            subject="Reservation Confirmed",
            email_body=f"Your reservation for resource ID {ap['model_name']} and {controller['name']} from {start_dt} to {end_dt} has been confirmed.",
        )
        # schedule email containing credentials to be sent 15 mins prior to start of reservation 
        reminder_time = start_dt - timedelta(minutes=15)
        if reminder_time > datetime.now():
            schedule_email(
                to_email=session.get('username'),
                subject="Reservation Credentials",
                email_body=f"Your reservation for resource ID {ap['model_name']} and {controller['name']} from {start_dt} to {end_dt} has been confirmed.\n\n Credentials to access resource:\n Email:\nPassword:",
                run_datetime=reminder_time
            )
        else:
            notify_user(
                to_email=session.get('username'),
                subject="Reservation Credentials",
                email_body=f"Your reservation for resource ID {ap['model_name']} and {controller['name']} from {start_dt} to {end_dt} has been confirmed.\n\n Credentials to access resource:\n Email:\nPassword:",
            )
    # reserve cloud/controller 
    else:
        cursor.execute("""
            INSERT INTO reservations (user_id, start_datetime, end_datetime,controller_id)
            VALUES (%s, %s, %s, %s)
        """, (user_id, start_dt, end_dt, controller_id))
        notify_user(
            to_email=session.get('username'),
            subject="Reservation Confirmed",
            email_body=f"Your reservation for {controller['name']} from {start_dt} to {end_dt} has been confirmed.",
        )  
        # schedule email containing credentials to be sent 15 mins prior to start of reservation 
        reminder_time = start_dt - timedelta(minutes=15)
        if reminder_time > datetime.now():
            schedule_email(
                to_email=session.get('username'),
                subject="Reservation Credentials",
                email_body=f"Your reservation for {controller['name']} from {start_dt} to {end_dt} has been confirmed.\n\nCredentials to access resource:\nEmail:\nPassword:",
                run_datetime=reminder_time
            )  

        else:
            notify_user(
                to_email=session.get('username'),
                subject="Reservation Credentials",
                email_body=f"Your reservation for {controller['name']} from {start_dt} to {end_dt} has been confirmed.\n\nCredentials to access resource:\nEmail:\nPassword:",
            )  

    conn.commit()
    
    inserted_id = cursor.lastrowid
    
    # Fetch the row using that ID
    cursor.execute("SELECT * FROM reservations WHERE id = %s", (inserted_id,))
    row = cursor.fetchone()
    
    row['start_datetime_formatted'] = row['start_datetime'].strftime("%b %d, %Y %H:%M")
    row['end_datetime_formatted'] = row['end_datetime'].strftime("%b %d, %Y %H:%M")
    if(ap):
        row['resource_name']=ap['model_name']
    row['controller_name']=controller['name']


    conn.close()
    return jsonify(resource_id=ap_id, controller_id=controller_id,new_reservation=row)


# @reservation_bp.route('/delete_reservation/<int:id>')
# def delete_reservation(id):
#     if 'user_id' not in session:
#         return redirect(url_for('auth.index'))

#     user_id = session['user_id']

#     conn = get_db_connection()
#     cursor = conn.cursor()

#     # Make sure the reservation belongs to the current user
#     cursor.execute("SELECT * FROM reservations WHERE id = %s AND user_id = %s", (id, user_id))
#     reservation = cursor.fetchone()

#     if reservation:
#         cursor.execute("DELETE FROM reservations WHERE id = %s", (id,))
#         conn.commit()
#         notify_user(
#             to_email=session.get('username'),
#             subject="Reservation Cancelled",
#             email_body=f"Your reservation ID {id} has been cancelled.",
#         )

#     conn.close()
#     return redirect(url_for('reservation.reserve'))

@reservation_bp.route('/cancel_reservation',methods=['POST'])
def cancel_reservation():
    if 'user_id' not in session:
        return redirect(url_for('auth.index'))
    print("inside cancel reservation")

    user_id = session['user_id']

    data = request.get_json()

    if not data or 'id' not in data:
        return jsonify({'error': 'Missing reservation ID'}), 400

    id = data['id']
    print("id:",id)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Make sure the reservation belongs to the current user
    cursor.execute("SELECT * FROM reservations WHERE id = %s AND user_id = %s", (id, user_id))
    reservation = cursor.fetchone()
    print("reservation:",reservation)

    if reservation:
        cursor.execute("DELETE FROM reservations WHERE id = %s", (id,))
        conn.commit()
        print("deleted reservation")
        notify_user(
            to_email=session.get('username'),
            subject="Reservation Cancelled",
            email_body=f"Your reservation ID {id} has been cancelled.",
        )
        response = {'status': 'success', 'cancelled_id': id}
    else:
        response = {'status': 'error', 'message': 'Reservation not found or unauthorized'}

    conn.close()
    return jsonify(response)