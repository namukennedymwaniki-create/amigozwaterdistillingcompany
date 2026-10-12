# =========================================================
# services_quality.py
# Batch & Quality Control Service Layer
# =========================================================
# Batch statuses:
#   Released    - Safe for sale
#   Quarantined - Awaiting QC
#   Rejected    - Failed QC
#   Expired     - Past expiry date
#   Recalled    - Withdrawn from market
# =========================================================

import streamlit as st
from datetime import datetime, date, timedelta
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql
from services_inventory import post_movement, get_stock_balance, generate_reference


# =========================================================
# CONSTANTS
# =========================================================
BATCH_STATUSES = ["Released", "Quarantined", "Rejected", "Expired", "Recalled"]
DEFAULT_NEW_BATCH_STATUS = "Quarantined"
EXPIRY_WARNING_DAYS = 90


# =========================================================
# GENERATE BATCH NUMBER
# =========================================================
def generate_batch_number(product_code):
    """
    Generate unique batch number: {PRODUCT_CODE}-{YYYYMMDD}-{SEQ}
    Example: BW-500ML-20261013-001
    """
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"{product_code}-{today}"
        
        result = conn.execute(text("""
            SELECT batch_number FROM product_batches
            WHERE batch_number LIKE :pat
            ORDER BY id DESC LIMIT 1
        """), {"pat": f"{prefix}-%"}).fetchone()
        
        if result and result[0]:
            try:
                seq = int(result[0].split("-")[-1])
                return f"{prefix}-{str(seq + 1).zfill(3)}"
            except:
                return f"{prefix}-001"
        return f"{prefix}-001"
    except:
        return None
    finally:
        conn.close()


# =========================================================
# CREATE BATCH
# =========================================================
def create_batch(product_id, batch_number=None, production_date=None,
                 expiry_date=None, quantity=0, warehouse_id=None,
                 status=DEFAULT_NEW_BATCH_STATUS, notes=None, unit_cost=0):
    """
    Create a new batch. Optionally post opening movement.
    
    Returns: (success: bool, message: str, batch_id: int | None)
    """
    conn = get_db_connection()
    if not conn:
        return False, "DB connection failed", None
    
    try:
        # Get product code for batch number generation
        product = conn.execute(text(
            "SELECT product_code, product_name, is_batch_tracked FROM products WHERE id = :pid"
        ), {"pid": product_id}).fetchone()
        
        if not product:
            conn.close()
            return False, "Product not found", None
        
        product_code = product[0]
        product_name = product[1]
        is_batch_tracked = product[2]
        
        if not is_batch_tracked:
            conn.close()
            return False, f"Product '{product_name}' is not batch-tracked. Enable batch tracking in Products.", None
        
        # Auto-generate batch number if not provided
        if not batch_number:
            conn.close()
            batch_number = generate_batch_number(product_code)
            if not batch_number:
                return False, "Failed to generate batch number", None
            conn = get_db_connection()
        
        # Check duplicate
        existing = conn.execute(text(
            "SELECT id FROM product_batches WHERE batch_number = :bn"
        ), {"bn": batch_number}).fetchone()
        
        if existing:
            conn.close()
            return False, f"Batch number '{batch_number}' already exists", None
        
        # Validate status
        if status not in BATCH_STATUSES:
            conn.close()
            return False, f"Invalid status: {status}", None
        
        # Insert batch
        result = conn.execute(text("""
            INSERT INTO product_batches (
                batch_number, product_id, production_date, expiry_date,
                quality_status, quantity_produced, notes,
                created_at, updated_at
            ) VALUES (
                :bn, :pid, :pd, :ed, :status, :qty, :notes,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "bn": batch_number,
            "pid": product_id,
            "pd": production_date,
            "ed": expiry_date,
            "status": status,
            "qty": quantity,
            "notes": notes,
        })
        
        batch_id = result.fetchone()[0]
        conn.commit()
        conn.close()
        
        # Post opening movement if quantity > 0
        if quantity > 0 and warehouse_id:
            ref = generate_reference("BATCH")
            ok, msg, _ = post_movement(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity_change=quantity,
                movement_type="OPENING",
                reference_number=ref,
                batch_id=batch_id,
                unit_cost=unit_cost,
                reason=f"Batch {batch_number} initial quantity",
            )
            if not ok:
                return True, f"Batch created but movement failed: {msg}", batch_id
        
        log_audit("CREATE_BATCH", "product_batches", batch_id,
                  new_values={"batch_number": batch_number, "product_id": product_id,
                              "quantity": quantity, "status": status})
        
        return True, f"✅ Batch {batch_number} created with status '{status}'", batch_id
    
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except:
            pass
        return False, f"Error: {str(e)}", None


# =========================================================
# CHANGE BATCH STATUS
# =========================================================
def change_batch_status(batch_id, new_status, reason=None):
    """
    Change the quality status of a batch. Logs to audit.
    """
    if new_status not in BATCH_STATUSES:
        return False, f"Invalid status: {new_status}"
    
    if not reason:
        return False, "Reason is required for status change"
    
    conn = get_db_connection()
    if not conn:
        return False, "DB connection failed"
    
    try:
        # Get current
        current = conn.execute(text("""
            SELECT batch_number, quality_status FROM product_batches WHERE id = :id
        """), {"id": batch_id}).fetchone()
        
        if not current:
            conn.close()
            return False, "Batch not found"
        
        old_status = current[1]
        
        if old_status == new_status:
            conn.close()
            return False, f"Batch is already '{new_status}'"
        
        conn.execute(text("""
            UPDATE product_batches 
            SET quality_status = :status, updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {"status": new_status, "id": batch_id})
        
        conn.commit()
        conn.close()
        
        log_audit(
            action="BATCH_STATUS_CHANGE",
            table_name="product_batches",
            record_id=batch_id,
            old_values={"status": old_status, "batch_number": current[0]},
            new_values={"status": new_status, "reason": reason},
        )
        
        return True, f"✅ Batch {current[0]} → {new_status}"
    
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except:
            pass
        return False, f"Error: {str(e)}"


# =========================================================
# GET BATCHES
# =========================================================
def get_batches(product_id=None, status_filter=None, include_expired=True):
    """
    Fetch batches with filters.
    Auto-flags expired batches.
    """
    today = date.today()
    
    query = """
        SELECT 
            pb.id,
            pb.batch_number,
            p.product_code,
            p.product_name,
            p.unit,
            pb.production_date,
            pb.expiry_date,
            pb.quality_status,
            pb.quantity_produced,
            pb.notes,
            pb.created_at,
            CASE 
                WHEN pb.expiry_date IS NOT NULL 
                     AND pb.expiry_date < :today 
                THEN TRUE 
                ELSE FALSE 
            END as is_expired,
            CASE 
                WHEN pb.expiry_date IS NOT NULL 
                     AND pb.expiry_date >= :today 
                     AND pb.expiry_date <= :warning 
                THEN TRUE 
                ELSE FALSE 
            END as is_expiring_soon
        FROM product_batches pb
        JOIN products p ON pb.product_id = p.id
        WHERE 1=1
    """
    
    params = {
        "today": today,
        "warning": today + timedelta(days=EXPIRY_WARNING_DAYS),
    }
    
    if product_id:
        query += " AND pb.product_id = :pid"
        params["pid"] = product_id
    
    if status_filter and status_filter != "All":
        if status_filter == "Expired (auto)":
            query += " AND pb.expiry_date < :today"
        else:
            query += " AND pb.quality_status = :status"
            params["status"] = status_filter
    
    query += " ORDER BY pb.id DESC"
    
    return read_sql(query, params)


# =========================================================
# GET BATCH BY ID
# =========================================================
def get_batch(batch_id):
    """Get single batch details"""
    df = read_sql("""
        SELECT 
            pb.*,
            p.product_code,
            p.product_name,
            p.unit
        FROM product_batches pb
        JOIN products p ON pb.product_id = p.id
        WHERE pb.id = :id
    """, {"id": batch_id})
    
    if df.empty:
        return None
    return df.iloc[0]


# =========================================================
# GET AVAILABLE STOCK (Batch-Aware)
# =========================================================
def get_available_stock(product_id, warehouse_id=None, include_unbatched=True):
    """
    Calculate ONLY sellable stock:
    - Non-batch-tracked products: all stock
    - Batch-tracked products: only Released + non-expired batches
    """
    conn = get_db_connection()
    if not conn:
        return 0
    
    try:
        # Check if product is batch-tracked
        product = conn.execute(text(
            "SELECT is_batch_tracked FROM products WHERE id = :pid"
        ), {"pid": product_id}).fetchone()
        
        if not product:
            conn.close()
            return 0
        
        is_batch_tracked = product[0]
        
        # If NOT batch-tracked, return total stock
        if not is_batch_tracked:
            conn.close()
            return get_stock_balance(product_id, warehouse_id)
        
        # Batch-tracked: sum only Released + non-expired
        today = date.today()
        
        query = """
            SELECT COALESCE(SUM(sm.quantity_change), 0) as balance
            FROM stock_movements sm
            JOIN product_batches pb ON sm.batch_id = pb.id
            WHERE sm.product_id = :pid
              AND sm.is_posted = 1
              AND pb.quality_status = 'Released'
              AND (pb.expiry_date IS NULL OR pb.expiry_date >= :today)
        """
        params = {"pid": product_id, "today": today}
        
        if warehouse_id is not None:
            query += " AND sm.warehouse_id = :wid"
            params["wid"] = warehouse_id
        
        result = conn.execute(text(query), params).scalar()
        conn.close()
        return float(result or 0)
    
    except Exception as e:
        try:
            conn.close()
        except:
            pass
        print(f"Available stock error: {e}")
        return 0


# =========================================================
# EXPIRY MONITOR
# =========================================================
def get_expiring_batches(days_ahead=EXPIRY_WARNING_DAYS):
    """Get batches expiring within N days"""
    today = date.today()
    threshold = today + timedelta(days=days_ahead)
    
    return read_sql("""
        SELECT 
            pb.id,
            pb.batch_number,
            p.product_code,
            p.product_name,
            p.unit,
            pb.expiry_date,
            pb.quality_status,
            (pb.expiry_date - :today) as days_until_expiry,
            CASE 
                WHEN pb.expiry_date < :today THEN 'Expired'
                WHEN pb.expiry_date < :today + INTERVAL '30 days' THEN 'Critical'
                WHEN pb.expiry_date < :today + INTERVAL '60 days' THEN 'Warning'
                ELSE 'Notice'
            END as severity
        FROM product_batches pb
        JOIN products p ON pb.product_id = p.id
        WHERE pb.expiry_date IS NOT NULL
          AND pb.expiry_date <= :threshold
          AND pb.quality_status NOT IN ('Rejected', 'Recalled', 'Expired')
        ORDER BY pb.expiry_date ASC
    """, {"today": today, "threshold": threshold})


# =========================================================
# BATCH SUMMARY FOR A PRODUCT
# =========================================================
def get_batch_summary(product_id):
    """Get summary of all batches for a product"""
    return read_sql("""
        SELECT 
            quality_status,
            COUNT(*) as batch_count,
            COALESCE(SUM(quantity_produced), 0) as total_quantity
        FROM product_batches
        WHERE product_id = :pid
        GROUP BY quality_status
        ORDER BY quality_status
    """, {"pid": product_id})


# =========================================================
# CHECK IF BATCH IS SELLABLE
# =========================================================
def is_batch_sellable(batch_id):
    """Check if a batch is sellable (Released + not expired)"""
    today = date.today()
    df = read_sql("""
        SELECT quality_status, expiry_date
        FROM product_batches
        WHERE id = :id
    """, {"id": batch_id})
    
    if df.empty:
        return False, "Batch not found"
    
    status = df.iloc[0]['quality_status']
    expiry = df.iloc[0]['expiry_date']
    
    if status != "Released":
        return False, f"Batch status is '{status}', not 'Released'"
    
    if expiry is not None:
        try:
            if isinstance(expiry, str):
                exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            else:
                exp_date = expiry
            if exp_date < today:
                return False, f"Batch expired on {exp_date}"
        except:
            pass
    
    return True, "Batch is sellable"
