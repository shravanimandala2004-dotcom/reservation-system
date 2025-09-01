import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='Welcome@12345!',
        database='ap_reservation'
    )