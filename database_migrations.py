# =========================================================
# database_migrations.py
# Safe migrations for Stage 04 (Sales) and Stage 03 (Dispatch)
# Run once at app startup — idempotent
# =========================================================

import streamlit as st
from sqlalchemy import text
from database import _get_engine, get_is_cloud


def run_migrations():
    """Run all pending migrations safely."""
    engine = _get_engine()
    if engine is None:
        return False
    
    is_cloud = get_is_cloud()
    
    try:
        with engine.begin() as conn:
            if is_cloud:
                _migrate_postgres(conn)
            else:
                _migrate_sqlite(conn)
        
        print("✅ Migrations complete")
        return True
    except Exception as e:
        print(f"❌ Migration error: {e}")
        return False


def _migrate_postgres(conn):
    """PostgreSQL migrations"""
    
    # ============================================
    # 1. STOCK RESERVATIONS
    # ============================================
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS stock_reservations (
            id SERIAL PRIMARY KEY,
            reservation_number VARCHAR(50) UNIQUE NOT NULL,
            product_id INTEGER REFERENCES products(id),
            warehouse_id INTEGER REFERENCES warehouses(id),
            batch_id INTEGER REFERENCES product_batches(id),
            quantity NUMERIC(12,2) NOT NULL,
            reference_id INTEGER,
            reference_table VARCHAR(50),
            reference_number VARCHAR(50),
            reserved_for VARCHAR(200),
            status VARCHAR(30) DEFAULT 'Active',
            expires_at TIMESTAMP,
            released_at TIMESTAMP,
            released_reason TEXT,
            notes TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_reservations_product 
        ON stock_reservations(product_id)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_reservations_status 
        ON stock_reservations(status)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_reservations_reference 
        ON stock_reservations(reference_table, reference_id)
    """))
    
    # ============================================
    # 2. INVOICES
    # ============================================
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS invoices (
            id SERIAL PRIMARY KEY,
            invoice_number VARCHAR(50) UNIQUE NOT NULL,
            order_id INTEGER REFERENCES sales_orders(id),
            customer_id INTEGER REFERENCES customers(id),
            invoice_date DATE NOT NULL,
            due_date DATE,
            subtotal NUMERIC(12,2) DEFAULT 0,
            tax_amount NUMERIC(12,2) DEFAULT 0,
            total_amount NUMERIC(12,2) DEFAULT 0,
            amount_paid NUMERIC(12,2) DEFAULT 0,
            balance_due NUMERIC(12,2) DEFAULT 0,
            status VARCHAR(30) DEFAULT 'Unpaid',
            notes TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    # ============================================
    # 3. INVOICE ITEMS
    # ============================================
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS invoice_items (
            id SERIAL PRIMARY KEY,
            invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            description TEXT,
            quantity NUMERIC(12,2) NOT NULL,
            unit_price NUMERIC(12,2) NOT NULL,
            line_total NUMERIC(12,2) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    # ============================================
    # 4. VEHICLES
    # ============================================
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id SERIAL PRIMARY KEY,
            plate_number VARCHAR(30) UNIQUE NOT NULL,
            description VARCHAR(200),
            capacity_kg NUMERIC(10,2) DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    # ============================================
    # 5. DRIVERS
    # ============================================
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS drivers (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            phone VARCHAR(20),
            license_number VARCHAR(50),
            is_active BOOLEAN DEFAULT TRUE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    # ============================================
    # 6. ADD COLUMNS TO DISPATCHES
    # ============================================
    alter_statements = [
        "ALTER TABLE dispatches ADD COLUMN IF NOT EXISTS vehicle_id INTEGER",
        "ALTER TABLE dispatches ADD COLUMN IF NOT EXISTS driver_id INTEGER",
        "ALTER TABLE dispatches ADD COLUMN IF NOT EXISTS picked_by INTEGER",
        "ALTER TABLE dispatches ADD COLUMN IF NOT EXISTS picked_at TIMESTAMP",
        "ALTER TABLE dispatches ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP",
    ]
    for stmt in alter_statements:
        try:
            conn.execute(text(stmt))
        except Exception as e:
            print(f"Alter warning: {e}")
    
    # ============================================
    # 7. ADD COLUMNS TO SALES ORDERS
    # ============================================
    sales_alter = [
        "ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS tax_rate NUMERIC(5,2) DEFAULT 0",
        "ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS vat_enabled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMP",
        "ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS confirmed_by INTEGER",
        "ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS dispatched_at TIMESTAMP",
        "ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP",
        "ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS cancellation_reason TEXT",
    ]
    for stmt in sales_alter:
        try:
            conn.execute(text(stmt))
        except Exception as e:
            print(f"Sales alter warning: {e}")
    
    # ============================================
    # 8. ADD COLUMNS TO CUSTOMERS
    # ============================================
    cust_alter = [
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS customer_type VARCHAR(50) DEFAULT 'Retail'",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS credit_limit NUMERIC(12,2) DEFAULT 0",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS current_balance NUMERIC(12,2) DEFAULT 0",
    ]
    for stmt in cust_alter:
        try:
            conn.execute(text(stmt))
        except Exception as e:
            print(f"Customer alter warning: {e}")


def _migrate_sqlite(conn):
    """SQLite migrations"""
    
    # STOCK RESERVATIONS
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS stock_reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reservation_number TEXT UNIQUE NOT NULL,
            product_id INTEGER,
            warehouse_id INTEGER,
            batch_id INTEGER,
            quantity REAL NOT NULL,
            reference_id INTEGER,
            reference_table TEXT,
            reference_number TEXT,
            reserved_for TEXT,
            status TEXT DEFAULT 'Active',
            expires_at TEXT,
            released_at TEXT,
            released_reason TEXT,
            notes TEXT,
            created_by INTEGER,
            created_at TEXT
        )
    """))
    
    # INVOICES
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            order_id INTEGER,
            customer_id INTEGER,
            invoice_date TEXT NOT NULL,
            due_date TEXT,
            subtotal REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            amount_paid REAL DEFAULT 0,
            balance_due REAL DEFAULT 0,
            status TEXT DEFAULT 'Unpaid',
            notes TEXT,
            created_by INTEGER,
            created_at TEXT,
            updated_at TEXT
        )
    """))
    
    # INVOICE ITEMS
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER,
            product_id INTEGER,
            description TEXT,
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            line_total REAL NOT NULL,
            created_at TEXT
        )
    """))
    
    # VEHICLES
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT UNIQUE NOT NULL,
            description TEXT,
            capacity_kg REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            notes TEXT,
            created_at TEXT
        )
    """))
    
    # DRIVERS
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS drivers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            license_number TEXT,
            is_active INTEGER DEFAULT 1,
            notes TEXT,
            created_at TEXT
        )
    """))
    
    # SQLite doesn't support IF NOT EXISTS for ADD COLUMN, so check manually
    _sqlite_add_column_if_missing(conn, "dispatches", "vehicle_id", "INTEGER")
    _sqlite_add_column_if_missing(conn, "dispatches", "driver_id", "INTEGER")
    _sqlite_add_column_if_missing(conn, "dispatches", "picked_by", "INTEGER")
    _sqlite_add_column_if_missing(conn, "dispatches", "picked_at", "TEXT")
    _sqlite_add_column_if_missing(conn, "dispatches", "delivered_at", "TEXT")
    
    _sqlite_add_column_if_missing(conn, "sales_orders", "tax_rate", "REAL DEFAULT 0")
    _sqlite_add_column_if_missing(conn, "sales_orders", "vat_enabled", "INTEGER DEFAULT 0")
    _sqlite_add_column_if_missing(conn, "sales_orders", "confirmed_at", "TEXT")
    _sqlite_add_column_if_missing(conn, "sales_orders", "confirmed_by", "INTEGER")
    _sqlite_add_column_if_missing(conn, "sales_orders", "dispatched_at", "TEXT")
    _sqlite_add_column_if_missing(conn, "sales_orders", "cancelled_at", "TEXT")
    _sqlite_add_column_if_missing(conn, "sales_orders", "cancellation_reason", "TEXT")
    
    _sqlite_add_column_if_missing(conn, "customers", "customer_type", "TEXT DEFAULT 'Retail'")
    _sqlite_add_column_if_missing(conn, "customers", "credit_limit", "REAL DEFAULT 0")
    _sqlite_add_column_if_missing(conn, "customers", "current_balance", "REAL DEFAULT 0")


def _sqlite_add_column_if_missing(conn, table, column, col_type):
    """Add column to SQLite table if it doesn't exist"""
    try:
        result = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        existing = [row[1] for row in result]
        if column not in existing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
    except Exception as e:
        print(f"Column add warning for {table}.{column}: {e}")
