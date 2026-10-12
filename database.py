# =========================================================
# AMIGOZ WATER DISTILLING COMPANY - DATABASE LAYER
# =========================================================
# Complete database initialization for the full ERP system
# Supports PostgreSQL (Neon) on cloud and SQLite locally
# =========================================================

import streamlit as st
import os
import json
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# =========================================================
# CONNECTION MANAGEMENT
# =========================================================

@st.cache_resource
def _get_engine():
    """Get cached SQLAlchemy engine (created once per session)"""
    database_url = None
    
    # Try Streamlit secrets first (cloud)
    try:
        database_url = st.secrets.get("DATABASE_URL")
    except:
        pass
    
    # Fallback to environment variable (local)
    if not database_url:
        database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        # PostgreSQL (Neon) - ensure SSL
        if "sslmode" not in database_url:
            if "?" in database_url:
                database_url += "&sslmode=require"
            else:
                database_url += "?sslmode=require"
        
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=300
        )
    else:
        # SQLite fallback
        engine = create_engine(
            'sqlite:///amigoz_erp.db',
            connect_args={'check_same_thread': False}
        )
    
    return engine


def get_db_connection():
    """Get a new database session"""
    try:
        engine = _get_engine()
        Session = sessionmaker(bind=engine)
        return Session()
    except Exception as e:
        st.error(f"❌ Database connection error: {str(e)}")
        return None


def read_sql(query, params=None):
    """
    Helper: Run a SELECT and return a DataFrame.
    Works with SQLAlchemy engine + psycopg (v3).
    Accepts either a plain string or a SQLAlchemy text() object.
    Named parameters (`:id`) are supported.
    """
    from sqlalchemy import text as sql_text

    engine = _get_engine()
    if engine is None:
        return pd.DataFrame()

    # Wrap in text() if it's a plain string so `:name` params work
    stmt = sql_text(query) if isinstance(query, str) else query

    try:
        if params:
            return pd.read_sql(stmt, engine, params=params)
        return pd.read_sql(stmt, engine)
    except Exception as e:
        print(f"read_sql error: {e}")
        try:
            with engine.connect() as conn:
                if params:
                    return pd.read_sql(stmt, conn, params=params)
                return pd.read_sql(stmt, conn)
        except Exception as e2:
            print(f"read_sql fallback error: {e2}")
            return pd.DataFrame()


def get_is_cloud():
    """Returns True if using PostgreSQL (cloud)"""
    try:
        if st.secrets.get("DATABASE_URL"):
            return True
    except:
        pass
    return os.getenv("DATABASE_URL") is not None


# =========================================================
# TABLE INITIALIZATION - 19 CORE TABLES
# =========================================================

def init_all_tables():
    """Create all 19 tables if they don't exist. Safe to run repeatedly."""
    engine = _get_engine()
    if engine is None:
        return False
    
    is_cloud = get_is_cloud()
    
    try:
        with engine.begin() as conn:
            
            # ============================================
            # POSTGRESQL SCHEMA
            # ============================================
            if is_cloud:
                statements = [
                    """CREATE TABLE IF NOT EXISTS roles (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(50) UNIQUE NOT NULL,
                        description TEXT,
                        permissions JSONB,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(50) UNIQUE NOT NULL,
                        email VARCHAR(100),
                        password_hash VARCHAR(255),
                        first_name VARCHAR(50),
                        last_name VARCHAR(50),
                        phone VARCHAR(20),
                        role_id INTEGER REFERENCES roles(id),
                        is_active BOOLEAN DEFAULT TRUE,
                        is_superuser BOOLEAN DEFAULT FALSE,
                        last_login TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS warehouses (
                        id SERIAL PRIMARY KEY,
                        code VARCHAR(20) UNIQUE NOT NULL,
                        name VARCHAR(100) NOT NULL,
                        warehouse_type VARCHAR(30) NOT NULL,
                        location VARCHAR(200),
                        address TEXT,
                        phone VARCHAR(20),
                        manager_name VARCHAR(100),
                        is_active BOOLEAN DEFAULT TRUE,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS product_categories (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) UNIQUE NOT NULL,
                        description TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS products (
                        id SERIAL PRIMARY KEY,
                        product_code VARCHAR(50) UNIQUE NOT NULL,
                        product_name VARCHAR(200) NOT NULL,
                        category_id INTEGER REFERENCES product_categories(id),
                        size VARCHAR(50),
                        unit VARCHAR(20) DEFAULT 'pcs',
                        pack_size INTEGER DEFAULT 1,
                        cost_price NUMERIC(12,2) DEFAULT 0,
                        selling_price NUMERIC(12,2) DEFAULT 0,
                        reorder_level INTEGER DEFAULT 0,
                        reorder_quantity INTEGER DEFAULT 0,
                        is_batch_tracked BOOLEAN DEFAULT FALSE,
                        is_active BOOLEAN DEFAULT TRUE,
                        description TEXT,
                        image_url VARCHAR(500),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS suppliers (
                        id SERIAL PRIMARY KEY,
                        supplier_code VARCHAR(50) UNIQUE NOT NULL,
                        supplier_name VARCHAR(200) NOT NULL,
                        contact_person VARCHAR(100),
                        phone VARCHAR(20),
                        email VARCHAR(100),
                        address TEXT,
                        town VARCHAR(50),
                        payment_terms VARCHAR(100),
                        tax_pin VARCHAR(50),
                        is_active BOOLEAN DEFAULT TRUE,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS customers (
                        id SERIAL PRIMARY KEY,
                        customer_code VARCHAR(50) UNIQUE NOT NULL,
                        customer_name VARCHAR(200) NOT NULL,
                        customer_type VARCHAR(50) DEFAULT 'Retail',
                        contact_person VARCHAR(100),
                        phone VARCHAR(20),
                        email VARCHAR(100),
                        address TEXT,
                        town VARCHAR(50),
                        credit_limit NUMERIC(12,2) DEFAULT 0,
                        payment_terms VARCHAR(100),
                        tax_pin VARCHAR(50),
                        is_active BOOLEAN DEFAULT TRUE,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS product_batches (
                        id SERIAL PRIMARY KEY,
                        batch_number VARCHAR(50) UNIQUE NOT NULL,
                        product_id INTEGER REFERENCES products(id),
                        production_date DATE,
                        expiry_date DATE,
                        quality_status VARCHAR(30) DEFAULT 'Released',
                        quantity_produced NUMERIC(12,2) DEFAULT 0,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS stock_movements (
                        id SERIAL PRIMARY KEY,
                        movement_date DATE NOT NULL,
                        movement_type VARCHAR(30) NOT NULL,
                        reference_number VARCHAR(50),
                        product_id INTEGER REFERENCES products(id),
                        batch_id INTEGER REFERENCES product_batches(id),
                        warehouse_id INTEGER REFERENCES warehouses(id),
                        quantity_change NUMERIC(12,2) NOT NULL,
                        unit_cost NUMERIC(12,2) DEFAULT 0,
                        balance_after NUMERIC(12,2),
                        reason TEXT,
                        reference_id INTEGER,
                        reference_table VARCHAR(50),
                        created_by INTEGER REFERENCES users(id),
                        approved_by INTEGER REFERENCES users(id),
                        is_posted BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS purchase_orders (
                        id SERIAL PRIMARY KEY,
                        po_number VARCHAR(50) UNIQUE NOT NULL,
                        supplier_id INTEGER REFERENCES suppliers(id),
                        order_date DATE NOT NULL,
                        expected_date DATE,
                        status VARCHAR(30) DEFAULT 'Draft',
                        total_amount NUMERIC(12,2) DEFAULT 0,
                        notes TEXT,
                        created_by INTEGER REFERENCES users(id),
                        approved_by INTEGER REFERENCES users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS goods_received_notes (
                        id SERIAL PRIMARY KEY,
                        grn_number VARCHAR(50) UNIQUE NOT NULL,
                        po_id INTEGER REFERENCES purchase_orders(id),
                        supplier_id INTEGER REFERENCES suppliers(id),
                        warehouse_id INTEGER REFERENCES warehouses(id),
                        received_date DATE NOT NULL,
                        status VARCHAR(30) DEFAULT 'Draft',
                        notes TEXT,
                        received_by INTEGER REFERENCES users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS sales_orders (
                        id SERIAL PRIMARY KEY,
                        order_number VARCHAR(50) UNIQUE NOT NULL,
                        customer_id INTEGER REFERENCES customers(id),
                        order_date DATE NOT NULL,
                        delivery_date DATE,
                        status VARCHAR(30) DEFAULT 'Draft',
                        subtotal NUMERIC(12,2) DEFAULT 0,
                        tax_amount NUMERIC(12,2) DEFAULT 0,
                        total_amount NUMERIC(12,2) DEFAULT 0,
                        notes TEXT,
                        created_by INTEGER REFERENCES users(id),
                        approved_by INTEGER REFERENCES users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS sales_order_items (
                        id SERIAL PRIMARY KEY,
                        order_id INTEGER REFERENCES sales_orders(id) ON DELETE CASCADE,
                        product_id INTEGER REFERENCES products(id),
                        quantity_ordered NUMERIC(12,2) NOT NULL,
                        quantity_dispatched NUMERIC(12,2) DEFAULT 0,
                        unit_price NUMERIC(12,2) NOT NULL,
                        line_total NUMERIC(12,2) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS dispatches (
                        id SERIAL PRIMARY KEY,
                        dispatch_number VARCHAR(50) UNIQUE NOT NULL,
                        order_id INTEGER REFERENCES sales_orders(id),
                        warehouse_id INTEGER REFERENCES warehouses(id),
                        dispatch_date DATE NOT NULL,
                        vehicle_number VARCHAR(50),
                        driver_name VARCHAR(100),
                        status VARCHAR(30) DEFAULT 'Draft',
                        notes TEXT,
                        created_by INTEGER REFERENCES users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS dispatch_items (
                        id SERIAL PRIMARY KEY,
                        dispatch_id INTEGER REFERENCES dispatches(id) ON DELETE CASCADE,
                        product_id INTEGER REFERENCES products(id),
                        batch_id INTEGER REFERENCES product_batches(id),
                        quantity_dispatched NUMERIC(12,2) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS deliveries (
                        id SERIAL PRIMARY KEY,
                        delivery_number VARCHAR(50) UNIQUE NOT NULL,
                        dispatch_id INTEGER REFERENCES dispatches(id),
                        delivery_date DATE NOT NULL,
                        delivered_by VARCHAR(100),
                        received_by VARCHAR(100),
                        status VARCHAR(30) DEFAULT 'Pending',
                        notes TEXT,
                        proof_of_delivery TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS containers (
                        id SERIAL PRIMARY KEY,
                        container_code VARCHAR(50) UNIQUE NOT NULL,
                        container_name VARCHAR(100) NOT NULL,
                        container_type VARCHAR(50),
                        size VARCHAR(20),
                        deposit_amount NUMERIC(12,2) DEFAULT 0,
                        is_returnable BOOLEAN DEFAULT TRUE,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS container_transactions (
                        id SERIAL PRIMARY KEY,
                        transaction_date DATE NOT NULL,
                        transaction_type VARCHAR(30) NOT NULL,
                        container_id INTEGER REFERENCES containers(id),
                        customer_id INTEGER REFERENCES customers(id),
                        quantity NUMERIC(12,2) NOT NULL,
                        deposit_amount NUMERIC(12,2) DEFAULT 0,
                        reference_number VARCHAR(50),
                        notes TEXT,
                        created_by INTEGER REFERENCES users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS payments (
                        id SERIAL PRIMARY KEY,
                        payment_number VARCHAR(50) UNIQUE NOT NULL,
                        payment_date DATE NOT NULL,
                        payment_type VARCHAR(30) NOT NULL,
                        customer_id INTEGER REFERENCES customers(id),
                        supplier_id INTEGER REFERENCES suppliers(id),
                        reference_id INTEGER,
                        reference_table VARCHAR(50),
                        amount NUMERIC(12,2) NOT NULL,
                        payment_method VARCHAR(50),
                        reference_number VARCHAR(100),
                        notes TEXT,
                        created_by INTEGER REFERENCES users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""",
                    """CREATE TABLE IF NOT EXISTS audit_logs (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER,
                        username VARCHAR(50),
                        action VARCHAR(50) NOT NULL,
                        table_name VARCHAR(50),
                        record_id INTEGER,
                        old_values JSONB,
                        new_values JSONB,
                        ip_address VARCHAR(50),
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )"""
                ]
            
            # ============================================
            # SQLITE SCHEMA
            # ============================================
            else:
                statements = [
                    """CREATE TABLE IF NOT EXISTS roles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        permissions TEXT,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        email TEXT,
                        password_hash TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        phone TEXT,
                        role_id INTEGER,
                        is_active INTEGER DEFAULT 1,
                        is_superuser INTEGER DEFAULT 0,
                        last_login TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS warehouses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        warehouse_type TEXT NOT NULL,
                        location TEXT,
                        address TEXT,
                        phone TEXT,
                        manager_name TEXT,
                        is_active INTEGER DEFAULT 1,
                        notes TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS product_categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_code TEXT UNIQUE NOT NULL,
                        product_name TEXT NOT NULL,
                        category_id INTEGER,
                        size TEXT,
                        unit TEXT DEFAULT 'pcs',
                        pack_size INTEGER DEFAULT 1,
                        cost_price REAL DEFAULT 0,
                        selling_price REAL DEFAULT 0,
                        reorder_level INTEGER DEFAULT 0,
                        reorder_quantity INTEGER DEFAULT 0,
                        is_batch_tracked INTEGER DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        description TEXT,
                        image_url TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS suppliers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        supplier_code TEXT UNIQUE NOT NULL,
                        supplier_name TEXT NOT NULL,
                        contact_person TEXT,
                        phone TEXT,
                        email TEXT,
                        address TEXT,
                        town TEXT,
                        payment_terms TEXT,
                        tax_pin TEXT,
                        is_active INTEGER DEFAULT 1,
                        notes TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS customers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_code TEXT UNIQUE NOT NULL,
                        customer_name TEXT NOT NULL,
                        customer_type TEXT DEFAULT 'Retail',
                        contact_person TEXT,
                        phone TEXT,
                        email TEXT,
                        address TEXT,
                        town TEXT,
                        credit_limit REAL DEFAULT 0,
                        payment_terms TEXT,
                        tax_pin TEXT,
                        is_active INTEGER DEFAULT 1,
                        notes TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS product_batches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        batch_number TEXT UNIQUE NOT NULL,
                        product_id INTEGER,
                        production_date TEXT,
                        expiry_date TEXT,
                        quality_status TEXT DEFAULT 'Released',
                        quantity_produced REAL DEFAULT 0,
                        notes TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS stock_movements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        movement_date TEXT NOT NULL,
                        movement_type TEXT NOT NULL,
                        reference_number TEXT,
                        product_id INTEGER,
                        batch_id INTEGER,
                        warehouse_id INTEGER,
                        quantity_change REAL NOT NULL,
                        unit_cost REAL DEFAULT 0,
                        balance_after REAL,
                        reason TEXT,
                        reference_id INTEGER,
                        reference_table TEXT,
                        created_by INTEGER,
                        approved_by INTEGER,
                        is_posted INTEGER DEFAULT 1,
                        created_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS purchase_orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        po_number TEXT UNIQUE NOT NULL,
                        supplier_id INTEGER,
                        order_date TEXT NOT NULL,
                        expected_date TEXT,
                        status TEXT DEFAULT 'Draft',
                        total_amount REAL DEFAULT 0,
                        notes TEXT,
                        created_by INTEGER,
                        approved_by INTEGER,
                        created_at TEXT,
                        updated_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS goods_received_notes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        grn_number TEXT UNIQUE NOT NULL,
                        po_id INTEGER,
                        supplier_id INTEGER,
                        warehouse_id INTEGER,
                        received_date TEXT NOT NULL,
                        status TEXT DEFAULT 'Draft',
                        notes TEXT,
                        received_by INTEGER,
                        created_at TEXT,
                        updated_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS sales_orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_number TEXT UNIQUE NOT NULL,
                        customer_id INTEGER,
                        order_date TEXT NOT NULL,
                        delivery_date TEXT,
                        status TEXT DEFAULT 'Draft',
                        subtotal REAL DEFAULT 0,
                        tax_amount REAL DEFAULT 0,
                        total_amount REAL DEFAULT 0,
                        notes TEXT,
                        created_by INTEGER,
                        approved_by INTEGER,
                        created_at TEXT,
                        updated_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS sales_order_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_id INTEGER,
                        product_id INTEGER,
                        quantity_ordered REAL NOT NULL,
                        quantity_dispatched REAL DEFAULT 0,
                        unit_price REAL NOT NULL,
                        line_total REAL NOT NULL,
                        created_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS dispatches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dispatch_number TEXT UNIQUE NOT NULL,
                        order_id INTEGER,
                        warehouse_id INTEGER,
                        dispatch_date TEXT NOT NULL,
                        vehicle_number TEXT,
                        driver_name TEXT,
                        status TEXT DEFAULT 'Draft',
                        notes TEXT,
                        created_by INTEGER,
                        created_at TEXT,
                        updated_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS dispatch_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dispatch_id INTEGER,
                        product_id INTEGER,
                        batch_id INTEGER,
                        quantity_dispatched REAL NOT NULL,
                        created_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS deliveries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        delivery_number TEXT UNIQUE NOT NULL,
                        dispatch_id INTEGER,
                        delivery_date TEXT NOT NULL,
                        delivered_by TEXT,
                        received_by TEXT,
                        status TEXT DEFAULT 'Pending',
                        notes TEXT,
                        proof_of_delivery TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS containers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        container_code TEXT UNIQUE NOT NULL,
                        container_name TEXT NOT NULL,
                        container_type TEXT,
                        size TEXT,
                        deposit_amount REAL DEFAULT 0,
                        is_returnable INTEGER DEFAULT 1,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS container_transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_date TEXT NOT NULL,
                        transaction_type TEXT NOT NULL,
                        container_id INTEGER,
                        customer_id INTEGER,
                        quantity REAL NOT NULL,
                        deposit_amount REAL DEFAULT 0,
                        reference_number TEXT,
                        notes TEXT,
                        created_by INTEGER,
                        created_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS payments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        payment_number TEXT UNIQUE NOT NULL,
                        payment_date TEXT NOT NULL,
                        payment_type TEXT NOT NULL,
                        customer_id INTEGER,
                        supplier_id INTEGER,
                        reference_id INTEGER,
                        reference_table TEXT,
                        amount REAL NOT NULL,
                        payment_method TEXT,
                        reference_number TEXT,
                        notes TEXT,
                        created_by INTEGER,
                        created_at TEXT
                    )""",
                    """CREATE TABLE IF NOT EXISTS audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        username TEXT,
                        action TEXT NOT NULL,
                        table_name TEXT,
                        record_id INTEGER,
                        old_values TEXT,
                        new_values TEXT,
                        ip_address TEXT,
                        timestamp TEXT
                    )"""
                ]
            
            # Execute all CREATE TABLE statements
            for stmt in statements:
                try:
                    conn.execute(text(stmt))
                except Exception as e:
                    print(f"Table creation warning: {e}")
            
            # ============================================
            # CREATE INDEXES
            # ============================================
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_products_code ON products(product_code)",
                "CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active)",
                "CREATE INDEX IF NOT EXISTS idx_customers_code ON customers(customer_code)",
                "CREATE INDEX IF NOT EXISTS idx_suppliers_code ON suppliers(supplier_code)",
                "CREATE INDEX IF NOT EXISTS idx_warehouses_code ON warehouses(code)",
                "CREATE INDEX IF NOT EXISTS idx_stock_movements_date ON stock_movements(movement_date)",
                "CREATE INDEX IF NOT EXISTS idx_stock_movements_product ON stock_movements(product_id)",
                "CREATE INDEX IF NOT EXISTS idx_batches_product ON product_batches(product_id)",
            ]
            
            for idx in indexes:
                try:
                    conn.execute(text(idx))
                except Exception as e:
                    print(f"Index warning: {e}")
        
        return True
    
    except Exception as e:
        st.error(f"❌ Table initialization error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# =========================================================
# SEED DEFAULT DATA
# =========================================================

def seed_default_data():
    """Insert default roles, warehouses, categories, containers"""
    conn = get_db_connection()
    if not conn:
        return False
    
    is_cloud = get_is_cloud()
    now = "CURRENT_TIMESTAMP"
    
    try:
        # SEED ROLES
        count = conn.execute(text("SELECT COUNT(*) FROM roles")).scalar()
        if count == 0:
            roles = [
                ("Administrator", "Full system access"),
                ("Managing Director", "View all data and approve"),
                ("Production Manager", "Manage production"),
                ("Quality Control Officer", "Manage quality control"),
                ("Storekeeper", "Manage inventory"),
                ("Procurement Officer", "Manage procurement"),
                ("Sales Officer", "Manage sales"),
                ("Accountant", "Manage finances"),
                ("Driver", "Manage deliveries"),
            ]
            for name, desc in roles:
                conn.execute(text(f"""
                    INSERT INTO roles (name, description, is_active, created_at)
                    VALUES (:name, :desc, 1, {now})
                """), {"name": name, "desc": desc})
        
        # SEED WAREHOUSES
        count = conn.execute(text("SELECT COUNT(*) FROM warehouses")).scalar()
        if count == 0:
            warehouses = [
                ("MAIN", "Main Store", "Main Store", "Head Office", "Amigoz Head Office"),
                ("PROD", "Production Store", "Production Store", "Production Unit", "Production Area"),
                ("DIST", "Distribution Depot", "Distribution Depot", "Depot", "Distribution Center"),
            ]
            for code, name, wtype, loc, addr in warehouses:
                conn.execute(text(f"""
                    INSERT INTO warehouses (code, name, warehouse_type, location, address, is_active, created_at)
                    VALUES (:code, :name, :wtype, :loc, :addr, 1, {now})
                """), {"code": code, "name": name, "wtype": wtype, "loc": loc, "addr": addr})
        
        # SEED PRODUCT CATEGORIES
        count = conn.execute(text("SELECT COUNT(*) FROM product_categories")).scalar()
        if count == 0:
            categories = [
                ("Bottled Water", "Purified bottled drinking water"),
                ("Bulk Water", "Bulk water supply in tanks"),
                ("Sachet Water", "Sachet drinking water"),
                ("Containers", "Returnable water containers"),
                ("Accessories", "Dispensers, pumps, and accessories"),
            ]
            for name, desc in categories:
                conn.execute(text(f"""
                    INSERT INTO product_categories (name, description, is_active, created_at)
                    VALUES (:name, :desc, 1, {now})
                """), {"name": name, "desc": desc})
        
        # SEED CONTAINERS
        count = conn.execute(text("SELECT COUNT(*) FROM containers")).scalar()
        if count == 0:
            containers = [
                ("CON-20L", "20 Litre Bottle", "Bottle", "20L", 300.00),
                ("CON-10L", "10 Litre Bottle", "Bottle", "10L", 200.00),
                ("CON-5L", "5 Litre Bottle", "Bottle", "5L", 150.00),
                ("CON-1L", "1 Litre Bottle", "Bottle", "1L", 50.00),
                ("CON-500ML", "500ml Bottle", "Bottle", "500ml", 30.00),
                ("CON-DISP", "Water Dispenser", "Dispenser", "Standard", 2500.00),
            ]
            for code, name, ctype, size, deposit in containers:
                conn.execute(text(f"""
                    INSERT INTO containers (container_code, container_name, container_type, size, deposit_amount, is_returnable, is_active, created_at)
                    VALUES (:code, :name, :ctype, :size, :deposit, 1, 1, {now})
                """), {"code": code, "name": name, "ctype": ctype, "size": size, "deposit": deposit})
        
        conn.commit()
        return True
    
    except Exception as e:
        print(f"Seed data error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# =========================================================
# AUDIT LOGGING
# =========================================================

def log_audit(action, table_name=None, record_id=None, old_values=None, new_values=None):
    """Log an audit trail entry"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        user_id = st.session_state.get('user_id')
        username = st.session_state.get('user') or 'system'
        
        old_json = json.dumps(old_values, default=str) if old_values else None
        new_json = json.dumps(new_values, default=str) if new_values else None
        
        conn.execute(text("""
            INSERT INTO audit_logs 
            (user_id, username, action, table_name, record_id, old_values, new_values, timestamp)
            VALUES (:uid, :uname, :action, :tname, :rid, :old, :new, CURRENT_TIMESTAMP)
        """), {
            "uid": user_id,
            "uname": username,
            "action": action,
            "tname": table_name,
            "rid": record_id,
            "old": old_json,
            "new": new_json
        })
        
        conn.commit()
        return True
    
    except Exception as e:
        print(f"Audit log error: {e}")
        return False
    finally:
        try:
            conn.close()
        except:
            pass


# =========================================================
# HELPER: GET NEXT CODE
# =========================================================

def get_next_code(table, column, prefix, pad=4):
    """Generate next sequential code like PROD-0001"""
    conn = get_db_connection()
    if not conn:
        return f"{prefix}-0001"
    
    try:
        result = conn.execute(text(f"""
            SELECT {column} FROM {table} 
            WHERE {column} LIKE :prefix 
            ORDER BY id DESC LIMIT 1
        """), {"prefix": f"{prefix}-%"}).fetchone()
        
        if result and result[0]:
            try:
                last_num = int(str(result[0]).split('-')[-1])
                return f"{prefix}-{str(last_num + 1).zfill(pad)}"
            except:
                return f"{prefix}-0001"
        return f"{prefix}-0001"
    
    except:
        return f"{prefix}-0001"
    finally:
        conn.close()


# =========================================================
# INITIALIZATION HELPER
# =========================================================

def initialize_database():
    """Run full initialization: create tables + seed defaults."""
    if not init_all_tables():
        return False
    seed_default_data()
    return True
