from flask import Blueprint, render_template, request, redirect, url_for, session
from app.utils.db import get_db_connection
from .notification_routes import notify_user, get_emails_by_resource
from flask import jsonify
import mysql 

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/inventory', methods=['GET', 'POST'])
def inventory():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST' and session.get('role') == 'admin':
        manufacturer = request.form['manufacturer']
        name = request.form['resource_name']
        ap_count = request.form['ap_count']
        status = request.form['status']
        link = request.form['link']
        controllers=request.form.getlist('controllers_list')
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
            cursor.execute("INSERT INTO resources (manufacturer_id,name, ap_count, status, link) VALUES (%s,%s, %s, %s, %s)",
                           (manufacturer,name, ap_count, status, link))
            conn.commit()
            print(controllers)
            if len(controllers)!=0:
                cursor.execute("Select id from resources where manufacturer_id=%s and name=%s and ap_count=%s and status=%s and link=%s",(manufacturer,name, ap_count, status, link))
                resource_id=cursor.fetchone()['id']
                for controller in controllers:
                    cursor.execute("insert into resource_controller_map (controller_id,resource_id) values (%s,%s)",(controller,resource_id))
                    conn.commit()


            # Notify all admins
            cursor.execute("SELECT username FROM users WHERE role = 'admin'")
            admin_users = cursor.fetchall()
            subject = "Resource Added"
            body = f"""
            Resource Name: {name}
            AP Count: {ap_count}
            Status: {status}
            Link: {link}
            Action: ADDED
            """
            for admin in admin_users:
                notify_user(
                    to_email=admin['username'],
                    subject=subject,
                    email_body=body,
                )
 

            # Optional: Send to all users if needed
            # cursor.execute("SELECT username FROM users")
            # all_users = cursor.fetchall()
            # for user in all_users:
            #     notify_user(
            #         to_email=user['username'],
            #         subject=f"New Resource Added: {name}",
            #         email_body=f"A new resource '{name}' with {ap_count} APs is now available.",
            #    )

    # Fetch manufacturers
    cursor.execute("SELECT distinct name,manufacturer_id as id from manufacturers")
    manufacturers =  cursor.fetchall()
    print("manufacturers:", manufacturers)

    # Display inventory
    # cursor.execute("SELECT * FROM resources")
    # resources = cursor.fetchall()
    conn.close()
    return render_template('inventory.html', role=session.get('role'),manufacturers=manufacturers)

@inventory_bp.route('/inventory/add_controller', methods=['POST'])
def add_controller():
    if session.get('role') != 'admin':
        return "Unauthorized", 403

    manufacturer = request.form['manufacturer']
    name = request.form['controller_name']
    status= request.form['status']

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO controllers (manufacturer_id, name) VALUES (%s, %s)",
                    (manufacturer, name))
        conn.commit()

        # Notify all admins
        cursor.execute("SELECT username FROM users WHERE role = 'admin'")
        admin_users = cursor.fetchall()
        print("admin_users:", admin_users)
        subject = "Controller Added"
        body = f"""
        Manufacturer ID: {manufacturer}
        Controller Name: {name}
        Action: ADDED
        """
        for admin in admin_users:
            notify_user(
                to_email=admin[0],
                subject=subject,
                email_body=body,
            )
    
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('inventory.inventory'))

@inventory_bp.route('/inventory/add_manufacturer', methods=['POST'])
def add_manufacturer():
    if session.get('role') != 'admin':
        return "Unauthorized", 403

    name = request.form['manufacturer_name']
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO manufacturers (name) VALUES (%s)", (name,))
        conn.commit()

        # Notify all admins
        cursor.execute("SELECT username FROM users WHERE role = 'admin'")
        admin_users = cursor.fetchall()
        subject = "Manufacturer Added"
        body = f"""
        Manufacturer Name: {name}
        Action: ADDED
        """
        for admin in admin_users:
            notify_user(
                to_email=admin[0],
                subject=subject,
                email_body=body,
            )
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('inventory.inventory'))

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

@inventory_bp.route('/get_controllers/<int:manufacturer_id>')
def get_controllers_by_manufacturer(manufacturer_id):
    if session.get('role') == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get controllers by manufacturer
        cursor.execute("SELECT * FROM controllers WHERE manufacturer_id = %s", (manufacturer_id,))
        controllers = cursor.fetchall()
        print(controllers)
        cursor.close()
        conn.close()
        return jsonify({'controllers':controllers})


@inventory_bp.route('/admin_page')
def admin_page():
    # Check if logged in
    if 'user_id' not in session:
        return redirect(url_for('inventory.login'))

    # Allow only admins
    if session.get('role') != 'admin':
        return "⛔ You are not authorized to view this page."
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Fetch current settings for display
    cursor.execute("SELECT max_reservations, max_days FROM permissions ")
    # settings = {row['key_name']: row['value'] for row in cursor.fetchall()}
    settings=cursor.fetchone()
    conn.close()
    print("settings:", settings)

    return render_template(
        'admin_page.html',
        role=session.get('role'),
        settings=settings
    )


@inventory_bp.route('/get_resources_by_manufacturer',methods=['GET'])
def get_resources_by_manufacturer():
    manufacturer = request.args.get('manufacturer')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT r.* from resources as r join manufacturers as m on r.manufacturer_id=m.manufacturer_id where m.name=%s",(manufacturer,))
    resources=cursor.fetchall()
    cursor.execute("""
        SELECT 
            distinct c.*, 
            CASE 
                WHEN r.controller_id IS NOT NULL THEN 'Reserved'
                ELSE 'Available'
            END AS reservation_status
        FROM controllers c
        JOIN manufacturers m ON c.manufacturer_id = m.manufacturer_id
        LEFT JOIN reservations r ON c.controller_id = r.controller_id
        WHERE m.name = %s;""",(manufacturer,)
        )
    controllers=cursor.fetchall()
    conn.close()
    return jsonify(resources,controllers)

@inventory_bp.route('/get_controllers_by_resource')
def get_controllers_by_resource():
    resource_id = request.args.get('resource_id')
    query = """
        SELECT c.controller_id, c.name
        FROM controllers c
        JOIN resource_controller_map rcm ON c.controller_id = rcm.controller_id
        WHERE rcm.resource_id = %s
    """
    conn = get_db_connection()
    cursor= conn.cursor(dictionary=True)
    cursor.execute(query, (resource_id,))
    controllers = cursor.fetchall()
    return jsonify(controllers)


@inventory_bp.route('/delete_controller/<int:id>')
def delete_controller(id):
    if session.get('role') == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get controller details first
        cursor.execute("SELECT * FROM controllers WHERE controller_id = %s", (id,))
        controller = cursor.fetchone()

        if controller:
            # Notify all admins
            cursor.execute("SELECT username FROM users WHERE role = 'admin'")
            admin_users = cursor.fetchall()
            subject = "Controller Deleted"
            body = f"""
            Controller Name: {controller['name']}
            Action: DELETED
            """
            for admin in admin_users:
                notify_user(
                    to_email=admin['username'],
                    subject=subject,
                    email_body=body,
                )

            cursor.execute("DELETE FROM reservations WHERE controller_id = %s", (id,))
            cursor.execute("DELETE FROM resource_controller_map WHERE controller_id = %s", (id,))
            cursor.execute("DELETE FROM controllers WHERE controller_id = %s", (id,))
            conn.commit()
        conn.close()
    return redirect(url_for('inventory.inventory'))

@inventory_bp.route('/edit_controller', methods=['POST'])
def edit_controller():
    if session.get('role') != 'admin':
        return "Unauthorized", 403

    controller_id = request.form['id']
    name = request.form['name']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE controllers 
        SET name = %s
        WHERE controller_id = %s
    """, (name, controller_id))
    conn.commit()

    # Notify all admins
    cursor.execute("SELECT username FROM users WHERE role = 'admin'")
    admin_users = cursor.fetchall()
    subject = "Controller Edited"
    body = f"""
    Controller Name: {name}
    Action: EDITED
    """
    for admin in admin_users:
        notify_user(
            to_email=admin[0],
            subject=subject,
            email_body=body,
        )

    conn.close()
    return redirect(url_for('inventory.inventory'))