from flask import Blueprint, render_template, request, redirect, url_for, session
from app.utils.db import get_db_connection
from flask import jsonify
from ldap3 import Server, Connection, ALL, NTLM, SIMPLE
from dotenv import load_dotenv
import os
from flask import jsonify, session, request
from ldap3 import Server, Connection, ALL, SIMPLE

load_dotenv()

auth_bp = Blueprint('auth', __name__)

# LDAP Configuration
LDAP_SERVER = os.environ.get('LDAP_SERVER')
SERVICE_ACCOUNT_DN = os.environ.get('SERVICE_ACCOUNT_DN')
SERVICE_ACCOUNT_PASSWORD = os.environ.get('SERVICE_ACCOUNT_PASSWORD')

TME_GROUP_DN = 'CN=tme,OU=Groups,DC=commscope,DC=com'
SE_GROUP_DN = 'CN=se,OU=Groups,DC=commscope,DC=com'

@auth_bp.route('/')
def index():
    return render_template('index.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
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
            return redirect(url_for('details.details'))
        except Exception as e:
            return f"Signup failed: {str(e)}"
    
    return render_template('signup.html')

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
            attributes=["distinguishedName", "memberOf"]
        )

        if not service_conn.entries:
            return jsonify(status='error', message="❌ Invalid login credentials"), 401

        user_entry = service_conn.entries[0]
        user_dn = user_entry.distinguishedName.value
        groups = user_entry.memberOf.values if 'memberOf' in user_entry else []

        user_conn = Connection(server, user=user_dn, password=password, authentication=SIMPLE)
        if not user_conn.bind():
            return jsonify(status='error', message="❌ Invalid login credentials"), 401
        
        # if role == 'admin' and TME_GROUP_DN not in groups:
        #     return jsonify(status='error', message="❌ Invalid login credentials"), 401
        # elif role == 'user' and not any(group in groups for group in [TME_GROUP_DN, SE_GROUP_DN]):
        #     return jsonify(status='error', message="❌ Invalid login credentials"), 401

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s AND role=%s",
                       (username, role))
        user = cursor.fetchone()

        if user:
            session['user_id'] = user['id']     
        else:
            try:
                password ="**"
                cursor.execute("INSERT INTO users (username, password, role) VALUES ( %s, %s, %s)",
                            ( username, password, role))
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
        return jsonify(status='success', message="Login successful"), 200
    else:
        return redirect(url_for('auth.index'))