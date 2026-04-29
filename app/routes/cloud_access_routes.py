from flask import Blueprint, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
from app.utils.db import get_db_connection
from flask import jsonify
from .notification_routes import schedule_email
import requests
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

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

    # Check if user has permission to access cloud resources
    cursor.execute("Select * from reservations where user_id = %s and controller_id = %s and end_datetime > UTC_TIMESTAMP()", (current_user, controller_id))
    reservation = cursor.fetchone()

    if not reservation:
        return jsonify(status="error", message="Forbidden: you did not reserve this resource"),403

    cursor.execute("Select * from controllers where controller_id = %s", (controller_id,))
    controller = cursor.fetchone()
    username = controller["cloud_username"]
    password = controller["cloud_password"]

    http_session = requests.Session()
    url=controller["url"]
    parsed = urlparse(url)

    # Build base URL up to host:port
    base_url = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"

    print(base_url)

    # GET login page
    resp = http_session.get(url, verify=False)
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

    # print("Status:", post_resp.status_code)
    # print("Location:", post_resp.headers.get("Location"))
    # print("Cookies:", http_session.cookies.get_dict())

    location = post_resp.headers.get("Location")
    if location:
        redirect_url = base_url + location
        # Instead of printing, send the browser there:
        return jsonify(status="success", redirect_url=redirect_url),200
    else:
        return jsonify(status="error", message="Login failed: no redirect location found"),400