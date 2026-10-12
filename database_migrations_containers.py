# =========================================================
# database_migrations_containers.py
# Stage 06 — Returnable Containers migrations
# =========================================================

from sqlalchemy import text
from database import _get_engine, get_is_cloud


def run_container_migrations():
    """Idempotent migrations for container tracking"""
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
        print("✅ Container migrations complete")
        return True
    except Exception as e:
        print(f"❌ Container migration error: {e}")
        return False


def _pg(conn):
    # Container issue/return headers
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS container_issues (
            id SERIAL PRIMARY KEY,
            issue_number VARCHAR(50) UNIQUE NOT NULL,
            customer_id INTEGER REFERENCES customers(id),
            order_id INTEGER REFERENCES sales_orders(id),
            dispatch_id INTEGER REFERENCES dispatches(id),
            issue_date DATE NOT NULL,
            status VARCHAR(30) DEFAULT 'Issued',
            due_date DATE,
            total_deposit NUMERIC(12,2) DEFAULT 0,
            refunded_amount NUMERIC(12,2) DEFAULT 0,
            forfeited_amount NUMERIC(12,2) DEFAULT 0,
            notes TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS container_issue_items (
            id SERIAL PRIMARY KEY,
            issue_id INTEGER REFERENCES container_issues(id) ON DELETE CASCADE,
            container_id INTEGER REFERENCES containers(id),
            quantity_issued NUMERIC(12,2) NOT NULL DEFAULT 0,
            quantity_returned NUMERIC(12,2) NOT NULL DEFAULT 0,
            quantity_lost NUMERIC(12,2) NOT NULL DEFAULT 0,
            deposit_per_unit NUMERIC(12,2) NOT NULL DEFAULT 0,
            line_deposit NUMERIC(12,2) NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS container_returns (
            id SERIAL PRIMARY KEY,
            return_number VARCHAR(50) UNIQUE NOT NULL,
            issue_id INTEGER REFERENCES container_issues(id),
            customer_id INTEGER REFERENCES customers(id),
            return_date DATE NOT NULL,
            status VARCHAR(30) DEFAULT 'Received',
            refund_amount NUMERIC(12,2) DEFAULT 0,
            refund_status VARCHAR(30) DEFAULT 'Pending',
            notes TEXT,
            received_by INTEGER,
            refunded_by INTEGER,
            refunded_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS container_return_items (
            id SERIAL PRIMARY KEY,
            return_id INTEGER REFERENCES container_returns(id) ON DELETE CASCADE,
            issue_item_id INTEGER REFERENCES container_issue_items(id),
            container_id INTEGER REFERENCES containers(id),
            quantity_returned NUMERIC(12,2) NOT NULL DEFAULT 0,
            quantity_lost NUMERIC(12,2) NOT NULL DEFAULT 0,
            loss_reason VARCHAR(200),
            deposit_per_unit NUMERIC(12,2) NOT NULL DEFAULT 0,
            refund_line NUMERIC(12,2) DEFAULT 0,
            forfeited_line NUMERIC(12,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    # Indexes
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_cissues_customer ON container_issues(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_cissues_status ON container_issues(status)",
        "CREATE INDEX IF NOT EXISTS idx_cissues_order ON container_issues(order_id)",
        "CREATE INDEX IF NOT EXISTS idx_creturns_customer ON container_returns(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_creturns_issue ON container_returns(issue_id)",
    ]:
        try:
            conn.execute(text(idx))
        except Exception as e:
            print(f"Index warn: {e}")


def _sqlite(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS container_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            order_id INTEGER,
            dispatch_id INTEGER,
            issue_date TEXT NOT NULL,
            status TEXT DEFAULT 'Issued',
            due_date TEXT,
            total_deposit REAL DEFAULT 0,
            refunded_amount REAL DEFAULT 0,
            forfeited_amount REAL DEFAULT 0,
            notes TEXT,
            created_by INTEGER,
            created_at TEXT,
            updated_at TEXT
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS container_issue_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER,
            container_id INTEGER,
            quantity_issued REAL DEFAULT 0,
            quantity_returned REAL DEFAULT 0,
            quantity_lost REAL DEFAULT 0,
            deposit_per_unit REAL DEFAULT 0,
            line_deposit REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS container_returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            return_number TEXT UNIQUE NOT NULL,
            issue_id INTEGER,
            customer_id INTEGER,
            return_date TEXT NOT NULL,
            status TEXT DEFAULT 'Received',
            refund_amount REAL DEFAULT 0,
            refund_status TEXT DEFAULT 'Pending',
            notes TEXT,
            received_by INTEGER,
            refunded_by INTEGER,
            refunded_at TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS container_return_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            return_id INTEGER,
            issue_item_id INTEGER,
            container_id INTEGER,
            quantity_returned REAL DEFAULT 0,
            quantity_lost REAL DEFAULT 0,
            loss_reason TEXT,
            deposit_per_unit REAL DEFAULT 0,
            refund_line REAL DEFAULT 0,
            forfeited_line REAL DEFAULT 0,
            created_at TEXT
        )
    """))
