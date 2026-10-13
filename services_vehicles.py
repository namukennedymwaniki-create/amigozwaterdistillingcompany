# =========================================================
# services_vehicles.py
# Vehicle & Driver CRUD — Boolean-safe
# =========================================================

import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql


def _safe_df(df):
    if isinstance(df, pd.DataFrame):
        return df
    return pd.DataFrame()


# =========================================================
# VEHICLES
# =========================================================
def create_vehicle(plate_number, description=None, capacity_kg=0, notes=None):
    if not plate_number:
        return False, "Plate number required", None

    conn = get_db_connection()
    if not conn:
        return False, "DB connection failed", None
    try:
        existing = conn.execute(text(
            "SELECT id FROM vehicles WHERE LOWER(plate_number) = LOWER(:p)"
        ), {"p": plate_number.strip()}).fetchone()
        if existing:
            return False, f"Vehicle '{plate_number}' already exists", None

        result = conn.execute(text("""
            INSERT INTO vehicles (plate_number, description, capacity_kg, is_active, notes, created_at)
            VALUES (:plate, :desc, :cap, :active, :notes, CURRENT_TIMESTAMP)
            RETURNING id
        """), {
            "plate": plate_number.strip().upper(),
            "desc": description,
            "cap": float(capacity_kg or 0),
            "active": True,
            "notes": notes,
        })
        vehicle_id = result.fetchone()[0]
        conn.commit()
        log_audit("CREATE_VEHICLE", "vehicles", vehicle_id,
                  new_values={"plate_number": plate_number})
        return True, f"✅ Vehicle {plate_number} created", vehicle_id
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


def get_vehicles(active_only=True):
    query = "SELECT * FROM vehicles WHERE 1=1"
    params = {}
    if active_only:
        query += " AND is_active = :active"
        params["active"] = True
    query += " ORDER BY plate_number"
    return _safe_df(read_sql(query, params if params else None))


def update_vehicle(vehicle_id, **kwargs):
    allowed = ["plate_number", "description", "capacity_kg", "is_active", "notes"]
    boolean_fields = {"is_active"}
    updates, params = [], {"id": int(vehicle_id)}

    for k, v in kwargs.items():
        if k in allowed:
            if k in boolean_fields:
                v = bool(v)
            updates.append(f"{k} = :{k}")
            params[k] = v

    if not updates:
        return False, "No valid fields"

    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    try:
        conn.execute(text(
            f"UPDATE vehicles SET {', '.join(updates)} WHERE id = :id"
        ), params)
        conn.commit()
        log_audit("UPDATE_VEHICLE", "vehicles", vehicle_id, new_values=kwargs)
        return True, "✅ Vehicle updated"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


# =========================================================
# DRIVERS
# =========================================================
def create_driver(name, phone=None, license_number=None, notes=None):
    if not name:
        return False, "Driver name required", None

    conn = get_db_connection()
    if not conn:
        return False, "DB connection failed", None
    try:
        result = conn.execute(text("""
            INSERT INTO drivers (name, phone, license_number, is_active, notes, created_at)
            VALUES (:name, :phone, :lic, :active, :notes, CURRENT_TIMESTAMP)
            RETURNING id
        """), {
            "name": name.strip(),
            "phone": phone,
            "lic": license_number,
            "active": True,
            "notes": notes,
        })
        driver_id = result.fetchone()[0]
        conn.commit()
        log_audit("CREATE_DRIVER", "drivers", driver_id, new_values={"name": name})
        return True, f"✅ Driver {name} created", driver_id
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


def get_drivers(active_only=True):
    query = "SELECT * FROM drivers WHERE 1=1"
    params = {}
    if active_only:
        query += " AND is_active = :active"
        params["active"] = True
    query += " ORDER BY name"
    return _safe_df(read_sql(query, params if params else None))


def update_driver(driver_id, **kwargs):
    allowed = ["name", "phone", "license_number", "is_active", "notes"]
    boolean_fields = {"is_active"}
    updates, params = [], {"id": int(driver_id)}

    for k, v in kwargs.items():
        if k in allowed:
            if k in boolean_fields:
                v = bool(v)
            updates.append(f"{k} = :{k}")
            params[k] = v

    if not updates:
        return False, "No valid fields"

    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    try:
        conn.execute(text(
            f"UPDATE drivers SET {', '.join(updates)} WHERE id = :id"
        ), params)
        conn.commit()
        log_audit("UPDATE_DRIVER", "drivers", driver_id, new_values=kwargs)
        return True, "✅ Driver updated"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()
