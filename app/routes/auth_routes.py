from flask import Blueprint, render_template, request, redirect, url_for, session
from app.utils.db import get_db_connection
from flask import jsonify
from ldap3 import Server, Connection, ALL, SIMPLE
from dotenv import load_dotenv
import os
from flask import jsonify, session, request
from ldap3 import Server, Connection, ALL, SIMPLE
import uuid
from .notification_routes import notify_user
import datetime
from datetime import timezone
# from ldap3 import BASE
 
load_dotenv()
 
auth_bp = Blueprint('auth', __name__)

# helper to extract CN from DN for group membership checks
# def extract_cn(dn):
#     """Extracts CN from a distinguished name"""
#     for part in dn.split(','):
#         if part.startswith('CN='):
#             return part.replace('CN=', '')
#     return None

# find out if user belongs to a valid department for access
def is_user_department(user_department):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT 1 FROM user_departments WHERE department_name = %s",
        (user_department,)
    )
    result = cursor.fetchone()

    conn.close()

    return result is not None

# LDAP Configuration
LDAP_SERVER = os.environ.get('LDAP_SERVER')
SERVICE_ACCOUNT_DN = os.environ.get('SERVICE_ACCOUNT_DN')
SERVICE_ACCOUNT_PASSWORD = os.environ.get('SERVICE_ACCOUNT_PASSWORD')

# ADMIN_GROUPS = {
#     "#PLM-PMM-TME ALL",
# }
# USER_GROUPS = {
#     "#PLM-PMM-TME ALL",
#     "SE"
# }

@auth_bp.route('/')
def index():
    return render_template('index.html')

# admin route to give individual users temporary or permanent access or to add new admins
@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data=request.get_json()
        username =data.get('username')
        password = "**"  # placeholder
        role = data.get('role')
        access_type = data.get('access_type')

        if not username or not role or not access_type:
            return jsonify(status="error", message="Missing username or role or access_type")

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("Select * from users where username=%s and role=%s", (username,role))
            user=cursor.fetchone()

            now=datetime.datetime.now(timezone.utc)

            status = 'pending' if access_type == 'temporary' else 'active'
            if access_type == "temporary":
                expires_at = now + datetime.timedelta(hours=24)
            else:
                expires_at = None

            if user:
                # check if existing user is permanent or temporary and not expired                
                if not user['expires_at'] or (user['expires_at'] and user['expires_at']>now):
                    return jsonify(status="error",message="Account already present."), 400
                
                # if user exists but is expired, give new temporary access and update expiry
                cursor.execute("UPDATE users SET expires_at=%s, status=%s WHERE id=%s",
                            (expires_at,status, user['id']))
                conn.commit()
                user_id=user['id']
            else:                
                # Insert new user
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
                subject = "Action Required – Activate Your Temporary Access to the Reservation Portal"
                body = f"""Hello,

A temporary account has been created for you by an administrator of the Network Devices Reservation Portal to grant you short‑term access.
To activate your account, please click the link below:

Activate Your Account:
{confirm_url}

Once activated, your temporary access will be valid for 24 hours from the time of activation.
Important Notes:

- You must activate your account using the link above before you can log in.
- If you do not activate the account, access will remain inactive.
- This temporary access is intended for limited‑time usage only.

If you did not expect this email or have any questions, please contact the portal administrator for assistance.
Best regards,
Reservation Portal Team"""

                #send email
                notify_user(username, subject, body)

            # return redirect(url_for('details.details'))
            return jsonify(status="success", message="Successful"), 200
        except Exception as e:
             return jsonify(status="error", message=f"Signup failed: {str(e)}"), 400
        finally:
            conn.close()
        
    else:
        return render_template('signup.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data=request.get_json()
        username =data.get('username')

        if not username:
            return jsonify(status='error', message='Enter email')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s AND role=%s",
                       (username, 'user'))
        user = cursor.fetchone()

        now = datetime.datetime.now(timezone.utc)

        # check if account already exists 
        if user:
            if user['access_type'] == 'temporary':
                expires_at = user['expires_at']
                expires_at = expires_at.replace(tzinfo=timezone.utc) if expires_at else None
                if user['status'] != 'active':
                    return jsonify(
                        status='error', 
                        message="❌ Your account is not active. Please check your email to activate."
                        ), 403
                
                if expires_at and expires_at < now:
                    return jsonify(
                        status='error', 
                        message="❌ Your account has expired."
                        ), 403
            return jsonify(
                status='error',
                message='You already have an active account'
            ), 403
        
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
            return jsonify(status='error', message="❌ Invalid email"), 401
 
        user_entry = service_conn.entries[0]

        if not is_user_department(user_entry.department.value):
            return jsonify(status='error', message='❌ Registration failed. User does not belong to valid department. Contact administrator for assistance.'), 401

        # Insert new permanent user
        cursor.execute(
            "INSERT INTO users (username, role, password, status,access_type) "
            "VALUES (%s, %s, %s,'active','permanent')",
            (username, 'user', "**")
        )
        conn.commit()

        notify_user(
            username,
            "Your Resource Scheduler Access",
            f"""Hello,

Your access to the Reservation Portal has been activated!

📧 Please log in using:
• Email: {username}\n
• Password: (the same password you use for your email account)

Best regards,
Resource Scheduler Team"""
        )
        return jsonify(status='success',message='Registration successful.'), 200
    else:
        return render_template('register.html')

# activating temporary access via email confirmation link 
@auth_bp.route('/confirm')
def confirm():
    token = request.args.get('token')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM confirmation_tokens WHERE token=%s", (token,))
        result = cursor.fetchone()

        if result:
            user_id = result[0]
            # Set expiration only now
            expires_at = datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=24)
            cursor.execute("UPDATE users SET status='active', expires_at=%s WHERE id=%s", (expires_at, user_id))
            cursor.execute("DELETE FROM confirmation_tokens WHERE token=%s", (token,))
            conn.commit()
            return "Your account is now active for 24 hours."
        else:
            return "Invalid or expired token."
    except Exception as e:
        return f"An error occurred: {str(e)}"
    finally:
        conn.close()
 
# login without temporary user check  
# @auth_bp.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         data=request.get_json()
#         username =data.get('username')
#         password =data.get('password')
#         role =data.get('role')
 
#         if not username or not password or not role:
#             return jsonify(status='error',message="Missing username, password, or role.")
        
 
#         server = Server(LDAP_SERVER, get_info=ALL)
#         service_conn = Connection(server, user=SERVICE_ACCOUNT_DN,
#                                 password=SERVICE_ACCOUNT_PASSWORD,
#                                 authentication=SIMPLE, auto_bind=True)
 
#         service_conn.search(
#             search_base="DC=vistancenetworks,DC=com",
#             search_filter=f"(mail={username})",
#             attributes=["distinguishedName", "memberOf", "department","employeeID","company","title"]
#         )
 
#         if not service_conn.entries:
#             return jsonify(status='error', message="❌ Invalid login credentials"), 401
 
#         user_entry = service_conn.entries[0]
#         user_dn = user_entry.distinguishedName.value
#         groups = user_entry.memberOf.values if 'memberOf' in user_entry else []
#         group_cns = [extract_cn(dn) for dn in groups]

#         # print("Direct groups (DNs):", groups)
#         # print("Direct groups (CNs):", group_cns)
#         # print("")

#         # service_conn.search(
#         #     search_base="DC=vistancenetworks,DC=com",
#         #     search_filter=f"(mail={username})",
#         #     attributes="*"
#         # )        
#         # entry = service_conn.entries[0]
#         # print(entry)
        
#         conn = get_db_connection()
#         cursor = conn.cursor(dictionary=True)
#         cursor.execute("SELECT * FROM users WHERE username=%s AND role=%s",
#                        (username, role))
#         user = cursor.fetchone()
#         rules_accepted = False

#         # check if user exists in database 
#         if user:            
#             # verify user credentials 
#             user_conn = Connection(server, user=user_dn, password=password, authentication=SIMPLE)
#             if not user_conn.bind():
#                 return jsonify(status='error', message="❌ Invalid login credentials"), 401
           
#             # ---- ROLE AUTHORIZATION ----
            
#             user_department = user_entry.department.value if 'department' in user_entry else None
#             if role == "admin":
#                 rules_accepted=True                
#                 if user['role']!='admin':
#                     return jsonify(
#                         status="error",
#                         message="❌ Access denied: admin group membership required"
#                     ), 403
#             elif role == "user":
#                 if not is_user_department(user_department):
#                     return jsonify(
#                         status="error",
#                         message="❌ Access denied: user group membership required"
#                     ), 403
                
#             session['user_id'] = user['id']
#             session['username'] = username
#             session['role'] = role        
#             return jsonify(status='success', message="Login successful", rules_accepted=rules_accepted), 200
                
#         else:
#             return jsonify(status='error', message="❌ Please register for access"), 401
         
 
#     else:
#         return redirect(url_for('auth.index'))
    
# login route with temporary user check and expiry handling
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
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
        # group_cns = [extract_cn(dn) for dn in groups]

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
        # check if user exists in database for the given role 
        cursor.execute("SELECT * FROM users WHERE username=%s AND role=%s",
                       (username, role))
        user = cursor.fetchone()

        if role == "admin":
            rules_accepted=True
        else:
            rules_accepted = False

        # check if user exists in database 
        if user:            
            # Temporary user check
            if user['access_type'] == 'temporary':
                status=user['status']
                expires_at = user['expires_at']
                expires_at = expires_at.replace(tzinfo=timezone.utc) if expires_at else None
                if status != 'active':
                    return jsonify(
                        status='error', 
                        message="❌ Your account is not active. Please check your email to activate."
                        ), 403
                
                if expires_at and expires_at < datetime.datetime.now(timezone.utc):
                    # Expired → delete account
                    # cursor.execute("DELETE FROM users WHERE id=%s", (user['id'],))
                    # conn.commit()
                    # conn.close()
                    return jsonify(
                        status='error', 
                        message="❌ Your account has expired."
                        ), 403
            
            # else:
            #     user_department = user_entry.department.value if 'department' in user_entry else None
            #     if role == "admin":
            #         rules_accepted=True
            #         if user['role']!='admin':
            #             return jsonify(
            #                 status="error",
            #                 message="❌ Access denied: admin group membership required"
            #             ), 403
            #     elif role == "user":
            #         user_department = user_entry.department.value if 'department' in user_entry else None
            #         if user['role']!='user':
            #             return jsonify(
            #                 status="error",
            #                 message="❌ Access denied: user group membership required"
            #             ), 403
        else:
            return jsonify(status='error', message="❌ Please register for access"), 401

        session['user_id'] = user['id']
        session['username'] = username
        session['role'] = role        
        return jsonify(status='success', message="Login successful", rules_accepted=rules_accepted), 200
    else:
        return redirect(url_for('auth.index'))