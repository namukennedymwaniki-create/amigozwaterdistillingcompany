from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from database import db, login_manager, csrf
from config import Config, DevelopmentConfig, ProductionConfig
import os
from datetime import datetime

# Import models
from models import (
    User, Role, Permission, RolePermission,
    Product, ProductCategory, Supplier, Customer,
    Inventory, StockTransaction
)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Create upload folder if not exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Register blueprints
    from auth import auth_bp
    from main import main_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    
    @app.context_processor
    def utility_processor():
        def get_now():
            return datetime.now()
        return dict(get_now=get_now)
    
    return app

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Seed default data
        from models import seed_default_data
        seed_default_data()
    app.run(debug=True, host='0.0.0.0', port=5000)