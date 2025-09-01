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

        cursor.execute("UPDATE permissions SET max_reservations=%s, max_days=%s WHERE id=1",
                       (max_reservations, max_days))
        conn.commit()

    cursor.execute("SELECT * FROM permissions WHERE id=1")
    settings = cursor.fetchone()
    conn.close()

    return render_template('permission.html', settings=settings)