from flask import Flask
from .routes import register_routes
import os

def create_app():
    app = Flask(__name__)
    app.secret_key = 'your-secret-key'

    register_routes(app)

    return app