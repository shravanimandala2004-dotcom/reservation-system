from flask import Blueprint, render_template, request, redirect, url_for, session
from app.utils.db import get_db_connection
from werkzeug.security import generate_password_hash

details_bp = Blueprint('details', __name__)

# @details_bp.route('/details')
# def details():
#     if session.get("role") != "admin":
#         return "Unauthorized", 403

#     conn = get_db_connection()
#     cursor = conn.cursor(dictionary=True)
#     cursor.execute("SELECT id, username, role FROM users")  # adjust your users table columns
#     users = cursor.fetchall()
#     print("users u:",users)
#     conn.close()

#     return render_template('details.html', users=users , role=session.get('role'))

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

            # password = request.form.get('password', "").strip()

            # if password:
            #     # 🔐 Hash before storing
            #     # from werkzeug.security import generate_password_hash
            #     # hashed_pw = generate_password_hash(password)

            #     cursor.execute(
            #         "UPDATE users SET username=%s, role=%s, password=%s WHERE id=%s",
            #         (username, role, password, user_id)
            #     )
            # else:
            cursor.execute(
                "UPDATE users SET username=%s, role=%s WHERE id=%s",
                (username, role, user_id)
            )

            conn.commit()
            return redirect(url_for('details.details'))

        # ✅ GET request → fetch user details
        cursor.execute("SELECT id, username, role FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()
        return render_template('edit_user.html', user=user, role=session.get('role'))

    finally:
        cursor.close()   # ✅ always close cursor
        conn.close()     # ✅ always close conn

@details_bp.route('/details')
def details():
    # Admin-only access
    if session.get("role") != "admin":
        return "Unauthorized", 403

    # ---- Pagination params ----
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    # ---- Filters ----
    search = request.args.get("search", "").strip()
    role_filter = request.args.get("role", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ---- Base query ----
    base_query = "FROM users WHERE 1=1"
    params = []

    if search:
        base_query += " AND username LIKE %s"
        params.append(f"%{search}%")

    if role_filter in ("admin", "user"):
        base_query += " AND role = %s"
        params.append(role_filter)

    # ---- Total count (for pagination) ----
    count_query = "SELECT COUNT(*) AS total " + base_query
    cursor.execute(count_query, params)
    total_users = cursor.fetchone()["total"]

    total_pages = (total_users + per_page - 1) // per_page

    # ---- Paginated data query ----
    data_query = (
        "SELECT id, username, role "
        + base_query +
        " ORDER BY id "
        " LIMIT %s OFFSET %s"
    )

    cursor.execute(data_query, params + [per_page, offset])
    users = cursor.fetchall()

    # ---- Admin departments ----
    cursor.execute("SELECT id, department_name FROM admin_departments")
    departments = cursor.fetchall()

    conn.close()

    return render_template(
        "details.html",
        users=users,
        departments=departments,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        search=search,
        role_filter=role_filter,
        role=session.get("role")
    )

@details_bp.route('/departments/add', methods=['POST'])
def add_department():
    if session.get("role") != "admin":
        return "Unauthorized", 403

    department = request.form.get("department_name")

    if department:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT IGNORE INTO admin_departments (department_name) VALUES (%s)",
            (department,)
        )
        conn.commit()
        conn.close()

    return redirect(url_for('details.details'))

@details_bp.route('/departments/delete/<int:dept_id>')
def delete_department(dept_id):
    if session.get("role") != "admin":
        return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admin_departments WHERE id = %s", (dept_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('details.details'))