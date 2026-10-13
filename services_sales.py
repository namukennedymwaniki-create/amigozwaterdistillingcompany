# =========================================================
# services_sales.py
# Sales Order Service Layer — Boolean-safe & DataFrame-safe
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql
from services_customers import check_credit_available
from services_quality import get_available_stock


ORDER_STATUSES = ["Draft", "Confirmed", "Dispatched", "Invoiced", "Cancelled"]


# =========================================================
# HELPERS
# =========================================================
def _safe_df(df):
    """Guarantee a DataFrame is returned, never None."""
    if isinstance(df, pd.DataFrame):
        return df
    return pd.DataFrame()


# =========================================================
# NUMBER GENERATION
# =========================================================
def generate_order_number():
    """SO-{YYYY}-{SEQ}"""
    conn = get_db_connection()
    if not conn:
        return f"SO-{datetime.now().year}-0001"
    try:
        year = datetime.now().year
        pattern = f"SO-{year}-%"
        result = conn.execute(text("""
            SELECT order_number FROM sales_orders
            WHERE order_number LIKE :pat
            ORDER BY id DESC LIMIT 1
        """), {"pat": pattern}).fetchone()
        if result and result[0]:
            try:
                num = int(result[0].split("-")[-1])
                return f"SO-{year}-{str(num + 1).zfill(4)}"
            except Exception:
                return f"SO-{year}-0001"
        return f"SO-{year}-0001"
    except Exception:
        return f"SO-{year}-0001"
    finally:
        conn.close()


def generate_reservation_number():
    """RSV-{YYYY}-{SEQ}"""
    conn = get_db_connection()
    if not conn:
        return f"RSV-{datetime.now().year}-0001"
    try:
        year = datetime.now().year
        pattern = f"RSV-{year}-%"
        result = conn.execute(text("""
            SELECT reservation_number FROM stock_reservations
            WHERE reservation_number LIKE :pat
            ORDER BY id DESC LIMIT 1
        """), {"pat": pattern}).fetchone()
        if result and result[0]:
            try:
                num = int(result[0].split("-")[-1])
                return f"RSV-{year}-{str(num + 1).zfill(4)}"
            except Exception:
                return f"RSV-{year}-0001"
        return f"RSV-{year}-0001"
    except Exception:
        return f"RSV-{year}-0001"
    finally:
        conn.close()


# =========================================================
# CREATE
# =========================================================
def create_sales_order(customer_id, order_date, delivery_date=None,
                       vat_enabled=False, tax_rate=16, notes=None,
                       items=None):
    """
    Create a sales order in Draft status.
    items: list of dicts [{product_id, quantity, unit_price}, ...]
    """
    if not customer_id:
        return False, "Customer required", None
    if not items:
        return False, "At least one line item required", None

    conn = get_db_connection()
    if not conn:
        return False, "DB connection failed", None
    try:
        order_number = generate_order_number()

        # Coerce boolean explicitly
        vat_enabled = bool(vat_enabled)

        subtotal = sum(float(it['quantity']) * float(it['unit_price']) for it in items)
        tax_amount = subtotal * (tax_rate / 100.0) if vat_enabled else 0.0
        total = subtotal + tax_amount

        result = conn.execute(text("""
            INSERT INTO sales_orders (
                order_number, customer_id, order_date, delivery_date,
                status, subtotal, tax_amount, total_amount,
                vat_enabled, tax_rate, notes, created_by,
                created_at, updated_at
            ) VALUES (
                :num, :cid, :odate, :ddate,
                'Draft', :sub, :tax, :total,
                :vat, :rate, :notes, :uid,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "num": order_number,
            "cid": int(customer_id),
            "odate": order_date,
            "ddate": delivery_date,
            "sub": subtotal,
            "tax": tax_amount,
            "total": total,
            "vat": vat_enabled,          # Python bool
            "rate": float(tax_rate) if vat_enabled else 0.0,
            "notes": notes,
            "uid": st.session_state.get('user_id'),
        })

        order_id = result.fetchone()[0]

        for it in items:
            line_total = float(it['quantity']) * float(it['unit_price'])
            conn.execute(text("""
                INSERT INTO sales_order_items (
                    order_id, product_id, quantity_ordered,
                    unit_price, line_total, created_at
                ) VALUES (
                    :oid, :pid, :qty, :price, :total, CURRENT_TIMESTAMP
                )
            """), {
                "oid": order_id,
                "pid": int(it['product_id']),
                "qty": float(it['quantity']),
                "price": float(it['unit_price']),
                "total": line_total,
            })

        conn.commit()
        log_audit("CREATE_SALES_ORDER", "sales_orders", order_id,
                  new_values={"order_number": order_number,
                              "customer_id": int(customer_id),
                              "total": total, "items_count": len(items)})

        return True, f"✅ Order {order_number} created (Draft)", order_id
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


# =========================================================
# READ
# =========================================================
def get_sales_orders(status_filter=None, customer_id=None, search=None):
    """List sales orders — always returns a DataFrame."""
    query = """
        SELECT 
            so.id,
            so.order_number,
            so.order_date,
            so.delivery_date,
            so.status,
            so.subtotal,
            so.tax_amount,
            so.total_amount,
            so.created_at,
            c.customer_code,
            c.customer_name,
            (SELECT COUNT(*) FROM sales_order_items WHERE order_id = so.id) as items_count
        FROM sales_orders so
        LEFT JOIN customers c ON so.customer_id = c.id
        WHERE 1=1
    """
    params = {}

    if status_filter and status_filter != "All":
        query += " AND so.status = :status"
        params["status"] = status_filter

    if customer_id:
        query += " AND so.customer_id = :cid"
        params["cid"] = int(customer_id)

    if search:
        query += " AND (LOWER(so.order_number) LIKE :s OR LOWER(c.customer_name) LIKE :s)"
        params["s"] = f"%{search.lower()}%"

    query += " ORDER BY so.id DESC LIMIT 500"
    return _safe_df(read_sql(query, params if params else None))


def get_order(order_id):
    """Get order header."""
    df = _safe_df(read_sql("""
        SELECT so.*, c.customer_code, c.customer_name
        FROM sales_orders so
        LEFT JOIN customers c ON so.customer_id = c.id
        WHERE so.id = :id
    """, {"id": int(order_id)}))
    return None if df.empty else df.iloc[0]


def get_order_items(order_id):
    """Get order line items — always returns a DataFrame."""
    return _safe_df(read_sql("""
        SELECT 
            soi.id,
            soi.product_id,
            soi.quantity_ordered,
            soi.quantity_dispatched,
            soi.unit_price,
            soi.line_total,
            p.product_code,
            p.product_name,
            p.unit
        FROM sales_order_items soi
        JOIN products p ON soi.product_id = p.id
        WHERE soi.order_id = :oid
        ORDER BY soi.id
    """, {"oid": int(order_id)}))


# =========================================================
# CONFIRM
# =========================================================
def confirm_order(order_id, allow_credit_override=False):
    """
    Confirm a draft order:
    1. Validate sellable stock for each item
    2. Check customer credit
    3. Create stock reservations
    4. Set status to 'Confirmed'
    """
    conn = get_db_connection()
    if not conn:
        return False, "DB connection failed"

    try:
        order = get_order(order_id)
        if order is None:
            return False, "Order not found"

        if order['status'] != 'Draft':
            return False, f"Cannot confirm order in '{order['status']}' status"

        items = get_order_items(order_id)
        if items.empty:
            return False, "No line items"

        # Validate stock
        errors = []
        for _, it in items.iterrows():
            available = get_available_stock(it['product_id'])
            if available < float(it['quantity_ordered']):
                errors.append(
                    f"  • {it['product_name']}: requested {it['quantity_ordered']}, "
                    f"available {available}"
                )

        if errors:
            return False, "❌ Insufficient sellable stock:\n" + "\n".join(errors)

        # Credit check
        ok, avail, msg = check_credit_available(order['customer_id'], order['total_amount'])
        if not ok and not allow_credit_override:
            return False, msg

        # Create reservations
        rsv_number = generate_reservation_number()

        for _, it in items.iterrows():
            conn.execute(text("""
                INSERT INTO stock_reservations (
                    reservation_number, product_id, quantity,
                    reference_id, reference_table, reference_number,
                    reserved_for, status, expires_at, notes,
                    created_by, created_at
                ) VALUES (
                    :rnum, :pid, :qty,
                    :rid, 'sales_orders', :onum,
                    :rfor, 'Active', :exp, :notes,
                    :uid, CURRENT_TIMESTAMP
                )
            """), {
                "rnum": rsv_number,
                "pid": int(it['product_id']),
                "qty": float(it['quantity_ordered']),
                "rid": int(order_id),
                "onum": order['order_number'],
                "rfor": order['customer_name'],
                "exp": datetime.now() + timedelta(days=7),
                "notes": f"Auto-reserve for order {order['order_number']}",
                "uid": st.session_state.get('user_id'),
            })

        # Update order status
        conn.execute(text("""
            UPDATE sales_orders 
            SET status = 'Confirmed',
                confirmed_at = CURRENT_TIMESTAMP,
                confirmed_by = :uid,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {"id": int(order_id), "uid": st.session_state.get('user_id')})

        conn.commit()
        log_audit("CONFIRM_SALES_ORDER", "sales_orders", order_id,
                  new_values={"status": "Confirmed", "reservation": rsv_number})

        return True, f"✅ Order {order['order_number']} confirmed. Reserved: {rsv_number}"

    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}"
    finally:
        conn.close()


# =========================================================
# CANCEL
# =========================================================
def cancel_order(order_id, reason=None):
    """Cancel order and release all reservations"""
    if not reason:
        return False, "Cancellation reason required"

    conn = get_db_connection()
    if not conn:
        return False, "DB connection failed"

    try:
        order = get_order(order_id)
        if order is None:
            return False, "Order not found"

        if order['status'] in ['Dispatched', 'Invoiced']:
            return False, f"Cannot cancel order in '{order['status']}' status"

        # Release reservations
        conn.execute(text("""
            UPDATE stock_reservations
            SET status = 'Released',
                released_at = CURRENT_TIMESTAMP,
                released_reason = :reason
            WHERE reference_table = 'sales_orders'
              AND reference_id = :oid
              AND status = 'Active'
        """), {"oid": int(order_id), "reason": reason})

        # Update order
        conn.execute(text("""
            UPDATE sales_orders
            SET status = 'Cancelled',
                cancelled_at = CURRENT_TIMESTAMP,
                cancellation_reason = :reason,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {"id": int(order_id), "reason": reason})

        conn.commit()
        log_audit("CANCEL_SALES_ORDER", "sales_orders", order_id,
                  new_values={"status": "Cancelled", "reason": reason})

        return True, f"✅ Order {order['order_number']} cancelled"

    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}"
    finally:
        conn.close()
