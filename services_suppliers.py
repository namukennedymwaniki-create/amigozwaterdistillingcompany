# =========================================================
# services_suppliers.py
# Supplier Management Service Layer
# =========================================================
# Notes:
#   - Boolean columns (is_active) always coerced to Python True/False
#   - All list-returning functions return a pd.DataFrame (never None)
#   - Uses bind params + TRUE literals to be PostgreSQL-safe
# =========================================================

import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql


SUPPLIER_TYPES = ["Raw Material", "Packaging", "Equipment", "Services", "Logistics", "Other"]


# =========================================================
# HELPERS
# =========================================================
def _safe_df(df):
    """Guarantee a DataFrame is returned, never None."""
    if isinstance(df, pd.DataFrame):
        return df
    return pd.DataFrame()


# =========================================================
# CODE GENERATION
# =========================================================
def generate_supplier_code():
    """SUP-{SEQ}"""
    conn = get_db_connection()
    if not conn:
        return "SUP-0001"
    try:
        result = conn.execute(text("""
            SELECT supplier_code FROM suppliers
            WHERE supplier_code LIKE 'SUP-%'
            ORDER BY id DESC LIMIT 1
        """)).fetchone()
        if result and result[0]:
            try:
                num = int(result[0].split("-")[-1])
                return f"SUP-{str(num + 1).zfill(4)}"
            except Exception:
                return "SUP-0001"
        return "SUP-0001"
    except Exception:
        return "SUP-0001"
    finally:
        conn.close()


# =========================================================
# CREATE
# =========================================================
def create_supplier(supplier_name, contact_person=None, phone=None, email=None,
                    address=None, town=None, payment_terms="30 days",
                    tax_pin=None, notes=None):
    if not supplier_name:
        return False, "Supplier name required", None

    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None
    try:
        code = generate_supplier_code()
        result = conn.execute(text("""
            INSERT INTO suppliers (
                supplier_code, supplier_name, contact_person, phone, email,
                address, town, payment_terms, tax_pin, is_active, notes,
                created_at, updated_at
            ) VALUES (
                :code, :name, :contact, :phone, :email,
                :addr, :town, :terms, :pin, :active, :notes,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "code": code,
            "name": supplier_name.strip(),
            "contact": contact_person,
            "phone": phone,
            "email": email,
            "addr": address,
            "town": town,
            "terms": payment_terms,
            "pin": tax_pin,
            "active": True,          # Python bool
            "notes": notes,
        })
        supplier_id = result.fetchone()[0]
        conn.commit()
        log_audit("CREATE_SUPPLIER", "suppliers", supplier_id,
                  new_values={"supplier_code": code, "name": supplier_name})
        return True, f"✅ Supplier '{supplier_name}' created ({code})", supplier_id
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


# =========================================================
# UPDATE — coerces boolean columns
# =========================================================
def update_supplier(supplier_id, **kwargs):
    """
    Update supplier fields.
    Allowed: supplier_name, contact_person, phone, email, address, town,
             payment_terms, tax_pin, is_active, notes
    Boolean fields are coerced to Python True/False.
    """
    allowed = ["supplier_name", "contact_person", "phone", "email",
               "address", "town", "payment_terms", "tax_pin",
               "is_active", "notes"]
    boolean_fields = {"is_active"}

    updates, params = [], {"id": int(supplier_id)}

    for k, v in kwargs.items():
        if k in allowed:
            if k in boolean_fields:
                v = bool(v)          # ← forces Python True/False for psycopg
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
            f"UPDATE suppliers SET {', '.join(updates)} WHERE id = :id"
        ), params)
        conn.commit()
        log_audit("UPDATE_SUPPLIER", "suppliers", supplier_id, new_values=kwargs)
        return True, "✅ Supplier updated"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


# =========================================================
# DEACTIVATE / ACTIVATE
# =========================================================
def deactivate_supplier(supplier_id):
    return update_supplier(supplier_id, is_active=False)


def activate_supplier(supplier_id):
    return update_supplier(supplier_id, is_active=True)


# =========================================================
# READ
# =========================================================
def get_suppliers(search=None, active_only=True):
    """
    List suppliers.
    active_only=True → filter where is_active = TRUE (PostgreSQL-safe).
    """
    query = "SELECT * FROM suppliers WHERE 1=1"
    params = {}

    if active_only:
        query += " AND is_active = :active"
        params["active"] = True

    if search:
        query += " AND (LOWER(supplier_name) LIKE :s OR LOWER(supplier_code) LIKE :s)"
        params["s"] = f"%{search.lower()}%"

    query += " ORDER BY supplier_name"
    return _safe_df(read_sql(query, params if params else None))


def get_supplier(supplier_id):
    df = _safe_df(read_sql(
        "SELECT * FROM suppliers WHERE id = :id",
        {"id": int(supplier_id)}
    ))
    return None if df.empty else df.iloc[0]


# =========================================================
# COUNTS / UTILITIES
# =========================================================
def count_suppliers(active_only=True):
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        if active_only:
            return int(conn.execute(text(
                "SELECT COUNT(*) FROM suppliers WHERE is_active = :a"
            ), {"a": True}).scalar() or 0)
        return int(conn.execute(text("SELECT COUNT(*) FROM suppliers")).scalar() or 0)
    except Exception:
        return 0
    finally:
        conn.close()
