# =========================================================
# database_migrations_delivery.py
# Stage 05 — Delivery Confirmation migrations
# =========================================================

from sqlalchemy import text
from database import _get_engine, get_is_cloud


def run_delivery_migrations():
    """Idempotent migrations for delivery confirmation"""
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
        print("✅ Delivery migrations complete")
        return True
    except Exception as e:
        print(f"❌ Delivery migration error: {e}")
        return False


def _pg(conn):
    # Extend deliveries table
    cols = [
        "ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS received_by_name VARCHAR(100)",
        "ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS received_by_phone VARCHAR(20)",
        "ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS signature_ref VARCHAR(200)",
        "ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS photo_url VARCHAR(500)",
        "ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS is_partial BOOLEAN DEFAULT FALSE",
        "ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS confirmed_by INTEGER",
        "ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMP",
        "ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS delivery_notes TEXT",
    ]
    for c in cols:
        try:
            conn.execute(text(c))
        except Exception as e:
            print(f"PG alter warning: {e}")
    
    # Delivery items (line-level reconciliation)
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS delivery_items (
            id SERIAL PRIMARY KEY,
            delivery_id INTEGER REFERENCES deliveries(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            batch_id INTEGER REFERENCES product_batches(id),
            quantity_dispatched NUMERIC(12,2) NOT NULL DEFAULT 0,
            quantity_received NUMERIC(12,2) NOT NULL DEFAULT 0,
            quantity_rejected NUMERIC(12,2) NOT NULL DEFAULT 0,
            rejection_reason VARCHAR(200),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_delivery_items_delivery
        ON delivery_items(delivery_id)
    """))


def _sqlite(conn):
    def add_col(table, col, typ):
        try:
            r = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            existing = [row[1] for row in r]
            if col not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
        except Exception as e:
            print(f"SQLite add col warn: {e}")
    
    add_col("deliveries", "received_by_name", "TEXT")
    add_col("deliveries", "received_by_phone", "TEXT")
    add_col("deliveries", "signature_ref", "TEXT")
    add_col("deliveries", "photo_url", "TEXT")
    add_col("deliveries", "is_partial", "INTEGER DEFAULT 0")
    add_col("deliveries", "confirmed_by", "INTEGER")
    add_col("deliveries", "confirmed_at", "TEXT")
    add_col("deliveries", "delivery_notes", "TEXT")
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS delivery_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            delivery_id INTEGER,
            product_id INTEGER,
            batch_id INTEGER,
            quantity_dispatched REAL DEFAULT 0,
            quantity_received REAL DEFAULT 0,
            quantity_rejected REAL DEFAULT 0,
            rejection_reason TEXT,
            notes TEXT,
            created_at TEXT
        )
    """))
