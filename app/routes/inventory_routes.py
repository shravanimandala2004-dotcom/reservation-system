from flask import Blueprint, render_template, request, redirect, url_for, session
from app.utils.db import get_db_connection
from .notification_routes import notify_user, get_emails_by_resource

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/inventory', methods=['GET', 'POST'])
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
                subject=f"Resource Updated: {name}"
                body=f"The resource '{name}' has been updated.\nAPs: {ap_count}\nStatus: {status}"
                notify_user(
                    to_email=email,
                    subject=subject,
                    email_body=body,
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
                notify_user(
                    to_email=session.get('username'),
                    subject=subject,
                    email_body=body,
                )
 

            # Optional: Send to all users if needed
            cursor.execute("SELECT username FROM users")
            all_users = cursor.fetchall()
            for user in all_users:
                notify_user(
                    to_email=user['username'],
                    subject=f"New Resource Added: {name}",
                    email_body=f"A new resource '{name}' with {ap_count} APs is now available.",
               )


    # Display inventory
    cursor.execute("SELECT * FROM resources")
    resources = cursor.fetchall()
    conn.close()
    return render_template('inventory.html', resources=resources, role=session.get('role'))

@inventory_bp.route('/delete_resource/<int:id>')
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
            print(emails) 
            # Notify each user
            for email in emails:
                notify_user(
                    to_email=email,
                    subject=f"Resource Deleted: {resource['name']}",
                    email_body=f"The resource '{resource['name']}' with {resource['ap_count']} APs has been deleted.",
                )

            cursor.execute("DELETE FROM reservations WHERE resource_id = %s", (id,))
            cursor.execute("DELETE FROM resources WHERE id = %s", (id,))
            conn.commit()
        conn.close()
    return redirect(url_for('inventory.inventory'))

@inventory_bp.route('/edit_resource', methods=['POST'])
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
        notify_user(
            to_email=session.get('username'),
            subject=subject,
            email_body=body,
        )

    # Send notification to all users who reserved this resource
    emails = get_emails_by_resource(resource_id)
    for email in emails:
        notify_user(
            to_email=email,
            subject=f"Resource Updated: {name}",
            email_body=f"The resource '{name}' has been updated.\nAPs: {ap_count}\nStatus: {status}",
        )

    conn.close()


    return redirect(url_for('inventory.inventory'))

@inventory_bp.route('/admin_page')
def admin_page():
    # Check if logged in
    if 'user_id' not in session:
        return redirect(url_for('inventory.login'))

    # Allow only admins
    if session.get('role') != 'admin':
        return "⛔ You are not authorized to view this page."

    return render_template('admin_page.html', role=session.get('role'))
