from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from flask_login import login_required, current_user
from app.utils.db import get_db_connection

from flask import Blueprint, render_template, request, redirect, url_for, session
from app.utils.db import get_db_connection
from werkzeug.security import generate_password_hash

contact_bp = Blueprint('contact', __name__)

@contact_bp.route('/', methods=['GET'])
def contacts():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM contacts")   # contacts table with id, email
    contacts = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('contact.html', contacts=contacts, role=session.get('role'))

@contact_bp.route('/add', methods=['POST'])
def add_contact():
    if session.get('role') == 'admin':   # only admins can add
        email = request.form.get('email')
        if email:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO contacts (email) VALUES (%s)", (email,))
            conn.commit()
            cursor.close()
            conn.close()
    return redirect(url_for('contact.contacts'))

@contact_bp.route('/delete/<int:contact_id>', methods=['POST'])
def delete_contact(contact_id):
    if session.get('role') == 'admin':   # only admins can delete
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contacts WHERE id = %s", (contact_id,))
        conn.commit()
        cursor.close()
        conn.close()
    return redirect(url_for('contact.contacts'))
