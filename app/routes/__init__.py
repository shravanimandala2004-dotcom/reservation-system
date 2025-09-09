from .auth_routes import auth_bp
from .reservation_routes import reservation_bp
from .inventory_routes import inventory_bp
from .permission_routes import permission_bp
from .details import details_bp

def register_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(reservation_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(permission_bp)
    app.register_blueprint(details_bp)