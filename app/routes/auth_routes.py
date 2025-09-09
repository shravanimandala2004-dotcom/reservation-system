from flask import Blueprint, render_template, request, redirect, url_for, session
from app.utils.db import get_db_connection

auth_bp = Blueprint('auth', __name__)

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
            return redirect(url_for('inventory.inventory'))
        else:
            return "❌ Invalid login credentials"
    else:
        return redirect(url_for('auth.index'))
    
@auth_bp.route('/user')
def user_dashboard():
    return render_template('user_dashboard.html')

@auth_bp.route('/admin')
def admin_dashboard():
    return render_template('admin_dashboard.html')