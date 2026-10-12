# =========================================================
# services_inventory.py
# Inventory Service Layer — Stock Ledger Operations
# =========================================================
# ALL stock changes MUST go through this module.
# Never UPDATE a stock balance directly — always post a movement.
# =========================================================

import streamlit as st
from datetime import datetime, date
from sqlalchemy import text
from database import get_db_connection, log_audit, get_is_cloud


# =========================================================
# MOVEMENT TYPES
# =========================================================
MOVEMENT_TYPES = {
    "OPENING": "Opening Stock",
    "RECEIPT": "Goods Received (Purchase)",
    "PRODUCTION": "Production Output",
    "TRANSFER_OUT": "Transfer Out",
    "TRANSFER_IN": "Transfer In",
    "ISSUE": "Issued to Customer",
    "DISPATCH": "Dispatched",
    "ADJUSTMENT_UP": "Adjustment (Increase)",
    "ADJUSTMENT_DOWN": "Adjustment (Decrease)",
    "DAMAGE": "Damaged Goods",
    "RETURN": "Customer Return",
}


# =========================================================
# CORE: POST A STOCK MOVEMENT
# =========================================================
def post_movement(product_id, warehouse_id, quantity_change, movement_type,
                  reference_number=None, batch_id=None, unit_cost=0,
                  reason=None, reference_id=None, reference_table=None,
                  movement_date=None):
    """
    The ONLY way to change stock.
    
    quantity_change: 
        Positive = INCREASE stock
        Negative = DECREASE stock
    
    Returns:
        (success: bool, message: str, movement_id: int | None)
    """
    conn = get_db_connection()
    if not conn:
        return False, "Database connection failed", None
    
    try:
        if movement_type not in MOVEMENT_TYPES:
            return False, f"Invalid movement type: {movement_type}", None
        
        if quantity_change == 0:
            return False, "Quantity change cannot be zero", None
        
        movement_date = movement_date or date.today()
        
        # ============================================
        # VALIDATION: Prevent negative stock
        # ============================================
        if quantity_change < 0:
            current_balance = get_stock_balance(
                product_id=product_id,
                warehouse_id=warehouse_id,
                batch_id=batch_id,
                conn=conn
            )
            if current_balance + quantity_change < 0:
                return False, (
                    f"Insufficient stock. Available: {current_balance}, "
                    f"Requested: {abs(quantity_change)}"
                ), None
        
        # ============================================
        # CALCULATE BALANCE AFTER
        # ============================================
        current = get_stock_balance(
            product_id=product_id,
            warehouse_id=warehouse_id,
            batch_id=batch_id,
            conn=conn
        )
        balance_after = current + quantity_change
        
        # ============================================
        # INSERT MOVEMENT
        # ============================================
        user_id = st.session_state.get('user_id')
        
        result = conn.execute(text("""
            INSERT INTO stock_movements (
                movement_date, movement_type, reference_number,
                product_id, batch_id, warehouse_id,
                quantity_change, unit_cost, balance_after,
                reason, reference_id, reference_table,
                created_by, is_posted, created_at
            ) VALUES (
                :mdate, :mtype, :ref,
                :pid, :bid, :wid,
                :qty, :cost, :balance,
                :reason, :refid, :reftable,
                :uid, 1, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "mdate": movement_date,
            "mtype": movement_type,
            "ref": reference_number,
            "pid": product_id,
            "bid": batch_id,
            "wid": warehouse_id,
            "qty": quantity_change,
            "cost": unit_cost,
            "balance": balance_after,
            "reason": reason,
            "refid": reference_id,
            "reftable": reference_table,
            "uid": user_id,
        })
        
        movement_id = result.fetchone()[0]
        conn.commit()
        
        # Audit
        log_audit(
            action=f"STOCK_MOVEMENT_{movement_type}",
            table_name="stock_movements",
            record_id=movement_id,
            new_values={
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "quantity_change": quantity_change,
                "balance_after": balance_after,
            }
        )
        
        return True, f"✅ Movement posted. New balance: {balance_after}", movement_id
    
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


# =========================================================
# GET STOCK BALANCE
# =========================================================
def get_stock_balance(product_id, warehouse_id=None, batch_id=None, conn=None):
    """
    Calculate stock balance from ledger.
    If warehouse_id is None, returns total across all warehouses.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True
    
    try:
        query = """
            SELECT COALESCE(SUM(quantity_change), 0) as balance
            FROM stock_movements
            WHERE product_id = :pid AND is_posted = 1
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
        print(f"Balance error: {e}")
        return 0.0
    finally:
        if close_conn:
            conn.close()


# =========================================================
# GET ALL BALANCES FOR A WAREHOUSE
# =========================================================
def get_warehouse_balances(warehouse_id=None):
    """Returns DataFrame of product balances for a warehouse (or all)"""
    import pandas as pd
    
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        query = """
            SELECT 
                p.id as product_id,
                p.product_code,
                p.product_name,
                p.unit,
                w.id as warehouse_id,
                w.code as warehouse_code,
                w.name as warehouse_name,
                COALESCE(SUM(sm.quantity_change), 0) as balance
            FROM products p
            CROSS JOIN warehouses w
            LEFT JOIN stock_movements sm 
                ON sm.product_id = p.id 
                AND sm.warehouse_id = w.id
                AND sm.is_posted = 1
            WHERE p.is_active = 1
        """
        params = {}
        
        if warehouse_id is not None:
            query += " AND w.id = :wid"
            params["wid"] = warehouse_id
        
        query += """
            GROUP BY p.id, p.product_code, p.product_name, p.unit,
                     w.id, w.code, w.name
            ORDER BY p.product_name, w.code
        """
        
        return pd.read_sql(text(query), conn, params=params)
    except Exception as e:
        print(f"Balances error: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


# =========================================================
# OPENING STOCK — Bulk entry at MAIN warehouse
# =========================================================
def post_opening_stock(product_id, quantity, unit_cost=0, batch_number=None,
                       production_date=None, expiry_date=None, reason=None):
    """
    Record opening stock at MAIN warehouse.
    Optionally creates a batch if product is batch-tracked.
    """
    conn = get_db_connection()
    if not conn:
        return False, "DB connection failed"
    
    try:
        # Get MAIN warehouse
        main_wh = conn.execute(text(
            "SELECT id FROM warehouses WHERE code = 'MAIN' LIMIT 1"
        )).fetchone()
        
        if not main_wh:
            return False, "MAIN warehouse not found. Please create it in Settings."
        
        main_wh_id = main_wh[0]
        
        # Handle batch if provided
        batch_id = None
        if batch_number:
            existing_batch = conn.execute(text(
                "SELECT id FROM product_batches WHERE batch_number = :bn"
            ), {"bn": batch_number}).fetchone()
            
            if existing_batch:
                batch_id = existing_batch[0]
            else:
                result = conn.execute(text("""
                    INSERT INTO product_batches (
                        batch_number, product_id, production_date, expiry_date,
                        quality_status, quantity_produced, created_at, updated_at
                    ) VALUES (
                        :bn, :pid, :pd, :ed, 'Released', :qty,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    ) RETURNING id
                """), {
                    "bn": batch_number,
                    "pid": product_id,
                    "pd": production_date,
                    "ed": expiry_date,
                    "qty": quantity,
                })
                batch_id = result.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        # Post movement
        ref = generate_reference("OPEN")
        return post_movement(
            product_id=product_id,
            warehouse_id=main_wh_id,
            quantity_change=quantity,
            movement_type="OPENING",
            reference_number=ref,
            batch_id=batch_id,
            unit_cost=unit_cost,
            reason=reason or "Opening stock balance",
        )
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Error: {str(e)}"


# =========================================================
# STOCK TRANSFER (MAIN → PROD / DIST)
# =========================================================
def transfer_stock(product_id, from_wh_id, to_wh_id, quantity,
                   batch_id=None, reason=None, unit_cost=0):
    """
    Transfer stock between warehouses.
    Posts TWO movements: TRANSFER_OUT (negative) and TRANSFER_IN (positive).
    """
    if quantity <= 0:
        return False, "Quantity must be positive"
    
    if from_wh_id == to_wh_id:
        return False, "Source and destination must be different"
    
    # Check source balance
    source_balance = get_stock_balance(product_id, from_wh_id, batch_id)
    if source_balance < quantity:
        return False, (
            f"Insufficient stock at source. "
            f"Available: {source_balance}, Requested: {quantity}"
        )
    
    ref = generate_reference("TRF")
    
    # Post OUT from source
    ok1, msg1, _ = post_movement(
        product_id=product_id,
        warehouse_id=from_wh_id,
        quantity_change=-quantity,
        movement_type="TRANSFER_OUT",
        reference_number=ref,
        batch_id=batch_id,
        unit_cost=unit_cost,
        reason=reason or "Transfer out",
    )
    if not ok1:
        return False, f"Transfer OUT failed: {msg1}"
    
    # Post IN to destination
    ok2, msg2, _ = post_movement(
        product_id=product_id,
        warehouse_id=to_wh_id,
        quantity_change=quantity,
        movement_type="TRANSFER_IN",
        reference_number=ref,
        batch_id=batch_id,
        unit_cost=unit_cost,
        reason=reason or "Transfer in",
    )
    if not ok2:
        return False, f"Transfer IN failed (OUT already posted — reverse manually): {msg2}"
    
    return True, f"✅ Transferred {quantity} units. Ref: {ref}"


# =========================================================
# STOCK ADJUSTMENT
# =========================================================
def post_adjustment(product_id, warehouse_id, new_quantity,
                    batch_id=None, reason=None):
    """
    Adjust stock to a target quantity.
    Calculates the difference and posts an adjustment movement.
    """
    if not reason:
        return False, "Reason is required for adjustments"
    
    current = get_stock_balance(product_id, warehouse_id, batch_id)
    difference = new_quantity - current
    
    if difference == 0:
        return False, "No adjustment needed (quantities match)"
    
    movement_type = "ADJUSTMENT_UP" if difference > 0 else "ADJUSTMENT_DOWN"
    ref = generate_reference("ADJ")
    
    return post_movement(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity_change=difference,
        movement_type=movement_type,
        reference_number=ref,
        batch_id=batch_id,
        reason=reason,
    )


# =========================================================
# HELPERS
# =========================================================
def generate_reference(prefix):
    """Generate reference like OPEN-2026-0001"""
    conn = get_db_connection()
    if not conn:
        return f"{prefix}-{datetime.now().year}-0001"
    
    try:
        year = datetime.now().year
        pattern = f"{prefix}-{year}-%"
        
        result = conn.execute(text("""
            SELECT reference_number FROM stock_movements
            WHERE reference_number LIKE :pat
            ORDER BY id DESC LIMIT 1
        """), {"pat": pattern}).fetchone()
        
        if result and result[0]:
            try:
                num = int(result[0].split("-")[-1])
                return f"{prefix}-{year}-{str(num + 1).zfill(4)}"
            except:
                return f"{prefix}-{year}-0001"
        return f"{prefix}-{year}-0001"
    except:
        return f"{prefix}-{year}-0001"
    finally:
        conn.close()


# =========================================================
# LEDGER VIEW
# =========================================================
def get_ledger(product_id=None, warehouse_id=None, from_date=None, to_date=None):
    """Fetch ledger entries with optional filters"""
    import pandas as pd
    
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        query = """
            SELECT 
                sm.id,
                sm.movement_date,
                sm.movement_type,
                sm.reference_number,
                p.product_code,
                p.product_name,
                w.code as warehouse,
                sm.quantity_change,
                sm.balance_after,
                sm.reason,
                sm.created_at
            FROM stock_movements sm
            JOIN products p ON sm.product_id = p.id
            JOIN warehouses w ON sm.warehouse_id = w.id
            WHERE sm.is_posted = 1
        """
        params = {}
        
        if product_id:
            query += " AND sm.product_id = :pid"
            params["pid"] = product_id
        if warehouse_id:
            query += " AND sm.warehouse_id = :wid"
            params["wid"] = warehouse_id
        if from_date:
            query += " AND sm.movement_date >= :fd"
            params["fd"] = from_date
        if to_date:
            query += " AND sm.movement_date <= :td"
            params["td"] = to_date
        
        query += " ORDER BY sm.movement_date DESC, sm.id DESC LIMIT 500"
        
        return pd.read_sql(text(query), conn, params=params)
    except Exception as e:
        print(f"Ledger error: {e}")
        return pd.DataFrame()
    finally:
        conn.close()
