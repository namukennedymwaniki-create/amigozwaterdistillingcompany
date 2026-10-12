# =========================================================
# database_migrations_payments.py
# Payments module migrations
# =========================================================

from sqlalchemy import text
from database import _get_engine, get_is_cloud


def run_payments_migrations():
    engine = _get_engine()
    if engine is None:
        return False
    
    is_cloud = get_is_cloud()
    try:
        with engine.begin() as conn:
            if is_cloud:
                _pg(conn)
            else:
                _sqlite(conn)
        print("✅ Payments migrations complete")
        return True
    except Exception as e:
        print(f"❌ Payments migration error: {e}")
        return False


def _pg(conn):
    # ---- Allocations to invoices (customer receipts) ----
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS payment_allocations (
            id SERIAL PRIMARY KEY,
            payment_id INTEGER REFERENCES payments(id) ON DELETE CASCADE,
            invoice_id INTEGER REFERENCES invoices(id),
            amount NUMERIC(12,2) NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_pay_alloc_payment
        ON payment_allocations(payment_id)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_pay_alloc_invoice
        ON payment_allocations(invoice_id)
    """))

    # ---- Allocations to POs (supplier payments) ----
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS supplier_payment_allocations (
            id SERIAL PRIMARY KEY,
            payment_id INTEGER REFERENCES payments(id) ON DELETE CASCADE,
            po_id INTEGER REFERENCES purchase_orders(id),
            amount NUMERIC(12,2) NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_spay_alloc_payment
        ON supplier_payment_allocations(payment_id)
    """))

    # ---- Extend payments table ----
    alters = [
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS unallocated_amount NUMERIC(12,2) DEFAULT 0",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS is_reversal BOOLEAN DEFAULT FALSE",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS reverses_payment_id INTEGER",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS received_by INTEGER",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMP",
    ]
    for stmt in alters:
        try:
            conn.execute(text(stmt))
        except Exception as e:
            print(f"PG alter warn: {e}")


def _sqlite(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS payment_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER,
            invoice_id INTEGER,
            amount REAL NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS supplier_payment_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER,
            po_id INTEGER,
            amount REAL NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT
        )
    """))

    def add_col(table, col, typ):
        try:
            r = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            if col not in [row[1] for row in r]:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
        except Exception as e:
            print(f"SQLite add col warn: {e}")

    add_col("payments", "unallocated_amount", "REAL DEFAULT 0")
    add_col("payments", "is_reversal", "INTEGER DEFAULT 0")
    add_col("payments", "reverses_payment_id", "INTEGER")
    add_col("payments", "received_by", "INTEGER")
    add_col("payments", "confirmed_at", "TEXT")
