from .auth_routes import auth_bp
from .reservation_routes import reservation_bp
from .inventory_routes import inventory_bp
from .permission_routes import permission_bp
from .details import details_bp

from flask import Flask
from app.routes.rules import rules_bp

def create_app():
    app = Flask(__name__)
    register_routes(app)  # ✅ This line is missing in your current code
    return app

# def create_app():
#     app = Flask(__name__)
  

#     # Register blueprints inside the function
#     app.register_blueprint(rules_bp)

#     return app

def register_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(reservation_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(permission_bp)
    app.register_blueprint(details_bp)
    app.register_blueprint(rules_bp)