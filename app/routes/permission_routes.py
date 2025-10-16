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