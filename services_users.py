# =========================================================
# services_users.py
# User & Role Management Service Layer
# =========================================================

import hashlib
import secrets
import string
import streamlit as st
from datetime import datetime, date
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql
import pandas as pd

def _safe_df(df):
    """Guarantee a DataFrame is returned, never None."""
    if isinstance(df, pd.DataFrame):
        return df
    return pd.DataFrame()

# Must match streamlit_app.py hash_password()
_SALT = "amigoz_secure_salt_2024"


def _hash(password):
    return hashlib.sha256((_SALT + password).encode()).hexdigest()


def verify_password(password, hashed):
    return _hash(password) == hashed


def generate_temp_password(length=10):
    """Generate a random temporary password"""
    alphabet = string.ascii_letters + string.digits + "!@#$"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# =========================================================
# USERS
# =========================================================
# =========================================================
# USERS
# =========================================================
def get_users(search=None, role_id=None, active_only=False):
    query = """
        SELECT 
            u.id, u.username, u.email, u.first_name, u.last_name,
            u.phone, u.role_id, u.is_active, u.is_superuser,
            u.must_change_password, u.last_login, u.created_at,
            r.name as role_name
        FROM users u
        LEFT JOIN roles r ON u.role_id = r.id
        WHERE 1=1
    """
    params = {}
    if active_only:
        query += " AND u.is_active = :active"
        params["active"] = True
    if role_id:
        query += " AND u.role_id = :rid"
        params["rid"] = role_id
    if search:
        query += """ AND (
            LOWER(u.username) LIKE :s
            OR LOWER(u.email) LIKE :s
            OR LOWER(u.first_name) LIKE :s
            OR LOWER(u.last_name) LIKE :s
        )"""
        params["s"] = f"%{search.lower()}%"
    query += " ORDER BY u.id DESC"
    return _safe_df(read_sql(query, params if params else None))


def get_user(user_id):
    df = _safe_df(read_sql("""
        SELECT u.*, r.name as role_name
        FROM users u
        LEFT JOIN roles r ON u.role_id = r.id
        WHERE u.id = :id
    """, {"id": user_id}))
    return None if df.empty else df.iloc[0]


def get_user_by_username(username):
    df = _safe_df(read_sql("""
        SELECT u.*, r.name as role_name
        FROM users u
        LEFT JOIN roles r ON u.role_id = r.id
        WHERE LOWER(u.username) = LOWER(:u)
    """, {"u": username}))
    return None if df.empty else df.iloc[0]


def create_user(username, email=None, password=None, first_name=None,
                last_name=None, phone=None, role_id=None, is_superuser=False,
                must_change_password=True, notes=None):
    """Create a new user. If password is None, generates a temp password."""
    if not username:
        return False, "Username required", None, None

    if not password:
        password = generate_temp_password()

    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None, None
    try:
        existing = conn.execute(text(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(:u)"
        ), {"u": username.strip()}).fetchone()
        if existing:
            return False, f"Username '{username}' already exists", None, None

        result = conn.execute(text("""
            INSERT INTO users (
                username, email, password_hash, first_name, last_name,
                phone, role_id, is_active, is_superuser,
                must_change_password, notes, created_by,
                created_at, updated_at
            ) VALUES (
                :u, :e, :p, :fn, :ln,
                :ph, :rid, :active, :su,
                :mcp, :notes, :by,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "u": username.strip(),
            "e": email,
            "p": _hash(password),
            "fn": first_name,
            "ln": last_name,
            "ph": phone,
            "rid": role_id,
            "active": True,
            "su": is_superuser,
            "mcp": must_change_password,
            "notes": notes,
            "by": st.session_state.get('user_id'),
        })
        user_id = result.fetchone()[0]
        conn.commit()

        log_audit("CREATE_USER", "users", user_id,
                  new_values={"username": username, "role_id": role_id})

        return True, f"✅ User '{username}' created", user_id, password
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None, None
    finally:
        conn.close()


def update_user(user_id, **kwargs):
    """Update user fields."""
    allowed = ["email", "first_name", "last_name", "phone",
               "role_id", "is_active", "is_superuser", "notes"]
    updates = []
    params = {"id": user_id}

    for k, v in kwargs.items():
        if k in allowed:
            if k in ("is_active", "is_superuser"):
                v = bool(v)
            updates.append(f"{k} = :{k}")
            params[k] = v

    if not updates:
        return False, "No valid fields"

    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    try:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        conn.execute(text(
            f"UPDATE users SET {', '.join(updates)} WHERE id = :id"
        ), params)
        conn.commit()
        log_audit("UPDATE_USER", "users", user_id, new_values=kwargs)
        return True, "✅ User updated"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


def deactivate_user(user_id):
    """Soft-delete: set is_active = False"""
    if user_id == st.session_state.get('user_id'):
        return False, "You cannot deactivate your own account"
    return update_user(user_id, is_active=False)


def activate_user(user_id):
    return update_user(user_id, is_active=True)


def reset_password(user_id, new_password=None, must_change=True):
    """Reset a user's password. If new_password is None, generates temp."""
    if not new_password:
        new_password = generate_temp_password()

    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None
    try:
        conn.execute(text("""
            UPDATE users
            SET password_hash = :p,
                must_change_password = :mcp,
                password_changed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {"p": _hash(new_password), "mcp": must_change, "id": user_id})
        conn.commit()

        log_audit("RESET_PASSWORD", "users", user_id)
        return True, "✅ Password reset", new_password
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}", None
    finally:
        conn.close()


def change_own_password(user_id, old_password, new_password):
    """User changes their own password."""
    if not old_password or not new_password:
        return False, "Both old and new passwords required"
    if len(new_password) < 6:
        return False, "New password must be at least 6 characters"

    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    try:
        row = conn.execute(text(
            "SELECT password_hash FROM users WHERE id = :id"
        ), {"id": user_id}).fetchone()
        if not row:
            return False, "User not found"
        if not verify_password(old_password, row[0]):
            return False, "Current password is incorrect"

        conn.execute(text("""
            UPDATE users
            SET password_hash = :p,
                must_change_password = FALSE,
                password_changed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {"p": _hash(new_password), "id": user_id})
        conn.commit()

        log_audit("CHANGE_PASSWORD", "users", user_id)
        return True, "✅ Password changed"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


def touch_login(user_id, ip=None, user_agent=None, success=True, reason=None):
    """Record a login attempt"""
    conn = get_db_connection()
    if not conn:
        return
    try:
        username_row = conn.execute(text(
            "SELECT username FROM users WHERE id = :id"
        ), {"id": user_id}).fetchone()
        username = username_row[0] if username_row else None

        conn.execute(text("""
            INSERT INTO user_login_history (
                user_id, username, ip_address, user_agent, success, failure_reason
            ) VALUES (:id, :u, :ip, :ua, :ok, :r)
        """), {
            "id": user_id, "u": username, "ip": ip, "ua": user_agent,
            "ok": success, "r": reason,
        })

        if success:
            conn.execute(text("""
                UPDATE users
                SET last_login = CURRENT_TIMESTAMP,
                    last_login_ip = :ip,
                    failed_login_attempts = 0
                WHERE id = :id
            """), {"id": user_id, "ip": ip})
        else:
            conn.execute(text("""
                UPDATE users
                SET failed_login_attempts = COALESCE(failed_login_attempts, 0) + 1
                WHERE id = :id
            """), {"id": user_id})

        conn.commit()
    except Exception as e:
        print(f"Login touch error: {e}")
    finally:
        conn.close()


# =========================================================
# ROLES
# =========================================================
def get_roles(active_only=True):
    query = "SELECT * FROM roles WHERE 1=1"
    params = {}
    if active_only:
        query += " AND is_active = :active"
        params["active"] = True
    query += " ORDER BY name"
    return read_sql(query, params if params else None)


def get_role(role_id):
    df = read_sql("SELECT * FROM roles WHERE id = :id", {"id": role_id})
    return None if df.empty else df.iloc[0]


def create_role(name, description=None):
    if not name:
        return False, "Role name required", None

    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None
    try:
        existing = conn.execute(text(
            "SELECT id FROM roles WHERE LOWER(name) = LOWER(:n)"
        ), {"n": name.strip()}).fetchone()
        if existing:
            return False, f"Role '{name}' already exists", None

        result = conn.execute(text("""
            INSERT INTO roles (name, description, is_active, created_at)
            VALUES (:n, :d, :active, CURRENT_TIMESTAMP)
            RETURNING id
        """), {"n": name.strip(), "d": description, "active": True})
        role_id = result.fetchone()[0]
        conn.commit()

        log_audit("CREATE_ROLE", "roles", role_id, new_values={"name": name})
        return True, f"✅ Role '{name}' created", role_id
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}", None
    finally:
        conn.close()


def update_role(role_id, **kwargs):
    allowed = ["name", "description", "is_active"]
    updates = []
    params = {"id": role_id}
    for k, v in kwargs.items():
        if k in allowed:
            updates.append(f"{k} = :{k}")
            params[k] = v
    if not updates:
        return False, "No valid fields"

    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    try:
        conn.execute(text(
            f"UPDATE roles SET {', '.join(updates)} WHERE id = :id"
        ), params)
        conn.commit()
        log_audit("UPDATE_ROLE", "roles", role_id, new_values=kwargs)
        return True, "✅ Role updated"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


def get_users_count_by_role():
    return read_sql("""
        SELECT r.name as role_name, COUNT(u.id) as user_count
        FROM roles r
        LEFT JOIN users u ON u.role_id = r.id AND u.is_active = TRUE
        GROUP BY r.name
        ORDER BY r.name
    """)


# =========================================================
# PER-USER ACTIVITY
# =========================================================
def get_user_activity(user_id, limit=50):
    df = read_sql("""
        SELECT timestamp, action, table_name, record_id
        FROM audit_logs
        WHERE user_id = :id
        ORDER BY timestamp DESC
        LIMIT :lim
    """, {"id": user_id, "lim": limit})
    return df


def get_user_login_history(user_id, limit=30):
    return read_sql("""
        SELECT login_time, ip_address, success, failure_reason
        FROM user_login_history
        WHERE user_id = :id
        ORDER BY login_time DESC
        LIMIT :lim
    """, {"id": user_id, "lim": limit})
