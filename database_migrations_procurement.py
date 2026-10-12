# =========================================================
# database_migrations_procurement.py
# Stage 02 — Suppliers & Procurement migrations
# =========================================================

from sqlalchemy import text
from database import _get_engine, get_is_cloud


def run_procurement_migrations():
    """Idempotent migrations for procurement"""
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
        print("✅ Procurement migrations complete")
        return True
    except Exception as e:
        print(f"❌ Procurement migration error: {e}")
        return False


def _pg(conn):
    # -------- PURCHASE ORDER ITEMS --------
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS purchase_order_items (
            id SERIAL PRIMARY KEY,
            po_id INTEGER REFERENCES purchase_orders(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            quantity_ordered NUMERIC(12,2) NOT NULL DEFAULT 0,
            quantity_received NUMERIC(12,2) NOT NULL DEFAULT 0,
            unit_cost NUMERIC(12,2) NOT NULL DEFAULT 0,
            line_total NUMERIC(12,2) NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_po_items_po
        ON purchase_order_items(po_id)
    """))

    # -------- GRN ITEMS --------
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS goods_received_note_items (
            id SERIAL PRIMARY KEY,
            grn_id INTEGER REFERENCES goods_received_notes(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            po_item_id INTEGER REFERENCES purchase_order_items(id),
            batch_id INTEGER REFERENCES product_batches(id),
            quantity_received NUMERIC(12,2) NOT NULL DEFAULT 0,
            quantity_rejected NUMERIC(12,2) NOT NULL DEFAULT 0,
            unit_cost NUMERIC(12,2) NOT NULL DEFAULT 0,
            rejection_reason VARCHAR(200),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_grn_items_grn
        ON goods_received_note_items(grn_id)
    """))

    # -------- EXTRA HEADER COLUMNS --------
    alters = [
        # PO header
        "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP",
        "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS approved_by INTEGER",
        "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS payment_terms VARCHAR(50) DEFAULT '30 days'",
        "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'KES'",
        # GRN header
        "ALTER TABLE goods_received_notes ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMP",
        "ALTER TABLE goods_received_notes ADD COLUMN IF NOT EXISTS confirmed_by INTEGER",
        "ALTER TABLE goods_received_notes ADD COLUMN IF NOT EXISTS grn_notes TEXT",
        # Supplier extensions
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS current_balance NUMERIC(12,2) DEFAULT 0",
    ]
    for stmt in alters:
        try:
            conn.execute(text(stmt))
        except Exception as e:
            print(f"PG alter warn: {e}")


def _sqlite(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS purchase_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id INTEGER,
            product_id INTEGER,
            quantity_ordered REAL DEFAULT 0,
            quantity_received REAL DEFAULT 0,
            unit_cost REAL DEFAULT 0,
            line_total REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS goods_received_note_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grn_id INTEGER,
            product_id INTEGER,
            po_item_id INTEGER,
            batch_id INTEGER,
            quantity_received REAL DEFAULT 0,
            quantity_rejected REAL DEFAULT 0,
            unit_cost REAL DEFAULT 0,
            rejection_reason TEXT,
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

    add_col("purchase_orders", "approved_at", "TEXT")
    add_col("purchase_orders", "approved_by", "INTEGER")
    add_col("purchase_orders", "payment_terms", "TEXT DEFAULT '30 days'")
    add_col("purchase_orders", "currency", "TEXT DEFAULT 'KES'")
    add_col("goods_received_notes", "confirmed_at", "TEXT")
    add_col("goods_received_notes", "confirmed_by", "INTEGER")
    add_col("goods_received_notes", "grn_notes", "TEXT")
    add_col("suppliers", "current_balance", "REAL DEFAULT 0")
