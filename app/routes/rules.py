import mysql.connector
from flask import Blueprint, render_template, request, redirect, url_for,jsonify
from flask_login import login_required, current_user
from app.models import db, Rule
from flask import session
from app.utils.db import get_db_connection

rules_bp = Blueprint('rules', __name__, url_prefix='/rules')

# render rules page with rules from database and role from session for conditional rendering of admin features
@rules_bp.route('/', methods=['GET'])
def rules():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM rules")
    rules = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('rules.html', rules=rules ,role=session.get('role'))

# add new rule 
@rules_bp.route('/add', methods=['POST'])
def add_rule():
    new_rule = request.form.get('new_rule')
    if new_rule:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO rules (content) VALUES (%s)", (new_rule,))
        conn.commit()
        cursor.close()
        conn.close()
    return redirect(url_for('rules.rules'))

# delete existing rule 
@rules_bp.route('/delete/<int:rule_id>', methods=['POST'])
def delete_rule(rule_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rules WHERE id = %s", (rule_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('rules.rules'))

# render accept_rules page for users to accept rules before accessing inventory page.
@rules_bp.route('/accept_rules')
def accept_rules():
    # print("Accept Rules route called")
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM rules")
        rules = cursor.fetchall()
        # print("rules:", rules) 
        return render_template('accept_rules.html', rules=rules)
    except Exception as e:
        return jsonify({'message':"Error fetching rules: {str(e)}",'status':"error"}),500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
# redirect to inventory page after accepting rules.
@rules_bp.route('/accept_rules', methods=['POST'])
def accept_rules_post():
    # Logic to record acceptance of rules can be added here
    return redirect(url_for('inventory.inventory'))