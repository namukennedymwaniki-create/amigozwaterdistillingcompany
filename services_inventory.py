# =========================================================
# services_inventory.py
# Inventory Service Layer — Stock Ledger Operations
# =========================================================
# PRINCIPLE: ALL stock changes go through post_movement().
# Never UPDATE a stock balance directly — always post a movement.
#
# Return conventions:
#   post_movement()         → (success: bool, message: str, movement_id: int | None)
#   post_opening_stock()    → (success: bool, message: str, movement_id: int | None)
#   transfer_stock()        → (success: bool, message: str)
#   post_adjustment()       → (success: bool, message: str, movement_id: int | None)
#   post_damaged_goods()    → (success: bool, message: str, movement_id: int | None)
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, date
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql


# =========================================================
# HELPERS
# =========================================================
def _safe_df(df):
    """Guarantee a DataFrame is returned, never None."""
    if isinstance(df, pd.DataFrame):
        return df
    return pd.DataFrame()


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
        Positive → INCREASE stock
        Negative → DECREASE stock

    Returns:
        (success: bool, message: str, movement_id: int | None)
    """
    conn = get_db_connection()
    if not conn:
        return False, "Database connection failed", None

    try:
        if movement_type not in MOVEMENT_TYPES:
            return False, f"Invalid movement type: {movement_type}", None

        try:
            quantity_change = float(quantity_change)
        except Exception:
            return False, "Quantity must be numeric", None

        if quantity_change == 0:
            return False, "Quantity change cannot be zero", None

        movement_date = movement_date or date.today()

        # Validate: prevent going negative
        if quantity_change < 0:
            current_balance = get_stock_balance(
                product_id=product_id,
                warehouse_id=warehouse_id,
                batch_id=batch_id,
                conn=conn,
            )
            if current_balance + quantity_change < 0:
                return False, (
                    f"Insufficient stock. Available: {current_balance}, "
                    f"Requested: {abs(quantity_change)}"
                ), None

        # Compute balance_after for the ledger
        current = get_stock_balance(
            product_id=product_id,
            warehouse_id=warehouse_id,
            batch_id=batch_id,
            conn=conn,
        )
        balance_after = current + quantity_change

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
                :uid, TRUE, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "mdate": movement_date,
            "mtype": movement_type,
            "ref": reference_number,
            "pid": int(product_id) if product_id else None,
            "bid": int(batch_id) if batch_id else None,
            "wid": int(warehouse_id) if warehouse_id else None,
            "qty": quantity_change,
            "cost": float(unit_cost or 0),
            "balance": balance_after,
            "reason": reason,
            "refid": int(reference_id) if reference_id else None,
            "reftable": reference_table,
            "uid": user_id,
        })

        movement_id = result.fetchone()[0]
        conn.commit()

        log_audit(
            action=f"STOCK_MOVEMENT_{movement_type}",
            table_name="stock_movements",
            record_id=movement_id,
            new_values={
                "product_id": int(product_id),
                "warehouse_id": int(warehouse_id) if warehouse_id else None,
                "quantity_change": quantity_change,
                "balance_after": balance_after,
            },
        )

        return True, f"✅ Movement posted. New balance: {balance_after}", movement_id

    except Exception as e:
        conn.rollback()
        print(f"🔴 post_movement FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


# =========================================================
# STOCK BALANCE
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
            SELECT COALESCE(SUM(quantity_change), 0) AS balance
            FROM stock_movements
            WHERE product_id = :pid AND is_posted = TRUE
        """
        params = {"pid": int(product_id)}

        if warehouse_id is not None:
            query += " AND warehouse_id = :wid"
            params["wid"] = int(warehouse_id)

        if batch_id is not None:
            query += " AND batch_id = :bid"
            params["bid"] = int(batch_id)

        result = conn.execute(text(query), params).scalar()
        return float(result or 0)
    except Exception as e:
        print(f"Balance error: {e}")
        return 0.0
    finally:
        if close_conn:
            conn.close()


# =========================================================
# WAREHOUSE BALANCES
# =========================================================
def get_warehouse_balances(warehouse_id=None):
    """Returns DataFrame of product balances for a warehouse (or all)."""
    query = """
        SELECT 
            p.id AS product_id,
            p.product_code,
            p.product_name,
            p.unit,
            w.id AS warehouse_id,
            w.code AS warehouse_code,
            w.name AS warehouse_name,
            COALESCE(SUM(sm.quantity_change), 0) AS balance
        FROM products p
        CROSS JOIN warehouses w
        LEFT JOIN stock_movements sm 
            ON sm.product_id = p.id 
            AND sm.warehouse_id = w.id
            AND sm.is_posted = TRUE
        WHERE p.is_active = TRUE
    """
    params = {}

    if warehouse_id is not None:
        query += " AND w.id = :wid"
        params["wid"] = int(warehouse_id)

    query += """
        GROUP BY p.id, p.product_code, p.product_name, p.unit,
                 w.id, w.code, w.name
        ORDER BY p.product_name, w.code
    """

    return _safe_df(read_sql(query, params if params else None))


# =========================================================
# OPENING STOCK
# =========================================================
def post_opening_stock(product_id, quantity, unit_cost=0, batch_number=None,
                       production_date=None, expiry_date=None, reason=None,
                       batch_status=None, warehouse_code="MAIN"):
    """
    Record opening stock. Optionally creates a batch if batch_number is given.

    batch_status: override the default (Quarantined). Useful for test data
                  → pass 'Released' to make it immediately sellable.

    Returns:
        (success: bool, message: str, movement_id: int | None)
    """
    conn = get_db_connection()
    if not conn:
        return False, "DB connection failed", None

    try:
        # Resolve MAIN warehouse
        main_wh = conn.execute(text(
            "SELECT id FROM warehouses WHERE code = :c AND is_active = TRUE LIMIT 1"
        ), {"c": warehouse_code}).fetchone()

        if not main_wh:
            conn.close()
            return False, f"{warehouse_code} warehouse not found. Please create it in Settings.", None

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
                default_status = batch_status or "Quarantined"
                result = conn.execute(text("""
                    INSERT INTO product_batches (
                        batch_number, product_id, production_date, expiry_date,
                        quality_status, quantity_produced, notes,
                        created_at, updated_at
                    ) VALUES (
                        :bn, :pid, :pd, :ed,
                        :status, :qty, :notes,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    ) RETURNING id
                """), {
                    "bn": batch_number,
                    "pid": int(product_id),
                    "pd": production_date,
                    "ed": expiry_date,
                    "status": default_status,
                    "qty": float(quantity),
                    "notes": "[TEST] Opening stock batch" if reason and "[TEST]" in reason else None,
                })
                batch_id = result.fetchone()[0]

        conn.commit()
        conn.close()

        # Post the OPENING movement (separate connection inside post_movement)
        ref = generate_reference("OPEN")
        return post_movement(
            product_id=int(product_id),
            warehouse_id=main_wh_id,
            quantity_change=float(quantity),
            movement_type="OPENING",
            reference_number=ref,
            batch_id=batch_id,
            unit_cost=float(unit_cost or 0),
            reason=reason or "Opening stock balance",
        )

    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        print(f"post_opening_stock error: {e}")
        return False, f"Error: {str(e)}", None


# =========================================================
# STOCK TRANSFER
# =========================================================
def transfer_stock(product_id, from_wh_id, to_wh_id, quantity,
                   batch_id=None, reason=None, unit_cost=0):
    """Transfer stock between warehouses (2 movements)."""
    try:
        quantity = float(quantity)
    except Exception:
        return False, "Quantity must be numeric"

    if quantity <= 0:
        return False, "Quantity must be positive"

    if from_wh_id == to_wh_id:
        return False, "Source and destination must be different"

    source_balance = get_stock_balance(product_id, from_wh_id, batch_id)
    if source_balance < quantity:
        return False, (
            f"Insufficient stock at source. "
            f"Available: {source_balance}, Requested: {quantity}"
        )

    ref = generate_reference("TRF")

    ok1, msg1, _ = post_movement(
        product_id=int(product_id),
        warehouse_id=int(from_wh_id),
        quantity_change=-quantity,
        movement_type="TRANSFER_OUT",
        reference_number=ref,
        batch_id=int(batch_id) if batch_id else None,
        unit_cost=float(unit_cost or 0),
        reason=reason or "Transfer out",
    )
    if not ok1:
        return False, f"Transfer OUT failed: {msg1}"

    ok2, msg2, _ = post_movement(
        product_id=int(product_id),
        warehouse_id=int(to_wh_id),
        quantity_change=quantity,
        movement_type="TRANSFER_IN",
        reference_number=ref,
        batch_id=int(batch_id) if batch_id else None,
        unit_cost=float(unit_cost or 0),
        reason=reason or "Transfer in",
    )
    if not ok2:
        return False, f"Transfer IN failed (OUT already posted): {msg2}"

    return True, f"✅ Transferred {quantity} units. Ref: {ref}"


# =========================================================
# STOCK ADJUSTMENT
# =========================================================
def post_adjustment(product_id, warehouse_id, new_quantity,
                    batch_id=None, reason=None):
    """
    Adjust stock to a target quantity.
    Returns: (ok, msg, movement_id)
    """
    if not reason:
        return False, "Reason is required for adjustments", None

    current = get_stock_balance(product_id, warehouse_id, batch_id)
    try:
        new_quantity = float(new_quantity)
    except Exception:
        return False, "New quantity must be numeric", None

    difference = new_quantity - current

    if abs(difference) < 0.0001:
        return False, "No adjustment needed (quantities match)", None

    movement_type = "ADJUSTMENT_UP" if difference > 0 else "ADJUSTMENT_DOWN"
    ref = generate_reference("ADJ")

    return post_movement(
        product_id=int(product_id),
        warehouse_id=int(warehouse_id),
        quantity_change=difference,
        movement_type=movement_type,
        reference_number=ref,
        batch_id=int(batch_id) if batch_id else None,
        reason=reason,
    )


# =========================================================
# DAMAGED GOODS
# =========================================================
def post_damaged_goods(product_id, warehouse_id, quantity, reason=None,
                       batch_id=None, reference_number=None, unit_cost=0):
    """
    Record damaged goods — posts a DAMAGE (negative) movement.
    Returns: (ok, msg, movement_id)
    """
    try:
        quantity = float(quantity)
    except Exception:
        return False, "Quantity must be numeric", None

    if quantity <= 0:
        return False, "Quantity must be positive", None

    if not reason:
        return False, "Reason required for damaged goods", None

    return post_movement(
        product_id=int(product_id),
        warehouse_id=int(warehouse_id),
        quantity_change=-abs(quantity),
        movement_type="DAMAGE",
        reference_number=reference_number or f"DMG-{date.today().strftime('%Y%m%d')}",
        batch_id=int(batch_id) if batch_id else None,
        unit_cost=float(unit_cost or 0),
        reason=reason,
    )


# =========================================================
# REFERENCE NUMBER GENERATOR
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
            except Exception:
                return f"{prefix}-{year}-0001"
        return f"{prefix}-{year}-0001"
    except Exception:
        return f"{prefix}-{year}-0001"
    finally:
        conn.close()


# =========================================================
# LEDGER VIEW
# =========================================================
def get_ledger(product_id=None, warehouse_id=None, from_date=None, to_date=None):
    """Fetch ledger entries with optional filters. Always returns a DataFrame."""
    query = """
        SELECT 
            sm.id,
            sm.movement_date,
            sm.movement_type,
            sm.reference_number,
            p.product_code,
            p.product_name,
            w.code AS warehouse,
            sm.quantity_change,
            sm.balance_after,
            sm.reason,
            sm.created_at
        FROM stock_movements sm
        JOIN products p ON sm.product_id = p.id
        JOIN warehouses w ON sm.warehouse_id = w.id
        WHERE sm.is_posted = TRUE
    """
    params = {}

    if product_id:
        query += " AND sm.product_id = :pid"
        params["pid"] = int(product_id)
    if warehouse_id:
        query += " AND sm.warehouse_id = :wid"
        params["wid"] = int(warehouse_id)
    if from_date:
        query += " AND sm.movement_date >= :fd"
        params["fd"] = from_date
    if to_date:
        query += " AND sm.movement_date <= :td"
        params["td"] = to_date

    query += " ORDER BY sm.movement_date DESC, sm.id DESC LIMIT 500"

    return _safe_df(read_sql(query, params if params else None))


# =========================================================
# SELLABLE STOCK (BATCH-AWARE)
# =========================================================
def get_sellable_stock(product_id, warehouse_id=None):
    """
    Get stock that is available for sale.
    - Non-batch-tracked: all stock
    - Batch-tracked: only Released + non-expired batches
    """
    from services_quality import get_available_stock
    return get_available_stock(product_id, warehouse_id)


def check_sellable_stock(product_id, warehouse_id, quantity_requested):
    """
    Validate that enough sellable stock exists.
    Returns: (ok: bool, available: float, message: str)
    """
    available = get_sellable_stock(product_id, warehouse_id)

    if available >= quantity_requested:
        return True, available, f"✅ Sufficient stock: {available}"
    else:
        return False, available, (
            f"❌ Insufficient sellable stock. "
            f"Available: {available}, Requested: {quantity_requested}"
        )
