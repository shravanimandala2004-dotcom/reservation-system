
import mysql.connector
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from app.models import db, Rule
from flask import session
from app.utils.db import get_db_connection

rules_bp = Blueprint('rules', __name__, url_prefix='/rules')

# @rules_bp.route('/')
# def rules():
#     return render_template('rules.html', role=session.get('role'))

@rules_bp.route('/', methods=['GET'])
def rules():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM rules")
    rules = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('rules.html', rules=rules ,role=session.get('role'))

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

@rules_bp.route('/delete/<int:rule_id>', methods=['POST'])
def delete_rule(rule_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rules WHERE id = %s", (rule_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('rules.rules'))