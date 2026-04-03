from flask import Blueprint, render_template, request, redirect, url_for, session
from app.utils.db import get_db_connection

permission_bp = Blueprint('permission', __name__)

@permission_bp.route('/permission', methods=['GET', 'POST'])
def permission():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('auth.index'))  # only admins allowed

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        max_reservations = request.form['max_reservations']
        max_days = request.form['max_days']
        max_preBooking=request.form['max_preBooking']

        cursor.execute("UPDATE permissions SET max_reservations=%s, max_days=%s,max_preBooking=%s",
                       (max_reservations, max_days,max_preBooking))
        conn.commit()

    conn.close()

    return redirect(url_for('inventory.admin_page'))
 
def get_setting(key, default):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM permissions")
    row = cursor.fetchone()
    conn.close()
    return int(row[key]) if row else default

@permission_bp.route('/access', methods=['GET', 'POST'])
def access_page():
    if session.get("role") != "admin":
        return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    users = []

    if request.method == 'POST':
        access_type = request.form.get('access_type')   # department / individual
        role_type = request.form.get('role_type')       # admin / user
        search = request.form.get('search')

        # 🔍 SEARCH LOGIC
        query = "SELECT id, username, role FROM users WHERE 1=1"
        values = []

        if role_type:
            query += " AND role = %s"
            values.append(role_type)

        if search:
            query += " AND username LIKE %s"
            values.append(f"%{search}%")

        cursor.execute(query, tuple(values))
        users = cursor.fetchall()

        # 💾 SAVE (optional future logic)
        if 'save' in request.form:
            selected_users = request.form.getlist('selected_users')
            # You can store/update permissions here later
            print("Selected Users:", selected_users)

    conn.close()

    return render_template('access.html', users=users)