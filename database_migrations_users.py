# =========================================================
# database_migrations_users.py
# User Management migrations
# =========================================================

from sqlalchemy import text
from database import _get_engine, get_is_cloud


def run_users_migrations():
    """Idempotent migrations for user management"""
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
        print("✅ User migrations complete")
        return True
    except Exception as e:
        print(f"❌ User migration error: {e}")
        return False


def _pg(conn):
    alters = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_ip VARCHAR(50)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS notes TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by INTEGER",
    ]
    for stmt in alters:
        try:
            conn.execute(text(stmt))
        except Exception as e:
            print(f"PG user alter warn: {e}")

    # Login history (optional but useful)
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS user_login_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            username VARCHAR(50),
            login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address VARCHAR(50),
            user_agent TEXT,
            success BOOLEAN DEFAULT TRUE,
            failure_reason VARCHAR(200)
        )
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_login_history_user
        ON user_login_history(user_id)
    """))


def _sqlite(conn):
    def add_col(table, col, typ):
        try:
            r = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            if col not in [row[1] for row in r]:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
        except Exception as e:
            print(f"SQLite add col warn: {e}")

    add_col("users", "must_change_password", "INTEGER DEFAULT 0")
    add_col("users", "password_changed_at", "TEXT")
    add_col("users", "failed_login_attempts", "INTEGER DEFAULT 0")
    add_col("users", "last_login_ip", "TEXT")
    add_col("users", "notes", "TEXT")
    add_col("users", "created_by", "INTEGER")

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS user_login_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            login_time TEXT,
            ip_address TEXT,
            user_agent TEXT,
            success INTEGER DEFAULT 1,
            failure_reason TEXT
        )
    """))
