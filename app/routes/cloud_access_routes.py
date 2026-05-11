from flask import Blueprint, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
from app.utils.db import get_db_connection
from flask import jsonify
from .notification_routes import schedule_email
import requests
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

cloud_access_bp = Blueprint('cloud', __name__)

@cloud_access_bp.route('/smartzone')
def smartzone():
    # Check if user is logged in
    if "user_id" not in session:
        return "Unauthorized", 401

    current_user = session["user_id"]

    controller_id = request.args.get("resource_id")
    if not controller_id:
        return jsonify(status="error", message="Missing resource ID"),400

    conn=get_db_connection()
    cursor=conn.cursor(dictionary=True)

    try:
        # Check if user has permission to access cloud resources
        cursor.execute("Select * from reservations where user_id = %s and controller_id = %s and start_datetime <= UTC_TIMESTAMP() and end_datetime > UTC_TIMESTAMP()", (current_user, controller_id))
        reservation = cursor.fetchone()

        if not reservation:
            return jsonify(status="error", message="Forbidden: you did not reserve this resource"),403

        cursor.execute("Select * from controllers where controller_id = %s", (controller_id,))
        controller = cursor.fetchone()
        if not controller:
            return jsonify(status="error", message="Resource not found"),404
        username = controller["cloud_username"]
        password = controller["cloud_password"]
        url=controller["url"]

        if not url:
            return jsonify(status="error", message="Cloud URL not configured for this resource"),400

        if not username or not password:
            return jsonify(status="error", message="Cloud credentials not configured for this resource"),400 

        http_session = requests.Session()    
        parsed = urlparse(url)

        
        if parsed.scheme != "https" or not parsed.hostname:
                    return jsonify(
                        status="error",
                        message="Invalid controller URL"
                    ), 400


        # Build base URL up to host:port
        base_url = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            base_url += f":{parsed.port}"

        print(base_url)

        # GET login page
        try:
            resp = http_session.get(url, verify=False)
        except requests.RequestException as e:
            return jsonify(status="error", message="Failed to reach controller login page"), 500

        soup = BeautifulSoup(resp.text, "html.parser")

        def get_field(name):
            tag = soup.find("input", {"name": name})
            return tag["value"] if tag and tag.has_attr("value") else None

        lt = get_field("lt")
        execution = get_field("execution")
        event_id = get_field("_eventId")

        # print("lt:", lt, "execution:", execution, "event_id:", event_id)

        payload = {
            "username": username,
            "password": password,
            "lt": lt,
            "execution": execution,
            "_eventId": event_id
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0"
        }

        post_resp = http_session.post(url, data=payload, headers=headers, verify=False, allow_redirects=False)

        if post_resp.status_code not in (302, 303):
            return jsonify(
                status="error",
                message="Authentication failed with controller"
            ), 401

        # print("Status:", post_resp.status_code)
        # print("Location:", post_resp.headers.get("Location"))
        # print("Cookies:", http_session.cookies.get_dict())

        location = post_resp.headers.get("Location")
        if location:
            redirect_url =urljoin(base_url, location)            
            parsed_redirect = urlparse(redirect_url)

            if parsed_redirect.hostname != parsed.hostname:
                return jsonify(
                    status="error",
                    message="Unsafe redirect blocked"
                ), 400

            # Instead of printing, send the browser there:
            return jsonify(status="success", redirect_url=redirect_url),200
        else:
            return jsonify(status="error", message="Login failed: no redirect location found"),400
    except Exception as e:
        print("Error during cloud access:", str(e))
        return jsonify(status="error", message="An error occurred while accessing the cloud resource"),500
    finally:
        cursor.close()
        conn.close()