from flask import Blueprint, render_template, request, redirect, url_for, session
from app.utils.db import get_db_connection
from .notification_routes import notify_user, get_emails_by_resource
from flask import jsonify
import mysql 
from .permission_routes import get_setting
from datetime import datetime, timedelta

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/inventory', methods=['GET', 'POST'])
def inventory():
    if 'user_id' not in session:
        return redirect(url_for('auth.index'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # if request.method == 'POST' and session.get('role') == 'admin':
    #     manufacturer = request.form['manufacturer']
    #     name = request.form['resource_name']
    #     ap_count = request.form['ap_count']
    #     status = request.form['status']
    #     link = request.form['link']
    #     controllers=request.form.getlist('controllers_list')
    #     action_type = request.form.get('action_type', 'add')  # from form hidden field

    #     if action_type == 'edit':
    #         resource_id = request.form['resource_id']
    #         cursor.execute("UPDATE resources SET name=%s, ap_count=%s, status=%s, link=%s WHERE id=%s",
    #                        (name, ap_count, status, link, resource_id))
    #         conn.commit()

            
    #         emails = get_emails_by_resource(resource_id)
    #         for email in emails:
    #             subject=f"Resource Updated: {name}"
    #             body=f"The resource '{name}' has been updated.\nAPs: {ap_count}\nStatus: {status}"
    #             notify_user(
    #                 to_email=email,
    #                 subject=subject,
    #                 email_body=body,
    #             )

    #     else:  # Add new resource
    #         cursor.execute("INSERT INTO resources (manufacturer_id,name, ap_count, status, link) VALUES (%s,%s, %s, %s, %s)",
    #                        (manufacturer,name, ap_count, status, link))
    #         conn.commit()
    #         print(controllers)
    #         if len(controllers)!=0:
    #             cursor.execute("Select id from resources where manufacturer_id=%s and name=%s and ap_count=%s and status=%s and link=%s",(manufacturer,name, ap_count, status, link))
    #             resource_id=cursor.fetchone()['id']
    #             for controller in controllers:
    #                 cursor.execute("insert into resource_controller_map (controller_id,resource_id) values (%s,%s)",(controller,resource_id))
    #                 conn.commit()


    #         # Notify all admins
    #         cursor.execute("SELECT username FROM users WHERE role = 'admin'")
    #         admin_users = cursor.fetchall()
    #         subject = "Resource Added"
    #         body = f"""
    #         Resource Name: {name}
    #         AP Count: {ap_count}
    #         Status: {status}
    #         Link: {link}
    #         Action: ADDED
    #         """
    #         for admin in admin_users:
    #             notify_user(
    #                 to_email=admin['username'],
    #                 subject=subject,
    #                 email_body=body,
    #             )

    # Fetch manufacturers
    cursor.execute("SELECT distinct name,manufacturer_id as id from manufacturers")
    manufacturers =  cursor.fetchall()
    print("manufacturers:", manufacturers)

    # Fetch active reservations
    cursor.execute("""
        SELECT r.*, res.model_name AS resource_name, c.name AS controller_name
        FROM ap_reservations r
        LEFT JOIN ap res ON r.ap_id = res.ap_id
        LEFT JOIN controllers c ON r.controller_id = c.controller_id
        WHERE r.user_id = %s AND r.end_datetime >= NOW()
    """, (user_id,))
    active_reservations = cursor.fetchall()
    
    for r in active_reservations:
        r['start_datetime_formatted'] = r['start_datetime'].strftime("%b %d, %Y %H:%M")
        r['end_datetime_formatted'] = r['end_datetime'].strftime("%b %d, %Y %H:%M")

    preBooking=get_setting('max_preBooking',4)
    maxDays=get_setting('max_days',2)
    now=datetime.now()
    max_date = now + timedelta(days=preBooking)
    min_str = now.strftime('%Y-%m-%dT%H:%M')
    max_str = max_date.strftime('%Y-%m-%dT%H:%M')

    # Display inventory
    # cursor.execute("SELECT * FROM resources")
    # resources = cursor.fetchall()
    conn.close()
    return render_template('inventory.html', role=session.get('role'),manufacturers=manufacturers,active_reservations=active_reservations,min_str=min_str,max_str=max_str,preBooking=preBooking,maxDays=maxDays)

@inventory_bp.route('/add_controller', methods=['POST'])
def add_controller():
    if session.get('role') != 'admin':
        return "Unauthorized", 403

    data=request.get_json()
    manufacturer = data.get('manu_id')
    name = data.get('controller_name')
    url=data.get('url')
    print("url:",url)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO controllers (manufacturer_id, name,url) VALUES (%s, %s, %s)",
                    (manufacturer, name, url))
        conn.commit()

        return jsonify({
            "message": "Controller successfully added",
        }), 201

        # Notify all admins
        # cursor.execute("SELECT username FROM users WHERE role = 'admin'")
        # admin_users = cursor.fetchall()
        # print("admin_users:", admin_users)
        # subject = "Controller Added"
        # body = f"""
        # Manufacturer ID: {manufacturer}
        # Controller Name: {name}
        # Action: ADDED
        # """
        # for admin in admin_users:
        #     notify_user(
        #         to_email=admin[0],
        #         subject=subject,
        #         email_body=body,
        #     )
    
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()

@inventory_bp.route('/inventory/add_manufacturer', methods=['POST'])
def add_manufacturer():
    if session.get('role') != 'admin':
        return "Unauthorized", 403

    data=request.get_json()
    name = data.get('manufacturer_name')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO manufacturers (name) VALUES (%s)", (name,))
        conn.commit()
        cursor.execute("select * from manufacturers")
        manufacturers=cursor.fetchall()

        # Notify all admins
        # cursor.execute("SELECT username FROM users WHERE role = 'admin'")
        # admin_users = cursor.fetchall()
        # subject = "Manufacturer Added"
        # body = f"""
        # Manufacturer Name: {name}
        # Action: ADDED
        # """
        # for admin in admin_users:
        #     notify_user(
        #         to_email=admin[0],
        #         subject=subject,
        #         email_body=body,
        #     )
        return jsonify(manufacturers)
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500
    finally:
        cursor.close()
        conn.close()

# @inventory_bp.route('/delete_resource/<int:id>')
# def delete_resource(id):
#     if session.get('role') == 'admin':
#         conn = get_db_connection()
#         cursor = conn.cursor(dictionary=True)

#         # Get resource details first
#         cursor.execute("SELECT * FROM resources WHERE id = %s", (id,))
#         resource = cursor.fetchone()

#         if resource:
#             # Get all user emails for this resource
#             emails = get_emails_by_resource(id)
#             print(emails) 
#             # Notify each user
#             for email in emails:
#                 notify_user(
#                     to_email=email,
#                     subject=f"Resource Deleted: {resource['name']}",
#                     email_body=f"The resource '{resource['name']}' with {resource['ap_count']} APs has been deleted.",
#                 )

#             cursor.execute("DELETE FROM reservations WHERE resource_id = %s", (id,))
#             cursor.execute("DELETE FROM resources WHERE id = %s", (id,))
#             conn.commit()
#         conn.close()
#     return redirect(url_for('inventory.inventory'))

# @inventory_bp.route('/edit_resource', methods=['POST'])
# def edit_resource():
#     if session.get('role') != 'admin':
#         return "Unauthorized", 403

#     resource_id = request.form['id']
#     name = request.form['name']
#     ap_count = request.form['ap_count']
#     status = request.form['status']

#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("""
#         UPDATE resources 
#         SET name = %s, ap_count = %s, status = %s 
#         WHERE id = %s
#     """, (name, ap_count, status, resource_id))
#     conn.commit()
#     if session.get('role') == 'admin':
#         subject = "Resource Edited"
#         body = f"""
#         Resource Name: {name}
#         AP Count: {ap_count}
#         Status: {status}
#         Action: EDITED
#         """
#         notify_user(
#             to_email=session.get('username'),
#             subject=subject,
#             email_body=body,
#         )

#     # Send notification to all users who reserved this resource
#     emails = get_emails_by_resource(resource_id)
#     for email in emails:
#         notify_user(
#             to_email=email,
#             subject=f"Resource Updated: {name}",
#             email_body=f"The resource '{name}' has been updated.\nAPs: {ap_count}\nStatus: {status}",
#         )

#     conn.close()
#     return redirect(url_for('inventory.inventory'))

@inventory_bp.route('/get_controllers_by_manufacturer_id')
def get_controllers_by_manufacturer_id():
    if session.get('role') == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        manufacturer_id=request.args.get('manufacturer_id')

        # Get controllers by manufacturer
        cursor.execute("SELECT * FROM controllers WHERE manufacturer_id = %s", (manufacturer_id,))
        controllers = cursor.fetchall()
        print(controllers)
        cursor.close()
        conn.close()
        return jsonify(controllers)


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
    cursor.execute("SELECT max_reservations, max_days,max_preBooking FROM permissions ")
    # settings = {row['key_name']: row['value'] for row in cursor.fetchall()}
    settings=cursor.fetchone()
    conn.close()
    print("settings:", settings)

    return render_template(
        'admin_page.html',
        role=session.get('role'),
        settings=settings
    )


# @inventory_bp.route('/get_resources_by_manufacturer',methods=['GET'])
# def get_resources_by_manufacturer():
#     manufacturer = request.args.get('manufacturer')
#     conn = get_db_connection()
#     cursor = conn.cursor(dictionary=True)
#     cursor.execute("SELECT r.* from resources as r join manufacturers as m on r.manufacturer_id=m.manufacturer_id where m.name=%s",(manufacturer,))
#     resources=cursor.fetchall()
#     cursor.execute("""
#         SELECT 
#             distinct c.*, 
#             CASE 
#                 WHEN r.controller_id IS NOT NULL THEN 'Reserved'
#                 ELSE 'Available'
#             END AS reservation_status
#         FROM controllers c
#         JOIN manufacturers m ON c.manufacturer_id = m.manufacturer_id
#         LEFT JOIN reservations r ON c.controller_id = r.controller_id
#         WHERE m.name = %s;""",(manufacturer,)
#         )
#     controllers=cursor.fetchall()
#     conn.close()
#     return jsonify(resources,controllers)

@inventory_bp.route('/delete_controller',methods=['POST'])
def delete_controller():
    if session.get('role') == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        data=request.get_json()
        id=data.get('controller_id')

        # Get controller details first
        cursor.execute("SELECT * FROM controllers WHERE controller_id = %s", (id,))
        controller = cursor.fetchone()

        if controller:
            # Notify all admins
            # cursor.execute("SELECT username FROM users WHERE role = 'admin'")
            # admin_users = cursor.fetchall()
            # subject = "Controller Deleted"
            # body = f"""
            # Controller Name: {controller['name']}
            # Action: DELETED
            # """
            # for admin in admin_users:
            #     notify_user(
            #         to_email=admin['username'],
            #         subject=subject,
            #         email_body=body,
            #     )

            cursor.execute("DELETE FROM ap_reservations WHERE controller_id = %s", (id,))
            cursor.execute("DELETE FROM ap_controller_map WHERE controller_id = %s", (id,))
            cursor.execute("DELETE FROM controllers WHERE controller_id = %s", (id,))
            conn.commit()
        conn.close()
        return jsonify({
            "message": "Controller successfully deleted",
        }), 201
    return jsonify({
            "message": "Some error occurred",
        }), 500

@inventory_bp.route('/edit_controller', methods=['POST'])
def edit_controller():
    if session.get('role') != 'admin':
        return "Unauthorized", 403

    data=request.get_json()
    controller_id = data.get('controller_id')
    name = data.get('controller_name')
    new_url=data.get('new_url')

    conn = get_db_connection()
    cursor = conn.cursor()
    if name != "":
        cursor.execute("""
            UPDATE controllers 
            SET name = %s, url=%s
            WHERE controller_id = %s
        """, (name,new_url, controller_id))
        conn.commit()
    else:
        cursor.execute("""
            UPDATE controllers 
            SET url=%s
            WHERE controller_id = %s
        """, (new_url, controller_id))
        conn.commit()

    # Notify all admins
    # cursor.execute("SELECT username FROM users WHERE role = 'admin'")
    # admin_users = cursor.fetchall()
    # subject = "Controller Edited"
    # body = f"""
    # Controller Name: {name}
    # Action: EDITED
    # """
    # for admin in admin_users:
    #     notify_user(
    #         to_email=admin[0],
    #         subject=subject,
    #         email_body=body,
    #     )

    conn.close()
    return jsonify({
            "message": "Controller successfully edited",
        }), 201
    # return redirect(url_for('inventory.inventory'))

# new changes
@inventory_bp.route('/get_ap_by_manufacturer',methods=['GET'])
def get_ap_by_manufacturer():
    manufacturer = request.args.get('manufacturer')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT a.* from AP as a join manufacturers as m on a.manufacturer_id=m.manufacturer_id where m.name=%s",(manufacturer,))
        ap=cursor.fetchall()
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()
    return jsonify(ap)

@inventory_bp.route('/get_controllers_by_manufacturer',methods=['GET'])
def get_controllers_by_manufacturer():
    manufacturer = request.args.get('manufacturer')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT c.* from controllers as c join manufacturers as m on c.manufacturer_id=m.manufacturer_id where m.name=%s",(manufacturer,))
        controllers=cursor.fetchall()
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()
    return jsonify(controllers)

@inventory_bp.route('/get_controllers_by_AP',methods=['GET'])
def get_controllers_by_AP():
    ap_id = request.args.get('ap_id')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT c.* from controllers as c join ap_controller_map as acm on c.controller_id=acm.controller_id where acm.ap_id=%s",(ap_id,))
        controllers=cursor.fetchall()
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()
    return jsonify(controllers)

@inventory_bp.route('/get_ap_status',methods=['GET'])
def get_ap_status():
    ap_id = request.args.get('ap_id')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("select status from ap where ap_id=%s",(ap_id,))
        ap=cursor.fetchone()
        ap_id=ap['status']
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()
    return jsonify(ap_id)

@inventory_bp.route('/get_controller_status',methods=['GET'])
def get_controller_status():
    controller_id = request.args.get('controller_id')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("select status from controllers where controller_id=%s",(controller_id,))
        controller=cursor.fetchone()
        controller_status=controller['status']        
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()
    return jsonify(controller_status)

@inventory_bp.route('/get_controller_url',methods=['GET'])
def get_controller_url():
    controller_id = request.args.get('controller_id')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("select url from controllers where controller_id=%s",(controller_id,))
        controller=cursor.fetchone()
        controller_url=controller['url']        
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()
    return jsonify(controller_url)

@inventory_bp.route('/get_manufacturers',methods=['GET'])
def get_manufacturers():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("select * from manufacturers")
        manufacturers=cursor.fetchall()
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()
    return jsonify(manufacturers)

@inventory_bp.route('/get_ap',methods=['GET'])
def get_ap():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("select * from ap ")
        ap=cursor.fetchall()
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()
    return jsonify(ap)

@inventory_bp.route('/get_controllers',methods=['GET'])
def get_controllers():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("select * from controllers ")
        controllers=cursor.fetchall()
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()
    return jsonify(controllers)

@inventory_bp.route('/edit_manufacturer',methods=['POST'])
def edit_manufacturer():
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    data=request.get_json()
    id=data.get('id')
    new_name=data.get('new_name')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("update manufacturers set name=%s where manufacturer_id=%s",(new_name,id,))
        conn.commit()
        cursor.execute("select * from manufacturers")
        manufacturers=cursor.fetchall()
        return jsonify(manufacturers)
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()

@inventory_bp.route('/delete_manufacturer',methods=['POST'])
def delete_manufacturer():
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    
    data=request.get_json()
    id=data.get('id')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("delete from manufacturers where manufacturer_id=%s",(id,))
        conn.commit()
        cursor.execute("select * from manufacturers")
        manufacturers=cursor.fetchall()
        return jsonify(manufacturers)
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()

@inventory_bp.route('/add_ap',methods=['POST'])
def add_ap():
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    
    data=request.get_json()
    manu_id=data.get('manu_id')
    ap_name=data.get('ap_name')
    controller=data.get('controller')
    print("controller:",controller=="")
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("insert into ap (manufacturer_id,model_name,status) values (%s,%s,'Available')",(manu_id,ap_name,))
        conn.commit()
        
        # Get the last inserted ID
        ap_id = cursor.lastrowid
        
        # Insert into ap_controller_map if controller list is provided
        if controller!="":
            cursor.execute(
                "INSERT INTO ap_controller_map (ap_id, controller_id) VALUES (%s, %s)",
                (ap_id, controller)
            )
            conn.commit()

        # Optionally fetch the full row
        cursor.execute("SELECT * FROM ap WHERE ap_id = %s", (ap_id,))
        new_ap = cursor.fetchone()

        return jsonify({
            "message": "Access Point added successfully",
            "ap": {
                "id": new_ap['ap_id'],
                "manufacturer_id": new_ap['manufacturer_id'],
                "model_name": new_ap['model_name']
            }
        }), 201
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()

@inventory_bp.route('/edit_ap',methods=['POST'])
def edit_ap():
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    
    data=request.get_json()
    ap_id=data.get('ap_id')
    ap_name=data.get('ap_name')
    controller_id=data.get('checkedValues')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if(ap_name!= ""):
            cursor.execute("update AP set model_name=%s where ap_id=%s",(ap_name,ap_id,))
            conn.commit()

        cursor.execute("delete from ap_controller_map where ap_id=%s",(ap_id,))
        conn.commit()

        cursor.execute("insert into ap_controller_map (ap_id,controller_id) values (%s,%s)",(ap_id,controller_id,))
        conn.commit()

        # Optionally fetch the full row
        cursor.execute("SELECT * FROM ap WHERE ap_id = %s", (ap_id,))
        new_ap = cursor.fetchone()

        return jsonify({
            "message": "Access Point added successfully",
            "ap": {
                "id": new_ap['ap_id'],
                "manufacturer_id": new_ap['manufacturer_id'],
                "model_name": new_ap['model_name']
            }
        }), 201
            
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()

@inventory_bp.route('/delete_ap',methods=['POST'])
def delete_ap():
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    
    data=request.get_json()
    ap_id=data.get('ap_id')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("delete from ap_controller_map where ap_id=%s",(ap_id,))
        conn.commit()
        cursor.execute("delete from AP where ap_id=%s",(ap_id,))
        conn.commit()

        return jsonify({
            "message": "Access Point successfully deleted",
        }), 201
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()

@inventory_bp.route('/change_ap_status',methods=['POST'])
def change_ap_status():
    ap_id = request.args.get('ap_id')
    data=request.get_json()
    status=data.get('status')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("update ap set status=%s where ap_id=%s",(status,ap_id,))
        conn.commit()
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        return "Database error", 500

    finally:
        cursor.close()
        conn.close()
    return jsonify(ap_id)