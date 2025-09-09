from flask import Blueprint, render_template, request, redirect, url_for, session
from app.utils.db import get_db_connection
from werkzeug.security import generate_password_hash

details_bp = Blueprint('details', __name__)

@details_bp.route('/details')
def details():
    if session.get("role") != "admin":
        return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username, role FROM users")  # adjust your users table columns
    users = cursor.fetchall()
    print("users u:",users)
    conn.close()

    return render_template('details.html', users=users)

@details_bp.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if session.get("role") != "admin":
        return "Unauthorized", 403

    if request.method == 'POST':
        username = request.form['username']
        role = request.form['role']
        password = request.form['password']

        hashed_pw = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, role, password) VALUES (%s, %s, %s)",
            (username, role, hashed_pw)
        )
        conn.commit()
        conn.close()

        return redirect(url_for('details.details'))

    # For GET request, show a simple add user form
    return render_template('add_user.html') 

@details_bp.route('/delete/<int:user_id>', methods=['GET'])
def delete_user(user_id):
    if session.get('role') != 'admin':
        return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reservations WHERE user_id = %s", (user_id,))



    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('details.details'))

@details_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if session.get("role") != "admin":
        return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if request.method == 'POST':
            username = request.form['username']
            role = request.form['role']

            password = request.form.get('password', "").strip()

            if password:
                # 🔐 Hash before storing
                # from werkzeug.security import generate_password_hash
                # hashed_pw = generate_password_hash(password)

                cursor.execute(
                    "UPDATE users SET username=%s, role=%s, password=%s WHERE id=%s",
                    (username, role, password, user_id)
                )
            else:
                cursor.execute(
                    "UPDATE users SET username=%s, role=%s WHERE id=%s",
                    (username, role, user_id)
                )

            conn.commit()
            return redirect(url_for('details.details'))

        # ✅ GET request → fetch user details
        cursor.execute("SELECT id, username, role FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()
        return render_template('edit_user.html', user=user)

    finally:
        cursor.close()   # ✅ always close cursor
        conn.close()     # ✅ always close conn



