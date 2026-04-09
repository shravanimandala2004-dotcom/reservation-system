from flask import Blueprint, render_template, request, redirect, url_for, session
from app.utils.db import get_db_connection
from flask import jsonify
from ldap3 import Server, Connection, ALL, NTLM, SIMPLE
from dotenv import load_dotenv
import os
from flask import jsonify, session, request
from ldap3 import Server, Connection, ALL, SIMPLE
import uuid
from .notification_routes import notify_user
import datetime
 
load_dotenv()
 
auth_bp = Blueprint('auth', __name__)

from ldap3 import BASE

def extract_cn(dn):
    """Extracts CN from a distinguished name"""
    for part in dn.split(','):
        if part.startswith('CN='):
            return part.replace('CN=', '')
    return None

def is_admin_department(user_department):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT 1 FROM admin_departments WHERE department_name = %s",
        (user_department,)
    )
    result = cursor.fetchone()

    conn.close()

    return result is not None

# LDAP Configuration
LDAP_SERVER = os.environ.get('LDAP_SERVER')
SERVICE_ACCOUNT_DN = os.environ.get('SERVICE_ACCOUNT_DN')
SERVICE_ACCOUNT_PASSWORD = os.environ.get('SERVICE_ACCOUNT_PASSWORD')
 
ADMIN_GROUPS = {
    "#PLM-PMM-TME ALL"
}

ADMIN_GROUPS = {
    "#PLM-PMM-TME ALL",
}

USER_GROUPS = {
    "#PLM-PMM-TME ALL",
    "SE"
}
 
ADMIN_USERS = [
    "shravani.mandala@ruckusnetworks.com",
    "alvita.silva@ruckusnetworks.com"
]

@auth_bp.route('/')
def index():
    return render_template('index.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = "**"  # placeholder
        role = request.form['role']
        access_type = request.form['access_type']

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            status = 'pending' if access_type == 'temporary' else 'active'
            if access_type == "temporary":
                expires_at = datetime.datetime.now() + datetime.timedelta(hours=24)
            else:
                expires_at = None

            # Insert user with pending status
            cursor.execute(
                "INSERT INTO users (username, password, role, access_type, status, expires_at) VALUES (%s, %s, %s, %s, %s,%s)",
                (username, password, role, access_type, status, expires_at)
            )
            conn.commit()
            user_id = cursor.lastrowid

            # set status to pending for temporary users until they confirm via email
            if access_type == 'temporary':
                # Generate token
                token = str(uuid.uuid4())
                cursor.execute("INSERT INTO confirmation_tokens (user_id, token) VALUES (%s, %s)", (user_id, token))
                conn.commit()
                conn.close()

                confirm_url = url_for('auth.confirm', token=token, _external=True)
                subject = "Confirm Your Account"
                body = f"Click the link to activate your account: {confirm_url}"

                # use notification_routes.py's notify_user function to send email
                notify_user(username, subject, body)

            return redirect(url_for('details.details'))
        except Exception as e:
             return f"Signup failed: {str(e)}"

    return render_template('signup.html')

@auth_bp.route('/confirm')
def confirm():
    token = request.args.get('token')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM confirmation_tokens WHERE token=%s", (token,))
    result = cursor.fetchone()

    if result:
        user_id = result[0]
        # Set expiration only now
        expires_at = datetime.datetime.now() + datetime.timedelta(hours=24)
        cursor.execute("UPDATE users SET status='active', expires_at=%s WHERE id=%s", (expires_at, user_id))
        cursor.execute("DELETE FROM confirmation_tokens WHERE token=%s", (token,))
        conn.commit()
        conn.close()
        return "Your account is now active for 24 hours."
    else:
        return "Invalid or expired token."
 
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # if request.method == 'POST':
    #     data=request.get_json()
    #     username =data.get('username')
    #     password =data.get('password')
    #     role =data.get('role')
 
    #     if not username or not password or not role:
    #         return jsonify(status='error',message="Missing username, password, or role.")
 
    #     conn = get_db_connection()
    #     cursor = conn.cursor(dictionary=True)
    #     cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s AND role=%s",
    #                    (username, password, role))
    #     user = cursor.fetchone()
    #     conn.close()
 
    #     if user:
    #         session['user_id'] = user['id']    
    #         session['username'] = username
    #         session['role'] = role
    #         return jsonify(status='success',message="Login successful"),200
    #         # return redirect(url_for('inventory.inventory'))
    #     else:
    #         return jsonify(status='error',message="❌ Invalid login credentials"),401
    # else:
    #     return redirect(url_for('auth.index'))
   
 
    if request.method == 'POST':
        data=request.get_json()
        username =data.get('username')
        password =data.get('password')
        role =data.get('role')
 
        if not username or not password or not role:
            return jsonify(status='error',message="Missing username, password, or role.")
        
 
        server = Server(LDAP_SERVER, get_info=ALL)
        service_conn = Connection(server, user=SERVICE_ACCOUNT_DN,
                                password=SERVICE_ACCOUNT_PASSWORD,
                                authentication=SIMPLE, auto_bind=True)
 
        service_conn.search(
            search_base="DC=vistancenetworks,DC=com",
            search_filter=f"(mail={username})",
            attributes=["distinguishedName", "memberOf", "department","employeeID","company","title"]
        )
 
        if not service_conn.entries:
            return jsonify(status='error', message="❌ Invalid login credentials"), 401
 
        user_entry = service_conn.entries[0]
        user_dn = user_entry.distinguishedName.value
        groups = user_entry.memberOf.values if 'memberOf' in user_entry else []
        group_cns = [extract_cn(dn) for dn in groups]

        # print("Direct groups (DNs):", groups)
        # print("Direct groups (CNs):", group_cns)
        # print("")

        # service_conn.search(
        #     search_base="DC=vistancenetworks,DC=com",
        #     search_filter=f"(mail={username})",
        #     attributes="*"
        # )        
        # entry = service_conn.entries[0]
        # print(entry)

        # verify user credentials 
        user_conn = Connection(server, user=user_dn, password=password, authentication=SIMPLE)
        if not user_conn.bind():
            return jsonify(status='error', message="❌ Invalid login credentials"), 401
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s AND role=%s",
                       (username, role))
        user = cursor.fetchone()
        rules_accepted = False

        # check if user exists in database 
        if user:
            
            # Temporary user check
            if user['access_type'] == 'temporary':
                status=user['status']
                expires_at = user['expires_at']
                if status != 'active':
                    return jsonify(
                        status='error', 
                        message="❌ Your account is not active. Please check your email to activate."
                        ), 403
                
                if expires_at and expires_at < datetime.datetime.now():
                    # Expired → delete account
                    # cursor.execute("DELETE FROM users WHERE id=%s", (user['id'],))
                    conn.commit()
                    conn.close()
                    return jsonify(
                        status='error', 
                        message="❌ Your account has expired."
                        ), 403
            
                # session['user_id'] = user['id']
                # session['username'] = username
                # session['role'] = role        
                # return jsonify(status='success', message="Login successful", rules_accepted=rules_accepted), 200
            elif user['access_type'] == 'ldap':
                user_department = user_entry.department.value if 'department' in user_entry else None
                if role == "admin":
                    if not is_admin_department(user_department):
                        return jsonify(
                            status="error",
                            message="❌ Access denied: admin group membership required"
                        ), 403
                elif role == "user":
                    if not USER_GROUPS.intersection(group_cns):
                        return jsonify(
                            status="error",
                            message="❌ Access denied: user group membership required"
                        ), 403
        else:        
            # ---- ROLE AUTHORIZATION ----
            
            user_department = user_entry.department.value if 'department' in user_entry else None
            if role == "admin":
                if not is_admin_department(user_department):
                    return jsonify(
                        status="error",
                        message="❌ Access denied: admin group membership required"
                    ), 403
            elif role == "user":
                if not USER_GROUPS.intersection(group_cns):
                    return jsonify(
                        status="error",
                        message="❌ Access denied: user group membership required"
                    ), 403
            
        
            # ---- ROLE AUTHORIZATION ----
    
            # if role == "admin":
            #  if username.lower() not in {u.lower() for u in ADMIN_USERS}:
            #    return jsonify(
            #     status="error",
            #     message="❌ Access denied: You are not authorized as admin"
            # ), 403
         
 
        if user:
            session['user_id'] = user['id']
            rules_accepted = True    
        else:
            try:
                password ="**"
                cursor.execute("INSERT INTO users (username, password, role, access_type) VALUES ( %s, %s, %s, %s)",
                            ( username, password, role, 'ldap'))
                user_id = cursor.lastrowid
                session['user_id'] = user_id
                print("New user created with ID:", user_id)
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"Error creating user: {str(e)}")
                return jsonify(status='error', message="❌ Something went wrong"), 401
 
        session['username'] = username
        session['role'] = role        
        return jsonify(status='success', message="Login successful", rules_accepted=rules_accepted), 200
    else:
        return redirect(url_for('auth.index'))
