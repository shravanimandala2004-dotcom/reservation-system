from flask import Flask, render_template, request, redirect, url_for, session
from flask import Flask, render_template
from datetime import datetime, timedelta
import mysql.connector
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

EMAIL_ADDRESS = 'shravanimandala2004@gmail.com'
EMAIL_PASSWORD = 'Shravani@1234'

def send_email(to_email, subject, body):
    
    if not to_email or '@' not in to_email:
        return  # skip invalid emails

    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Email failed to send to {to_email}: {e}")

def get_emails_by_resource(resource_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT user_id FROM reservations WHERE resource_id = %s
    """, (resource_id,))
    emails = [row[0] for row in cursor.fetchall()]  # user_id is email
    conn.close()
    return emails

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',       # e.g., 'root'
        password='Shravani@1234',   # e.g., 'admin123'
        database='ap_reservation'         # the DB you created
    )

app = Flask(__name__)
app.secret_key = 'your-secret-key'

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password, role) VALUES ( %s, %s, %s)",
                           ( username, password, role))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))
        except Exception as e:
            return f"Signup failed: {str(e)}"
    
    return render_template('signup.html')


@app.route('/user')
def user_dashboard():
    return render_template('user_dashboard.html')

@app.route('/admin')
def admin_dashboard():
    return render_template('admin_dashboard.html')



@app.route('/reserve', methods=['GET', 'POST'])
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
        conn.commit()
        conn.close()
        return redirect(url_for('reserve'))

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')

        if not username or not password or not role:
            return "Missing username, password, or role."

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s AND role=%s",
                       (username, password, role))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']     
            session['username'] = username
            session['role'] = role
            return redirect(url_for('inventory'))
        else:
            return "❌ Invalid login credentials"
    else:
        return redirect(url_for('index'))


@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST' and session.get('role') == 'admin':
        name = request.form['resource_name']
        ap_count = request.form['ap_count']
        status = request.form['status']
        link = request.form['link']
        action_type = request.form.get('action_type', 'add')  # from form hidden field

        if action_type == 'edit':
            resource_id = request.form['resource_id']
            cursor.execute("UPDATE resources SET name=%s, ap_count=%s, status=%s, link=%s WHERE id=%s",
                           (name, ap_count, status, link, resource_id))
            conn.commit()

            
            emails = get_emails_by_resource(resource_id)
            for email in emails:
                send_email(
                    email,
                    f"Resource Updated: {name}",
                    f"The resource '{name}' has been updated.\nAPs: {ap_count}\nStatus: {status}"
                )

        else:  # Add new resource
            cursor.execute("INSERT INTO resources (name, ap_count, status, link) VALUES (%s, %s, %s, %s)",
                           (name, ap_count, status, link))
            conn.commit()


            if session.get('role') == 'admin':
                subject = "Resource Added"
                body = f"""
                Resource Name: {name}
                AP Count: {ap_count}
                Status: {status}
                Link: {link}
                Action: ADDED
                """
                send_email(session.get('username'), subject, body)
 

            # Optional: Send to all users if needed
            cursor.execute("SELECT username FROM users")
            all_users = cursor.fetchall()
            for user in all_users:
                send_email(
                    user['username'],
                    f"New Resource Added: {name}",
                    f"A new resource '{name}' with {ap_count} APs is now available."
                )

    # Display inventory
    cursor.execute("SELECT * FROM resources")
    resources = cursor.fetchall()
    conn.close()
    return render_template('inventory.html', resources=resources, role=session.get('role'))



@app.route('/delete_resource/<int:id>')
def delete_resource(id):
    if session.get('role') == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get resource details first
        cursor.execute("SELECT * FROM resources WHERE id = %s", (id,))
        resource = cursor.fetchone()

        if resource:
            # Get all user emails for this resource
            emails = get_emails_by_resource(id)

            # Notify each user
            for email in emails:
                send_email(
                    email,
                    f"Resource Deleted: {resource['name']}",
                    f"The resource '{resource['name']}' with {resource['ap_count']} APs has been deleted."
                )

            cursor.execute("DELETE FROM resources WHERE id = %s", (id,))
            conn.commit()
        conn.close()
    return redirect(url_for('inventory'))


@app.route('/edit_resource', methods=['POST'])
def edit_resource():
    if session.get('role') != 'admin':
        return "Unauthorized", 403

    resource_id = request.form['id']
    name = request.form['name']
    ap_count = request.form['ap_count']
    status = request.form['status']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE resources 
        SET name = %s, ap_count = %s, status = %s 
        WHERE id = %s
    """, (name, ap_count, status, resource_id))
    conn.commit()
    if session.get('role') == 'admin':
        subject = "Resource Edited"
        body = f"""
        Resource Name: {name}
        AP Count: {ap_count}
        Status: {status}
        Action: EDITED
        """
        send_email(session.get('username'), subject, body)

    # Send notification to all users who reserved this resource
    emails = get_emails_by_resource(resource_id)
    for email in emails:
        send_email(
            email,
            f"Resource Updated: {name}",
            f"The resource '{name}' has been updated.\nAPs: {ap_count}\nStatus: {status}"
        )

    conn.close()


    return redirect(url_for('inventory'))
@app.route('/permission', methods=['GET', 'POST'])
def permission():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))  # only admins allowed

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

@app.route('/delete_reservation/<int:id>')
def delete_reservation(id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Make sure the reservation belongs to the current user
    cursor.execute("SELECT * FROM reservations WHERE id = %s AND user_id = %s", (id, user_id))
    reservation = cursor.fetchone()

    if reservation:
        cursor.execute("DELETE FROM reservations WHERE id = %s", (id,))
        conn.commit()

    conn.close()
    return redirect(url_for('reserve'))



if __name__ == '__main__':
    app.run(debug=True)

