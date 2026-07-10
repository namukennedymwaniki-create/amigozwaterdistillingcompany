from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from database import db
from models import (
    User, Role, Product, ProductCategory, 
    Supplier, Customer, Inventory, StockTransaction
)
from datetime import datetime, timedelta
from sqlalchemy import func

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    return redirect(url_for('main.dashboard'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Get current date
    today = datetime.now().date()
    start_of_month = today.replace(day=1)
    
    # Production stats (mock data for now)
    production_today = 0
    production_month = 0
    machine_utilization = 75
    
    # Sales stats (mock data)
    sales_today = 0
    monthly_revenue = 0
    outstanding_payments = 0
    
    # Inventory stats
    total_products = Product.query.count()
    low_stock_products = Product.query.filter(
        Product.current_stock <= Product.min_stock_level
    ).count()
    reorder_alerts = Product.query.filter(
        Product.current_stock <= Product.min_stock_level * 0.5
    ).count()
    
    # Quality stats (mock)
    water_test_status = 'Passed'
    failed_batches = 0
    approved_batches = 0
    
    # Delivery stats (mock)
    vehicles_out = 2
    deliveries_completed = 5
    
    # Recent activities
    recent_transactions = StockTransaction.query.order_by(
        StockTransaction.created_at.desc()
    ).limit(10).all()
    
    # Quick stats for products
    total_stock = db.session.query(func.sum(Product.current_stock)).scalar() or 0
    
    context = {
        'production_today': production_today,
        'production_month': production_month,
        'machine_utilization': machine_utilization,
        'sales_today': sales_today,
        'monthly_revenue': monthly_revenue,
        'outstanding_payments': outstanding_payments,
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'reorder_alerts': reorder_alerts,
        'water_test_status': water_test_status,
        'failed_batches': failed_batches,
        'approved_batches': approved_batches,
        'vehicles_out': vehicles_out,
        'deliveries_completed': deliveries_completed,
        'recent_transactions': recent_transactions,
        'total_stock': total_stock,
        'today': today,
    }
    
    return render_template('dashboard.html', **context)

# Product Management Routes
@main_bp.route('/products')
@login_required
def products():
    if not current_user.has_permission('products', 'view'):
        flash('You don\'t have permission to view products.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    products = Product.query.all()
    categories = ProductCategory.query.all()
    return render_template('products/index.html', products=products, categories=categories)

@main_bp.route('/products/create', methods=['GET', 'POST'])
@login_required
def create_product():
    if not current_user.has_permission('products', 'create'):
        flash('You don\'t have permission to create products.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        # Create new product
        product = Product(
            code=request.form.get('code'),
            name=request.form.get('name'),
            description=request.form.get('description'),
            category_id=request.form.get('category_id'),
            unit=request.form.get('unit'),
            unit_price=request.form.get('unit_price'),
            cost_price=request.form.get('cost_price'),
            min_stock_level=request.form.get('min_stock_level'),
            max_stock_level=request.form.get('max_stock_level'),
            barcode=request.form.get('barcode'),
            weight=request.form.get('weight'),
            volume=request.form.get('volume'),
        )
        db.session.add(product)
        db.session.commit()
        flash('Product created successfully!', 'success')
        return redirect(url_for('main.products'))
    
    categories = ProductCategory.query.filter_by(is_active=True).all()
    return render_template('products/create.html', categories=categories)

@main_bp.route('/products/<int:product_id>')
@login_required
def view_product(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('products/view.html', product=product)

@main_bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    if not current_user.has_permission('products', 'update'):
        flash('You don\'t have permission to edit products.', 'danger')
        return redirect(url_for('main.products'))
    
    if request.method == 'POST':
        product.code = request.form.get('code')
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.category_id = request.form.get('category_id')
        product.unit = request.form.get('unit')
        product.unit_price = request.form.get('unit_price')
        product.cost_price = request.form.get('cost_price')
        product.min_stock_level = request.form.get('min_stock_level')
        product.max_stock_level = request.form.get('max_stock_level')
        product.barcode = request.form.get('barcode')
        product.weight = request.form.get('weight')
        product.volume = request.form.get('volume')
        product.is_active = bool(request.form.get('is_active'))
        
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('main.view_product', product_id=product.id))
    
    categories = ProductCategory.query.filter_by(is_active=True).all()
    return render_template('products/edit.html', product=product, categories=categories)

# Supplier Management
@main_bp.route('/suppliers')
@login_required
def suppliers():
    if not current_user.has_permission('suppliers', 'view'):
        flash('You don\'t have permission to view suppliers.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    suppliers = Supplier.query.all()
    return render_template('suppliers/index.html', suppliers=suppliers)

@main_bp.route('/suppliers/create', methods=['GET', 'POST'])
@login_required
def create_supplier():
    if not current_user.has_permission('suppliers', 'create'):
        flash('You don\'t have permission to create suppliers.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        supplier = Supplier(
            name=request.form.get('name'),
            contact_person=request.form.get('contact_person'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            address=request.form.get('address'),
            tax_number=request.form.get('tax_number'),
            payment_terms=request.form.get('payment_terms', 30),
        )
        db.session.add(supplier)
        db.session.commit()
        flash('Supplier created successfully!', 'success')
        return redirect(url_for('main.suppliers'))
    
    return render_template('suppliers/create.html')

@main_bp.route('/suppliers/<int:supplier_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    
    if not current_user.has_permission('suppliers', 'update'):
        flash('You don\'t have permission to edit suppliers.', 'danger')
        return redirect(url_for('main.suppliers'))
    
    if request.method == 'POST':
        supplier.name = request.form.get('name')
        supplier.contact_person = request.form.get('contact_person')
        supplier.email = request.form.get('email')
        supplier.phone = request.form.get('phone')
        supplier.address = request.form.get('address')
        supplier.tax_number = request.form.get('tax_number')
        supplier.payment_terms = request.form.get('payment_terms')
        supplier.is_active = bool(request.form.get('is_active'))
        
        db.session.commit()
        flash('Supplier updated successfully!', 'success')
        return redirect(url_for('main.suppliers'))
    
    return render_template('suppliers/edit.html', supplier=supplier)

# Customer Management
@main_bp.route('/customers')
@login_required
def customers():
    if not current_user.has_permission('customers', 'view'):
        flash('You don\'t have permission to view customers.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    customers = Customer.query.all()
    return render_template('customers/index.html', customers=customers)

@main_bp.route('/customers/create', methods=['GET', 'POST'])
@login_required
def create_customer():
    if not current_user.has_permission('customers', 'create'):
        flash('You don\'t have permission to create customers.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        customer = Customer(
            name=request.form.get('name'),
            contact_person=request.form.get('contact_person'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            address=request.form.get('address'),
            tax_number=request.form.get('tax_number'),
            credit_limit=request.form.get('credit_limit', 0),
        )
        db.session.add(customer)
        db.session.commit()
        flash('Customer created successfully!', 'success')
        return redirect(url_for('main.customers'))
    
    return render_template('customers/create.html')

# User Management
@main_bp.route('/users')
@login_required
def users():
    if not current_user.has_permission('users', 'view') and not current_user.is_superuser:
        flash('You don\'t have permission to view users.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    users = User.query.all()
    roles = Role.query.all()
    return render_template('users/index.html', users=users, roles=roles)

@main_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
def create_user():
    if not current_user.has_permission('users', 'create') and not current_user.is_superuser:
        flash('You don\'t have permission to create users.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        user = User(
            username=request.form.get('username'),
            email=request.form.get('email'),
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            phone=request.form.get('phone'),
            role_id=request.form.get('role_id'),
            is_active=True,
            is_superuser=bool(request.form.get('is_superuser', False)),
        )
        user.set_password(request.form.get('password'))
        db.session.add(user)
        db.session.commit()
        flash('User created successfully!', 'success')
        return redirect(url_for('main.users'))
    
    roles = Role.query.filter_by(is_active=True).all()
    return render_template('users/create.html', roles=roles)

@main_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if not current_user.has_permission('users', 'update') and not current_user.is_superuser:
        flash('You don\'t have permission to edit users.', 'danger')
        return redirect(url_for('main.users'))
    
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.phone = request.form.get('phone')
        user.role_id = request.form.get('role_id')
        user.is_active = bool(request.form.get('is_active', True))
        user.is_superuser = bool(request.form.get('is_superuser', False))
        
        password = request.form.get('password')
        if password:
            user.set_password(password)
        
        db.session.commit()
        flash('User updated successfully!', 'success')
        return redirect(url_for('main.users'))
    
    roles = Role.query.filter_by(is_active=True).all()
    return render_template('users/edit.html', user=user, roles=roles)

# Categories Management
@main_bp.route('/categories')
@login_required
def categories():
    if not current_user.has_permission('products', 'view'):
        flash('You don\'t have permission to view categories.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    categories = ProductCategory.query.all()
    return render_template('categories/index.html', categories=categories)

# Error handlers
@main_bp.app_errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@main_bp.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500