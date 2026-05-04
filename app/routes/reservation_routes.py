from flask import Blueprint, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
from app.utils.db import get_db_connection
from .notification_routes import notify_user
from .permission_routes import get_setting
from datetime import datetime, timezone
from flask import jsonify
from .notification_routes import schedule_email
import mysql.connector

reservation_bp = Blueprint('reservation', __name__)


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
        cursor.execute("SELECT * FROM ap WHERE ap_id = %s", (ap_id,))
        ap = cursor.fetchone()

    # get controller details 
    cursor.execute("SELECT * FROM controllers WHERE controller_id = %s", (controller_id,))
    controller = cursor.fetchone()

    # ✅ ADD COOLDOWN LOGIC HERE
    enable_cooldown = get_setting('enable_cooldown', 0)
    cooldown_hours = get_setting('cooldown_hours', 24)

    if enable_cooldown:
        cursor.execute("""
        SELECT end_datetime 
        FROM reservations
        WHERE user_id = %s 
        AND controller_id = %s
        ORDER BY end_datetime DESC
        LIMIT 1
    """, (user_id, controller_id))

    last_res = cursor.fetchone()
    if last_res:
        last_end = last_res['end_datetime'].replace(tzinfo=timezone.utc)
        cooldown_end = last_end + timedelta(hours=cooldown_hours)

        if datetime.now(timezone.utc) < cooldown_end:
            remaining = cooldown_end - datetime.now(timezone.utc)

            return jsonify({
                "status": "error",
                "message": f"⛔ You must wait {int(remaining.total_seconds()//3600)} hours before reserving this resource again."
            }), 403

    
    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    end_dt   = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

    # Ensure both are UTC-aware
    start_dt = start_dt.astimezone(timezone.utc)
    end_dt   = end_dt.astimezone(timezone.utc)
    duration = end_dt - start_dt

    # check validity of start date 
    if start_dt<datetime.now(timezone.utc):
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
    
    # Fetch active controllers for the user
    cursor.execute("""
        SELECT DISTINCT controller_id
        FROM reservations
        WHERE user_id = %s
        AND end_datetime >= NOW()
    """, (user_id,))

    active_controllers = cursor.fetchall() 

    
    # If user has active reservations
    if active_controllers:
        existing_controller_id = active_controllers[0]['controller_id']
        # print("existing_controller_id:",existing_controller_id)
        # print("controller_id:",controller_id)

        # If trying to reserve a different controller → BLOCK
        if int(existing_controller_id) != int(controller_id):
            return jsonify({
                "status": "error",
                "message": "You already have an active reservation on another cloud controller. "
                "Please release it before reserving a different controller."
            }),409
    
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
    
    rules= """Important usage instructions:
- Do not change the existing username or password, and do not create new credentials 
for the reserved portal.

Please adhere to these guidelines to avoid cancellation of your reservation."""

    start_str = start_dt.strftime("%b %d, %Y %I:%M %p UTC")
    end_str   = end_dt.strftime("%b %d, %Y %I:%M %p UTC")

    # reserve AP and controller 
    if ap_id:
        cursor.execute("""
            INSERT INTO reservations (user_id, ap_id, start_datetime, end_datetime,controller_id)
            VALUES (%s, %s, %s, %s,%s)
        """, (user_id, ap_id, start_dt, end_dt, controller_id))
        notify_user(
            to_email=session.get('username'),
            subject="Reservation Confirmed",
            email_body=f"Your reservation for resource ID {ap['model_name']} and {controller['name']} from {start_str} to {end_str} has been confirmed.\n\n{rules}",
        )
        # schedule email containing credentials to be sent 15 mins prior to start of reservation 
        reminder_time = start_dt - timedelta(minutes=15)
        if reminder_time > datetime.now(timezone.utc):
            schedule_email(
                to_email=session.get('username'),
                subject="Reservation Credentials",
                email_body=f"Your reservation for resource ID {ap['model_name']} and {controller['name']} from {start_str} to {end_str} has been confirmed.\n\n{rules}",
                run_datetime=reminder_time
            )
        else:
            notify_user(
                to_email=session.get('username'),
                subject="Reservation Credentials",
                email_body=f"Your reservation for resource ID {ap['model_name']} and {controller['name']} from {start_str} to {end_str} has been confirmed.\n\n{rules}",
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
            email_body=f"Your reservation for {controller['name']} from {start_str} to {end_str} has been confirmed.\n\n{rules}",
        )  
        # schedule email containing credentials to be sent 15 mins prior to start of reservation 
        reminder_time = start_dt - timedelta(minutes=15)
        if reminder_time > datetime.now(timezone.utc):
            schedule_email(
                to_email=session.get('username'),
                subject="Reservation Credentials",
                email_body=f"Your reservation for {controller['name']} from {start_str} to {end_str} has been confirmed.\n\n{rules}",
                run_datetime=reminder_time
            )  

        else:
            notify_user(
                to_email=session.get('username'),
                subject="Reservation Credentials",
                email_body=f"Your reservation for {controller['name']} from {start_str} to {end_str} has been confirmed.\n\n{rules}",
            )  

    conn.commit()
    
    inserted_id = cursor.lastrowid
    
    # Fetch the row using that ID
    cursor.execute("SELECT * FROM reservations WHERE id = %s", (inserted_id,))
    row = cursor.fetchone()
    
    row['start_datetime'] = row['start_datetime'].replace(tzinfo=timezone.utc)
    row['end_datetime']   = row['end_datetime'].replace(tzinfo=timezone.utc)
    if(ap):
        row['resource_name']=ap['model_name']
    row['controller_name']=controller['name']
    row['controller_url'] =controller['url']

    if active_count+1 >= max_reservations:
        reservation_limit_reached=True
    else:
        reservation_limit_reached=False

    conn.close()
    return jsonify(resource_id=ap_id, controller_id=controller_id,new_reservation=row,now=datetime.now(timezone.utc), reservation_limit_reached=reservation_limit_reached)


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

# override reservation 
def get_active_reservation(controller_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.id, r.user_id, u.username,
                r.start_datetime, r.end_datetime
            FROM reservations r
            JOIN users u ON u.id = r.user_id
            WHERE r.controller_id = %s
            AND r.end_datetime >  UTC_TIMESTAMP()
            ORDER BY r.start_datetime DESC
        """, (controller_id,))
        return cursor.fetchone()
    finally:
        conn.close()

def get_user_by_email(email):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE username = %s
            AND role = 'user'
            """,
            (email,)
        )

        user = cursor.fetchone()

        if not user:
            raise ValueError(f"User with email '{email}' not found")

        return user

    except mysql.connector.Error as db_err:
        # Database-level issues
        print(f"Database error in get_user_by_email: {db_err}")
        raise

    except ValueError:
        # Business logic error (user not found)
        raise

    except Exception as err:
        # Catch-all safety net
        print(f"Unexpected error in get_user_by_email: {err}")
        raise

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_last_reservation(user_id, controller_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, start_datetime, end_datetime
            FROM reservations
            WHERE user_id = %s
              AND controller_id = %s
            ORDER BY end_datetime DESC
            LIMIT 1
            """,
            (user_id, controller_id)
        )

        reservation = cursor.fetchone()

        if not reservation:
            return None

        # ✅ Explicitly mark DB DATETIME values as UTC
        reservation["start_datetime"] = reservation["start_datetime"].replace(
            tzinfo=timezone.utc
        )
        reservation["end_datetime"] = reservation["end_datetime"].replace(
            tzinfo=timezone.utc
        )

        return reservation

    except mysql.connector.Error as db_err:
        print(f"Database error in get_last_reservation: {db_err}")
        raise

    except Exception as err:
        print(f"Unexpected error in get_last_reservation: {err}")
        raise

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@reservation_bp.route("/admin/reservation_context")
def reservation_context():
    if 'user_id' not in session:
        return redirect(url_for('auth.index'))
    if session.get('role') != 'admin':
        return redirect(url_for('auth.index'))
    
    controller_id = request.args["controller_id"]

    res = get_active_reservation(controller_id)
    if not res:
        return jsonify({"current_reservations": None})
    
    for r in [res]:  # wrap in list for consistent frontend handling
        r["start"] = r["start_datetime"].replace(tzinfo=timezone.utc)
        r["end"] = r["end_datetime"].replace(tzinfo=timezone.utc)
        r["user_email"] = r.pop("username")  # rename for clarity

    return jsonify({
        "current_reservations": [res]
    })

@reservation_bp.route("/admin/check_cooldown", methods=["POST"])
def check_cooldown():
    if 'user_id' not in session:
        return redirect(url_for('auth.index'))
    if session.get('role') != 'admin':
        return redirect(url_for('auth.index'))
    
    cooldown_enabled = get_setting('enable_cooldown', 0)
    if not cooldown_enabled:
        return jsonify({"cooldown_active": False})
    
    data = request.json
    user = get_user_by_email(data["email"])
    print("user:",user)
    last = get_last_reservation(user["id"], data["controller_id"])

    if not last:
        return jsonify({"cooldown_active": False})
    
    cooldown_period_hours = get_setting('cooldown_hours', 24)

    cooldown_end = last["end_datetime"] + timedelta(hours=cooldown_period_hours)
    now = datetime.now(timezone.utc)

    return jsonify({
        "cooldown_active": now < cooldown_end,
        "cooldown_ends": cooldown_end.isoformat()
    })

@reservation_bp.route("/admin/override_reservation", methods=["POST"])
def override_reservation():
    # ---- Auth checks ----
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    if session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    data = request.json

    # ---- Parse input ----
    user = get_user_by_email(data["user_email"])

    start = datetime.fromisoformat(
        data["start"].replace("Z", "+00:00")
    ).astimezone(timezone.utc)

    end = datetime.fromisoformat(
        data["end"].replace("Z", "+00:00")
    ).astimezone(timezone.utc)

    controller_id = data["controller_id"]
    reason = data.get("reason", "Admin override")

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # ---------------------------------------------------
        # 1️⃣ Find overlapping reservations (any user)
        # ---------------------------------------------------
        cursor.execute(
            """
            SELECT r.id, r.user_id, u.username,
                   r.start_datetime, r.end_datetime
            FROM reservations r
            JOIN users u ON u.id = r.user_id
            WHERE r.controller_id = %s
              AND r.start_datetime < %s
              AND r.end_datetime   > %s
            """,
            (controller_id, end, start)
        )
        overlapping_reservations = cursor.fetchall()

        # ---------------------------------------------------
        # 2️⃣ Check cooldown for target user (informational)
        # ---------------------------------------------------
        cursor.execute(
            """
            SELECT end_datetime
            FROM reservations
            WHERE user_id = %s
              AND controller_id = %s
            ORDER BY end_datetime DESC
            LIMIT 1
            """,
            (user["id"], controller_id)
        )
        last_res = cursor.fetchone()

        cooldown_active = False
        cooldown_enable = get_setting('enable_cooldown', 0)
        cooldown_period = get_setting('cooldown_hours', 24)

        if last_res and cooldown_enable:
            last_end = last_res["end_datetime"].replace(tzinfo=timezone.utc)
            cooldown_end = last_end + timedelta(hours=cooldown_period)
            cooldown_active = start < cooldown_end

        # ---------------------------------------------------
        # 3️⃣ Delete overlapping reservations (admin override)
        # ---------------------------------------------------
        for r in overlapping_reservations:
            cursor.execute(
                "DELETE FROM reservations WHERE id = %s",
                (r["id"],)
            )

            # ---- Email user whose reservation was deleted ----
            schedule_email(
                to_email=r["username"],
                subject="Reservation Cancelled Due to Admin Override",
                email_body=(
                    f"Your reservation from {r['start_datetime']} to {r['end_datetime']} "
                    f"was cancelled by an administrator.\n\n"
                    f"Reason: {reason}\n\n"
                    "Please contact support if you have questions."
                ),
                run_datetime=datetime.now(timezone.utc)
            )

        # ---------------------------------------------------
        # 4️⃣ Create the override reservation
        # ---------------------------------------------------
        cursor.execute(
            """
            INSERT INTO reservations (
                user_id,
                controller_id,
                start_datetime,
                end_datetime
            ) VALUES (%s, %s, %s, %s)
            """,
            (
                user["id"],
                controller_id,
                start,
                end
            )
        )

        conn.commit()

        # ---------------------------------------------------
        # 5️⃣ Email the user who received the override
        # ---------------------------------------------------
        cooldown_note = (
            f"\n\nNote: This reservation was granted even though the {cooldown_period}‑hour cooldown "
            f"period was active until {cooldown_end}."
            if cooldown_active else ""
        )

        schedule_email(
            to_email=user["username"],
            subject="Reservation Granted via Admin Override",
            email_body=(
                f"An administrator has granted you access to the resource.\n\n"
                f"Reservation window:\n"
                f"Start: {start} (UTC)\n"
                f"End:   {end} (UTC)\n\n"
                f"Reason: {reason}"
                f"{cooldown_note}"
            ),
            run_datetime=datetime.now(timezone.utc)
        )

        return jsonify({
            "status": "success",
            "message": "Reservation overridden successfully",
            "overlaps_removed": len(overlapping_reservations),
            "cooldown_overridden": cooldown_active
        }), 200

    except Exception as err:
        if conn:
            conn.rollback()
        print(f"Error in override_reservation: {err}")
        return jsonify({"status": "error", "message": f"An error occurred: {err}"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()