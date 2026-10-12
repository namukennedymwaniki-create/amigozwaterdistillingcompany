# =========================================================
# services_procurement.py
# Purchase Orders + Goods Received Notes
# =========================================================
# PRINCIPLE:
#   POs NEVER touch stock.
#   Stock is only increased at GRN confirmation (movement = RECEIPT).
# =========================================================

import streamlit as st
from datetime import datetime, date
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql
from services_inventory import post_movement
from services_quality import generate_batch_number


PO_STATUSES = ["Draft", "Approved", "Partially Received", "Fully Received", "Cancelled"]
GRN_STATUSES = ["Draft", "Confirmed", "Cancelled"]


# =========================================================
# NUMBER GENERATION
# =========================================================
def _seq_number(table, column, prefix):
    conn = get_db_connection()
    if not conn:
        return f"{prefix}-{datetime.now().year}-0001"
    try:
        year = datetime.now().year
        pattern = f"{prefix}-{year}-%"
        result = conn.execute(text(f"""
            SELECT {column} FROM {table}
            WHERE {column} LIKE :pat
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


def generate_po_number():
    return _seq_number("purchase_orders", "po_number", "PO")


def generate_grn_number():
    return _seq_number("goods_received_notes", "grn_number", "GRN")


# =========================================================
# PURCHASE ORDERS
# =========================================================
def create_purchase_order(supplier_id, order_date=None, expected_date=None,
                          payment_terms="30 days", notes=None, items=None):
    """
    items: [{product_id, quantity_ordered, unit_cost}, ...]
    """
    if not supplier_id:
        return False, "Supplier required", None
    if not items:
        return False, "At least one line item required", None
    
    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None
    try:
        po_number = generate_po_number()
        order_date = order_date or date.today()
        
        subtotal = sum(float(it['quantity_ordered']) * float(it['unit_cost']) for it in items)
        
        result = conn.execute(text("""
            INSERT INTO purchase_orders (
                po_number, supplier_id, order_date, expected_date,
                status, total_amount, notes, payment_terms,
                created_by, created_at, updated_at
            ) VALUES (
                :num, :sid, :odate, :edate,
                'Draft', :total, :notes, :terms,
                :uid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "num": po_number, "sid": supplier_id, "odate": order_date,
            "edate": expected_date, "total": subtotal, "notes": notes,
            "terms": payment_terms, "uid": st.session_state.get('user_id'),
        })
        po_id = result.fetchone()[0]
        
        for it in items:
            line_total = float(it['quantity_ordered']) * float(it['unit_cost'])
            conn.execute(text("""
                INSERT INTO purchase_order_items (
                    po_id, product_id, quantity_ordered, quantity_received,
                    unit_cost, line_total, created_at
                ) VALUES (
                    :po, :pid, :qty, 0, :cost, :total, CURRENT_TIMESTAMP
                )
            """), {
                "po": po_id, "pid": it['product_id'],
                "qty": it['quantity_ordered'], "cost": it['unit_cost'],
                "total": line_total,
            })
        
        conn.commit()
        log_audit("CREATE_PO", "purchase_orders", po_id,
                  new_values={"po_number": po_number, "supplier_id": supplier_id,
                              "total": subtotal})
        return True, f"✅ PO {po_number} created (Draft)", po_id
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


def approve_purchase_order(po_id):
    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    try:
        row = conn.execute(text(
            "SELECT status, po_number FROM purchase_orders WHERE id = :id"
        ), {"id": po_id}).fetchone()
        if not row:
            return False, "PO not found"
        if row[0] != 'Draft':
            return False, f"PO is '{row[0]}' — only Draft can be approved"
        
        conn.execute(text("""
            UPDATE purchase_orders
            SET status = 'Approved',
                approved_at = CURRENT_TIMESTAMP,
                approved_by = :uid,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {"id": po_id, "uid": st.session_state.get('user_id')})
        conn.commit()
        log_audit("APPROVE_PO", "purchase_orders", po_id,
                  new_values={"status": "Approved"})
        return True, f"✅ PO {row[1]} approved"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


def cancel_purchase_order(po_id, reason=None):
    if not reason:
        return False, "Reason required"
    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    try:
        row = conn.execute(text(
            "SELECT status, po_number FROM purchase_orders WHERE id = :id"
        ), {"id": po_id}).fetchone()
        if not row:
            return False, "PO not found"
        if row[0] in ('Fully Received', 'Cancelled'):
            return False, f"Cannot cancel a '{row[0]}' PO"
        
        conn.execute(text("""
            UPDATE purchase_orders
            SET status = 'Cancelled', notes = COALESCE(notes,'') || :note,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {"id": po_id, "note": f"\n[CANCELLED] {reason}"})
        conn.commit()
        log_audit("CANCEL_PO", "purchase_orders", po_id,
                  new_values={"reason": reason})
        return True, f"✅ PO {row[1]} cancelled"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


def get_purchase_orders(status_filter=None, supplier_id=None, search=None):
    query = """
        SELECT 
            po.id, po.po_number, po.order_date, po.expected_date,
            po.status, po.total_amount, po.created_at,
            s.supplier_code, s.supplier_name,
            (SELECT COUNT(*) FROM purchase_order_items WHERE po_id = po.id) as items_count
        FROM purchase_orders po
        LEFT JOIN suppliers s ON po.supplier_id = s.id
        WHERE 1=1
    """
    params = {}
    if status_filter and status_filter != "All":
        query += " AND po.status = :st"; params["st"] = status_filter
    if supplier_id:
        query += " AND po.supplier_id = :sid"; params["sid"] = supplier_id
    if search:
        query += " AND (LOWER(po.po_number) LIKE :s OR LOWER(s.supplier_name) LIKE :s)"
        params["s"] = f"%{search.lower()}%"
    query += " ORDER BY po.id DESC LIMIT 500"
    return read_sql(query, params if params else None)


def get_purchase_order(po_id):
    df = read_sql("""
        SELECT po.*, s.supplier_code, s.supplier_name, s.address as supplier_address,
               s.phone as supplier_phone, s.email as supplier_email
        FROM purchase_orders po
        LEFT JOIN suppliers s ON po.supplier_id = s.id
        WHERE po.id = :id
    """, {"id": po_id})
    return None if df.empty else df.iloc[0]


def get_po_items(po_id):
    return read_sql("""
        SELECT poi.*, p.product_code, p.product_name, p.unit,
               (poi.quantity_ordered - poi.quantity_received) as qty_outstanding
        FROM purchase_order_items poi
        JOIN products p ON poi.product_id = p.id
        WHERE poi.po_id = :po
        ORDER BY poi.id
    """, {"po": po_id})


# =========================================================
# GOODS RECEIVED NOTES
# =========================================================
def create_grn(po_id, warehouse_id, received_date=None, notes=None, items=None):
    """
    Creates GRN header in Draft.
    items: [{po_item_id, product_id, quantity_received, quantity_rejected,
             unit_cost, rejection_reason, batch_number?, production_date?, expiry_date?}, ...]
    """
    if not items:
        return False, "At least one item required", None
    
    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None
    try:
        po = get_purchase_order(po_id)
        if po is None:
            return False, "PO not found", None
        if po['status'] not in ('Approved', 'Partially Received'):
            return False, f"PO status is '{po['status']}' — cannot receive", None
        
        grn_number = generate_grn_number()
        received_date = received_date or date.today()
        
        result = conn.execute(text("""
            INSERT INTO goods_received_notes (
                grn_number, po_id, supplier_id, warehouse_id,
                received_date, status, notes,
                created_at, updated_at
            ) VALUES (
                :num, :po, :sid, :wid,
                :rdate, 'Draft', :notes,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "num": grn_number, "po": po_id, "sid": po['supplier_id'],
            "wid": warehouse_id, "rdate": received_date, "notes": notes,
        })
        grn_id = result.fetchone()[0]
        
        for it in items:
            conn.execute(text("""
                INSERT INTO goods_received_note_items (
                    grn_id, product_id, po_item_id, batch_id,
                    quantity_received, quantity_rejected, unit_cost,
                    rejection_reason, notes, created_at
                ) VALUES (
                    :grn, :pid, :poi, NULL,
                    :qrec, :qrej, :cost,
                    :rreason, :notes, CURRENT_TIMESTAMP
                )
            """), {
                "grn": grn_id, "pid": it['product_id'], "poi": it.get('po_item_id'),
                "qrec": it.get('quantity_received', 0),
                "qrej": it.get('quantity_rejected', 0),
                "cost": it.get('unit_cost', 0),
                "rreason": it.get('rejection_reason'),
                "notes": it.get('notes'),
            })
        
        conn.commit()
        log_audit("CREATE_GRN", "goods_received_notes", grn_id,
                  new_values={"grn_number": grn_number, "po_id": po_id})
        return True, f"✅ GRN {grn_number} created (Draft)", grn_id
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


def confirm_grn(grn_id, default_batch_status="Quarantined"):
    """
    Confirm a GRN:
      1. For batch-tracked products → auto-create a batch (status Quarantined)
      2. Post RECEIPT stock movement for accepted quantity
      3. Update PO line quantity_received
      4. Recompute PO status (Partially / Fully Received)
      5. Mark GRN Confirmed
    """
    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    try:
        grn = conn.execute(text("""
            SELECT grn_number, po_id, warehouse_id, status
            FROM goods_received_notes WHERE id = :id
        """), {"id": grn_id}).fetchone()
        if not grn:
            return False, "GRN not found"
        grn_number, po_id, warehouse_id, status = grn
        if status != 'Draft':
            return False, f"GRN is '{status}' — only Draft can be confirmed"
        
        items = conn.execute(text("""
            SELECT id, product_id, po_item_id, quantity_received, quantity_rejected, unit_cost
            FROM goods_received_note_items WHERE grn_id = :gid
        """), {"gid": grn_id}).fetchall()
        if not items:
            return False, "GRN has no items"
        
        conn.commit()
        conn.close()
        
        # Post movements + create batches
        errors = []
        for row in items:
            item_id, pid, po_item_id, qrec, qrej, cost = row
            qrec = float(qrec or 0)
            if qrec <= 0:
                continue
            
            # Check batch-tracking
            bt = read_sql("SELECT is_batch_tracked, product_code FROM products WHERE id = :id",
                          {"id": pid})
            is_batch = bool(bt.iloc[0]['is_batch_tracked']) if not bt.empty else False
            product_code = bt.iloc[0]['product_code'] if not bt.empty else "PRD"
            
            batch_id = None
            if is_batch:
                batch_number = generate_batch_number(product_code)
                c2 = get_db_connection()
                try:
                    res = c2.execute(text("""
                        INSERT INTO product_batches (
                            batch_number, product_id, quality_status,
                            quantity_produced, notes, created_at, updated_at
                        ) VALUES (
                            :bn, :pid, :status,
                            :qty, :notes, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        ) RETURNING id
                    """), {
                        "bn": batch_number, "pid": pid, "status": default_batch_status,
                        "qty": qrec, "notes": f"Auto-created from GRN {grn_number}",
                    })
                    batch_id = res.fetchone()[0]
                    c2.commit()
                except Exception as be:
                    errors.append(f"Batch create failed for item {item_id}: {be}")
                finally:
                    c2.close()
                
                # Store batch_id on the GRN item
                c3 = get_db_connection()
                try:
                    c3.execute(text("""
                        UPDATE goods_received_note_items SET batch_id = :bid WHERE id = :id
                    """), {"bid": batch_id, "id": item_id})
                    c3.commit()
                finally:
                    c3.close()
            
            # Post RECEIPT movement
            ok, msg, _ = post_movement(
                product_id=pid,
                warehouse_id=warehouse_id,
                quantity_change=qrec,
                movement_type="RECEIPT",
                reference_number=grn_number,
                batch_id=batch_id,
                unit_cost=float(cost or 0),
                reason=f"Goods received — GRN {grn_number}",
                reference_id=grn_id,
                reference_table="goods_received_notes",
            )
            if not ok:
                errors.append(f"Item {item_id}: {msg}")
                continue
            
            # Update PO line received qty
            if po_item_id:
                c4 = get_db_connection()
                try:
                    c4.execute(text("""
                        UPDATE purchase_order_items
                        SET quantity_received = quantity_received + :qty
                        WHERE id = :id
                    """), {"qty": qrec, "id": po_item_id})
                    c4.commit()
                finally:
                    c4.close()
        
        # Confirm GRN
        c5 = get_db_connection()
        c5.execute(text("""
            UPDATE goods_received_notes
            SET status = 'Confirmed',
                confirmed_at = CURRENT_TIMESTAMP,
                confirmed_by = :uid,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {"id": grn_id, "uid": st.session_state.get('user_id')})
        c5.commit()
        c5.close()
        
        # Recompute PO status
        _refresh_po_status(po_id)
        
        log_audit("CONFIRM_GRN", "goods_received_notes", grn_id,
                  new_values={"grn_number": grn_number, "po_id": po_id})
        
        msg = f"✅ GRN {grn_number} confirmed — stock received"
        if errors:
            msg += " ⚠️ " + "; ".join(errors)
        return True, msg
    except Exception as e:
        try: conn.rollback(); conn.close()
        except: pass
        return False, f"Error: {str(e)}"


def _refresh_po_status(po_id):
    conn = get_db_connection()
    if not conn:
        return
    try:
        row = conn.execute(text("""
            SELECT 
                SUM(quantity_ordered) AS ordered,
                SUM(quantity_received) AS received,
                MAX(status) as cur_status
            FROM purchase_order_items
            WHERE po_id = :po
        """), {"po": po_id}).fetchone()
        if not row or row[0] is None:
            return
        ordered, received, cur = float(row[0]), float(row[1]), row[2]
        
        # Skip if already Cancelled
        po_stat = conn.execute(text(
            "SELECT status FROM purchase_orders WHERE id = :id"
        ), {"id": po_id}).fetchone()
        if po_stat and po_stat[0] == 'Cancelled':
            return
        
        if received <= 0:
            new_status = 'Approved'
        elif received < ordered - 0.0001:
            new_status = 'Partially Received'
        else:
            new_status = 'Fully Received'
        
        conn.execute(text("""
            UPDATE purchase_orders
            SET status = :st, updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {"st": new_status, "id": po_id})
        conn.commit()
    finally:
        conn.close()


def cancel_grn(grn_id, reason=None):
    """Only allow cancel of a Draft GRN (confirmed GRNs need reversal — out of scope)"""
    if not reason:
        return False, "Reason required"
    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    try:
        row = conn.execute(text(
            "SELECT status, grn_number FROM goods_received_notes WHERE id = :id"
        ), {"id": grn_id}).fetchone()
        if not row:
            return False, "GRN not found"
        if row[0] != 'Draft':
            return False, f"Cannot cancel a '{row[0]}' GRN — only Draft"
        
        conn.execute(text("""
            UPDATE goods_received_notes
            SET status = 'Cancelled', notes = COALESCE(notes,'') || :note,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {"id": grn_id, "note": f"\n[CANCELLED] {reason}"})
        conn.commit()
        log_audit("CANCEL_GRN", "goods_received_notes", grn_id,
                  new_values={"reason": reason})
        return True, f"✅ GRN {row[1]} cancelled"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


def get_grns(status_filter=None, search=None):
    query = """
        SELECT 
            g.id, g.grn_number, g.received_date, g.status,
            po.po_number,
            s.supplier_code, s.supplier_name,
            w.code as warehouse_code,
            (SELECT COUNT(*) FROM goods_received_note_items WHERE grn_id = g.id) as items_count
        FROM goods_received_notes g
        LEFT JOIN purchase_orders po ON g.po_id = po.id
        LEFT JOIN suppliers s ON g.supplier_id = s.id
        LEFT JOIN warehouses w ON g.warehouse_id = w.id
        WHERE 1=1
    """
    params = {}
    if status_filter and status_filter != "All":
        query += " AND g.status = :st"; params["st"] = status_filter
    if search:
        query += " AND (LOWER(g.grn_number) LIKE :s OR LOWER(s.supplier_name) LIKE :s)"
        params["s"] = f"%{search.lower()}%"
    query += " ORDER BY g.id DESC LIMIT 500"
    return read_sql(query, params if params else None)


def get_grn(grn_id):
    df = read_sql("""
        SELECT g.*, po.po_number, s.supplier_code, s.supplier_name,
               w.code as warehouse_code, w.name as warehouse_name
        FROM goods_received_notes g
        LEFT JOIN purchase_orders po ON g.po_id = po.id
        LEFT JOIN suppliers s ON g.supplier_id = s.id
        LEFT JOIN warehouses w ON g.warehouse_id = w.id
        WHERE g.id = :id
    """, {"id": grn_id})
    return None if df.empty else df.iloc[0]


def get_grn_items(grn_id):
    return read_sql("""
        SELECT gi.*, p.product_code, p.product_name, p.unit,
               pb.batch_number
        FROM goods_received_note_items gi
        JOIN products p ON gi.product_id = p.id
        LEFT JOIN product_batches pb ON gi.batch_id = pb.id
        WHERE gi.grn_id = :id
        ORDER BY gi.id
    """, {"id": grn_id})


# =========================================================
# REORDER REPORT
# =========================================================
def get_reorder_alerts(warehouse_id=None):
    """
    Products where total stock < reorder_level.
    Uses the ledger, summed across warehouses (or one).
    """
    query = """
        SELECT 
            p.id,
            p.product_code,
            p.product_name,
            p.unit,
            p.reorder_level,
            p.reorder_quantity,
            p.cost_price,
            COALESCE((
                SELECT SUM(sm.quantity_change)
                FROM stock_movements sm
                WHERE sm.product_id = p.id AND sm.is_posted = 1
    """
    if warehouse_id is not None:
        query += " AND sm.warehouse_id = :wid"
    query += """
            ), 0) as current_stock
        FROM products p
        WHERE p.is_active = 1 AND p.reorder_level > 0
    """
    params = {}
    if warehouse_id is not None:
        params["wid"] = warehouse_id
    
    query += " ORDER BY (current_stock - p.reorder_level) ASC"
    
    df = read_sql(query, params if params else None)
    if df.empty:
        return df
    return df[df['current_stock'] < df['reorder_level']]


# =========================================================
# DAMAGED GOODS ENTRY
# =========================================================
def post_damaged_goods(product_id, warehouse_id, quantity, reason=None,
                       batch_id=None, reference_number=None):
    """
    Record damaged goods — posts a DAMAGE (negative) movement.
    quantity must be positive; the function flips it to negative.
    """
    if quantity <= 0:
        return False, "Quantity must be positive"
    if not reason:
        return False, "Reason required for damaged goods"
    
    ok, msg, _ = post_movement(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity_change=-abs(quantity),
        movement_type="DAMAGE",
        reference_number=reference_number or f"DMG-{date.today().strftime('%Y%m%d')}",
        batch_id=batch_id,
        reason=reason,
    )
    return ok, msg


def get_damaged_goods_log(from_date=None, to_date=None):
    query = """
        SELECT 
            sm.id,
            sm.movement_date,
            sm.reference_number,
            p.product_code,
            p.product_name,
            p.unit,
            w.code as warehouse_code,
            sm.quantity_change,
            sm.reason,
            u.username as created_by
        FROM stock_movements sm
        JOIN products p ON sm.product_id = p.id
        JOIN warehouses w ON sm.warehouse_id = w.id
        LEFT JOIN users u ON sm.created_by = u.id
        WHERE sm.movement_type = 'DAMAGE'
    """
    params = {}
    if from_date:
        query += " AND sm.movement_date >= :fd"; params["fd"] = from_date
    if to_date:
        query += " AND sm.movement_date <= :td"; params["td"] = to_date
    query += " ORDER BY sm.movement_date DESC, sm.id DESC LIMIT 500"
    return read_sql(query, params if params else None)
