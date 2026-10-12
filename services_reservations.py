# =========================================================
# services_reservations.py
# Stock Reservation Service Layer
# =========================================================

import streamlit as st
from datetime import datetime, date, timedelta
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql
from services_inventory import get_stock_balance, generate_reference


def get_reserved_quantity(product_id, warehouse_id=None, batch_id=None):
    """Total quantity currently reserved (active) for a product"""
    conn = get_db_connection()
    if not conn:
        return 0
    
    try:
        query = """
            SELECT COALESCE(SUM(quantity), 0)
            FROM stock_reservations
            WHERE product_id = :pid AND status = 'Active'
        """
        params = {"pid": product_id}
        
        if warehouse_id is not None:
            query += " AND warehouse_id = :wid"
            params["wid"] = warehouse_id
        
        if batch_id is not None:
            query += " AND batch_id = :bid"
            params["bid"] = batch_id
        
        result = conn.execute(text(query), params).scalar()
        return float(result or 0)
    except Exception as e:
        print(f"Reserved qty error: {e}")
        return 0
    finally:
        conn.close()


def get_available_after_reservations(product_id, warehouse_id=None):
    """
    Available = physical stock - active reservations
    (Note: this ignores batch status; for sellable use services_quality.get_available_stock)
    """
    physical = get_stock_balance(product_id, warehouse_id)
    reserved = get_reserved_quantity(product_id, warehouse_id)
    return max(0, physical - reserved)


def create_reservation(product_id, quantity, warehouse_id=None, batch_id=None,
                       reference_id=None, reference_table=None, reference_number=None,
                       reserved_for=None, expires_days=7, notes=None):
    """Create a stock reservation"""
    if quantity <= 0:
        return False, "Quantity must be positive", None
    
    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None
    
    try:
        rsv_number = generate_reference("RSV")
        
        expires_at = datetime.now() + timedelta(days=expires_days)
        
        result = conn.execute(text("""
            INSERT INTO stock_reservations (
                reservation_number, product_id, warehouse_id, batch_id, quantity,
                reference_id, reference_table, reference_number, reserved_for,
                status, expires_at, notes, created_by, created_at
            ) VALUES (
                :rnum, :pid, :wid, :bid, :qty,
                :rid, :rtable, :rnum2, :rfor,
                'Active', :exp, :notes, :uid, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "rnum": rsv_number,
            "pid": product_id,
            "wid": warehouse_id,
            "bid": batch_id,
            "qty": quantity,
            "rid": reference_id,
            "rtable": reference_table,
            "rnum2": reference_number,
            "rfor": reserved_for,
            "exp": expires_at,
            "notes": notes,
            "uid": st.session_state.get('user_id'),
        })
        
        rsv_id = result.fetchone()[0]
        conn.commit()
        
        log_audit("CREATE_RESERVATION", "stock_reservations", rsv_id,
                  new_values={"product_id": product_id, "quantity": quantity,
                              "reservation_number": rsv_number})
        
        return True, f"✅ Reserved {quantity} units ({rsv_number})", rsv_id
    
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


def release_reservation(reservation_id, reason=None):
    """Release (cancel) a reservation"""
    if not reason:
        reason = "Manual release"
    
    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    
    try:
        conn.execute(text("""
            UPDATE stock_reservations
            SET status = 'Released',
                released_at = CURRENT_TIMESTAMP,
                released_reason = :reason
            WHERE id = :id AND status = 'Active'
        """), {"id": reservation_id, "reason": reason})
        
        conn.commit()
        log_audit("RELEASE_RESERVATION", "stock_reservations", reservation_id,
                  new_values={"reason": reason})
        
        return True, "✅ Reservation released"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


def release_reservations_for_reference(reference_table, reference_id, reason="Cancelled"):
    """Release all active reservations for a document (e.g., sales order)"""
    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    
    try:
        result = conn.execute(text("""
            UPDATE stock_reservations
            SET status = 'Released',
                released_at = CURRENT_TIMESTAMP,
                released_reason = :reason
            WHERE reference_table = :rtable 
              AND reference_id = :rid
              AND status = 'Active'
        """), {"rtable": reference_table, "rid": reference_id, "reason": reason})
        
        count = result.rowcount
        conn.commit()
        log_audit("BULK_RELEASE_RESERVATIONS", "stock_reservations", reference_id,
                  new_values={"reference_table": reference_table, "released_count": count})
        
        return True, f"✅ Released {count} reservation(s)"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


def get_active_reservations(product_id=None, reference_table=None, reference_id=None):
    """List active reservations"""
    query = """
        SELECT 
            sr.id,
            sr.reservation_number,
            sr.product_id,
            p.product_code,
            p.product_name,
            p.unit,
            sr.warehouse_id,
            w.code as warehouse_code,
            w.name as warehouse_name,
            sr.batch_id,
            pb.batch_number,
            sr.quantity,
            sr.reference_table,
            sr.reference_number,
            sr.reserved_for,
            sr.expires_at,
            sr.created_at
        FROM stock_reservations sr
        JOIN products p ON sr.product_id = p.id
        LEFT JOIN warehouses w ON sr.warehouse_id = w.id
        LEFT JOIN product_batches pb ON sr.batch_id = pb.id
        WHERE sr.status = 'Active'
    """
    params = {}
    
    if product_id:
        query += " AND sr.product_id = :pid"
        params["pid"] = product_id
    
    if reference_table:
        query += " AND sr.reference_table = :rtable"
        params["rtable"] = reference_table
    
    if reference_id:
        query += " AND sr.reference_id = :rid"
        params["rid"] = reference_id
    
    query += " ORDER BY sr.id DESC"
    
    return read_sql(query, params if params else None)


def expire_old_reservations():
    """Auto-release reservations past their expiry"""
    conn = get_db_connection()
    if not conn:
        return 0
    
    try:
        result = conn.execute(text("""
            UPDATE stock_reservations
            SET status = 'Expired',
                released_at = CURRENT_TIMESTAMP,
                released_reason = 'Auto-expired'
            WHERE status = 'Active'
              AND expires_at < CURRENT_TIMESTAMP
        """))
        
        count = result.rowcount
        conn.commit()
        return count
    except Exception as e:
        conn.rollback()
        print(f"Expiry error: {e}")
        return 0
    finally:
        conn.close()
