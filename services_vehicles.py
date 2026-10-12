# =========================================================
# services_vehicles.py
# Vehicle & Driver CRUD
# =========================================================

import streamlit as st
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql


# =========================================================
# VEHICLES
# =========================================================
def create_vehicle(plate_number, description=None, capacity_kg=0, notes=None):
    """Create a new vehicle"""
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
            VALUES (:plate, :desc, :cap, 1, :notes, CURRENT_TIMESTAMP)
            RETURNING id
        """), {
            "plate": plate_number.strip().upper(),
            "desc": description,
            "cap": capacity_kg,
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
    """List vehicles"""
    query = "SELECT * FROM vehicles WHERE 1=1"
    if active_only:
        query += " AND is_active = 1"
    query += " ORDER BY plate_number"
    return read_sql(query)


def update_vehicle(vehicle_id, **kwargs):
    """Update vehicle"""
    allowed = ["plate_number", "description", "capacity_kg", "is_active", "notes"]
    updates = []
    params = {"id": vehicle_id}
    
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
        conn.execute(text(f"UPDATE vehicles SET {', '.join(updates)} WHERE id = :id"), params)
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
    """Create a new driver"""
    if not name:
        return False, "Driver name required", None
    
    conn = get_db_connection()
    if not conn:
        return False, "DB connection failed", None
    
    try:
        result = conn.execute(text("""
            INSERT INTO drivers (name, phone, license_number, is_active, notes, created_at)
            VALUES (:name, :phone, :lic, 1, :notes, CURRENT_TIMESTAMP)
            RETURNING id
        """), {
            "name": name.strip(),
            "phone": phone,
            "lic": license_number,
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
    """List drivers"""
    query = "SELECT * FROM drivers WHERE 1=1"
    if active_only:
        query += " AND is_active = 1"
    query += " ORDER BY name"
    return read_sql(query)


def update_driver(driver_id, **kwargs):
    """Update driver"""
    allowed = ["name", "phone", "license_number", "is_active", "notes"]
    updates = []
    params = {"id": driver_id}
    
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
        conn.execute(text(f"UPDATE drivers SET {', '.join(updates)} WHERE id = :id"), params)
        conn.commit()
        log_audit("UPDATE_DRIVER", "drivers", driver_id, new_values=kwargs)
        return True, "✅ Driver updated"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()
