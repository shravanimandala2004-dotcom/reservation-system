from flask import Blueprint, render_template, request, redirect, url_for, session
from app.utils.db import get_db_connection
from flask import jsonify
from ldap3 import Server, Connection, ALL, NTLM, SIMPLE

auth_bp = Blueprint('auth', __name__)

# LDAP Configuration
LDAP_SERVER = 'ldap://your-ad-server.com'

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
    if request.method == 'POST':
        data=request.get_json()
        username =data.get('username')
        password =data.get('password')
        role =data.get('role')

        if not username or not password or not role:
            return jsonify(status='error',message="Missing username, password, or role.")

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
            return jsonify(status='success',message="Login successful"),200
            # return redirect(url_for('inventory.inventory'))
        else:
            return jsonify(status='error',message="❌ Invalid login credentials"),401
    else:
        return redirect(url_for('auth.index'))
    
    # LDAP code 
    # if request.method == 'POST':
    #     data = request.get_json()
    #     username = data.get('username')  
    #     password = data.get('password')
    #     role = data.get('role')

    #     if not username or not password or not role:
    #         return jsonify(status='error', message="Missing username, password, or role.")

    #     # Use email directly as the bind user
    #     server = Server(LDAP_SERVER, get_info=ALL)
    #     conn = Connection(server, user=username, password=password, authentication=SIMPLE)

    #     if conn.bind():
    #         session['username'] = username
    #         session['role'] = role
    #         return jsonify(status='success', message="Login successful"), 200
    #     else:
    #         return jsonify(status='error', message="❌ Invalid login credentials"), 401
    # else:
    #     return redirect(url_for('auth.index'))
    
@auth_bp.route('/user')
def user_dashboard():
    return render_template('user_dashboard.html')

@auth_bp.route('/admin')
def admin_dashboard():
    return render_template('admin_dashboard.html')