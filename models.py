from datetime import datetime
from flask_login import UserMixin
from database import db
from werkzeug.security import generate_password_hash, check_password_hash

class Permission(db.Model):
    __tablename__ = 'permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    module = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # create, read, update, delete, view
    description = db.Column(db.String(200))
    
    def __repr__(self):
        return f'<Permission {self.name}>'

class Role(db.Model):
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = db.relationship('User', back_populates='role', lazy='dynamic')
    permissions = db.relationship('Permission', secondary='role_permissions', lazy='dynamic')
    
    def __repr__(self):
        return f'<Role {self.name}>'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    is_superuser = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign Keys
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    
    # Relationships
    role = db.relationship('Role', back_populates='users')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}" if self.first_name and self.last_name else self.username
    
    def has_permission(self, module, action):
        if self.is_superuser:
            return True
        if not self.role:
            return False
        return self.role.permissions.filter_by(module=module, action=action).first() is not None
    
    def __repr__(self):
        return f'<User {self.username}>'

class RolePermission(db.Model):
    __tablename__ = 'role_permissions'
    
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), primary_key=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)

# Product Models
class ProductCategory(db.Model):
    __tablename__ = 'product_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    products = db.relationship('Product', back_populates='category')
    
    def __repr__(self):
        return f'<ProductCategory {self.name}>'

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    unit = db.Column(db.String(20), default='piece')  # piece, kg, liter, etc.
    unit_price = db.Column(db.Numeric(10, 2), default=0.00)
    cost_price = db.Column(db.Numeric(10, 2), default=0.00)
    min_stock_level = db.Column(db.Integer, default=0)
    max_stock_level = db.Column(db.Integer, default=1000)
    current_stock = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    barcode = db.Column(db.String(50))
    weight = db.Column(db.Numeric(10, 2))
    volume = db.Column(db.Numeric(10, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign Keys
    category_id = db.Column(db.Integer, db.ForeignKey('product_categories.id'))
    
    # Relationships
    category = db.relationship('ProductCategory', back_populates='products')
    
    def __repr__(self):
        return f'<Product {self.code} - {self.name}>'
    
    def is_low_stock(self):
        return self.current_stock <= self.min_stock_level

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    tax_number = db.Column(db.String(50))
    payment_terms = db.Column(db.Integer, default=30)  # days
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Supplier {self.name}>'

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    tax_number = db.Column(db.String(50))
    credit_limit = db.Column(db.Numeric(10, 2), default=0.00)
    current_balance = db.Column(db.Numeric(10, 2), default=0.00)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Customer {self.name}>'

class Inventory(db.Model):
    __tablename__ = 'inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    location = db.Column(db.String(100))
    batch_number = db.Column(db.String(50))
    expiration_date = db.Column(db.DateTime)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    product = db.relationship('Product')
    
    def __repr__(self):
        return f'<Inventory {self.product.name} - {self.quantity}>'

class StockTransaction(db.Model):
    __tablename__ = 'stock_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # IN, OUT, ADJUSTMENT
    quantity = db.Column(db.Integer, nullable=False)
    reference_type = db.Column(db.String(50))  # purchase_order, sales_order, etc.
    reference_id = db.Column(db.Integer)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    product = db.relationship('Product')
    user = db.relationship('User', foreign_keys=[created_by])
    
    def __repr__(self):
        return f'<StockTransaction {self.id} - {self.transaction_type}>'

# Seed default roles and permissions
def seed_default_data():
    """Seed default roles, permissions, and admin user"""
    
    # Create default roles
    roles_data = [
        {'name': 'Administrator', 'description': 'Full system access'},
        {'name': 'Managing Director', 'description': 'View all data'},
        {'name': 'Production Manager', 'description': 'Manage production'},
        {'name': 'Quality Control Officer', 'description': 'Manage quality control'},
        {'name': 'Storekeeper', 'description': 'Manage inventory'},
        {'name': 'Procurement Officer', 'description': 'Manage procurement'},
        {'name': 'Sales Officer', 'description': 'Manage sales'},
        {'name': 'Accountant', 'description': 'Manage finances'},
        {'name': 'Driver', 'description': 'Manage deliveries'},
    ]
    
    for role_data in roles_data:
        role = Role.query.filter_by(name=role_data['name']).first()
        if not role:
            role = Role(**role_data)
            db.session.add(role)
    
    db.session.commit()
    
    # Create default admin user if not exists
    admin_role = Role.query.filter_by(name='Administrator').first()
    admin_user = User.query.filter_by(username='admin').first()
    
    if not admin_user and admin_role:
        admin_user = User(
            username='admin',
            email='admin@wb-erp.com',
            first_name='System',
            last_name='Administrator',
            is_superuser=True,
            role=admin_role
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()