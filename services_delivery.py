# =========================================================
# services_delivery.py
# Delivery Confirmation Service Layer
# =========================================================
# Flow:
#   Dispatch (Dispatched) →
#     Create Delivery (Pending) with line items copied from dispatch_items
#     Confirm Delivery:
#       - Received qty = dispatched → mark Delivered
#       - Received qty < dispatched → mark Partially Delivered,
#         post RETURN movement for the shortfall back to the dispatch warehouse
#       - Rejected qty → also RETURN movement with reason
# =========================================================

import streamlit as st
from datetime import datetime, date
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql
from services_dispatch import get_dispatch, get_dispatch_items
from services_inventory import post_movement


REJECTION_REASONS = [
    "Damaged",
    "Wrong item",
    "Refused",
    "Short delivery",
    "Expired",
    "Other",
]


# =========================================================
# NUMBER GENERATION
# =========================================================
def generate_delivery_number():
    """DLV-{YYYY}-{SEQ}"""
    conn = get_db_connection()
    if not conn:
        return f"DLV-{datetime.now().year}-0001"
    
    try:
        year = datetime.now().year
        pattern = f"DLV-{year}-%"
        result = conn.execute(text("""
            SELECT delivery_number FROM deliveries
            WHERE delivery_number LIKE :pat
            ORDER BY id DESC LIMIT 1
        """), {"pat": pattern}).fetchone()
        
        if result and result[0]:
            try:
                num = int(result[0].split("-")[-1])
                return f"DLV-{year}-{str(num + 1).zfill(4)}"
            except:
                return f"DLV-{year}-0001"
        return f"DLV-{year}-0001"
    except:
        return f"DLV-{year}-0001"
    finally:
        conn.close()


# =========================================================
# CREATE DELIVERY FROM DISPATCH
# =========================================================
def create_delivery_from_dispatch(dispatch_id, delivery_date=None, delivered_by=None):
    """
    Creates a Pending delivery + line items copied from the dispatch.
    Idempotent: if an active delivery already exists for this dispatch, returns it.
    """
    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None
    
    try:
        # Guard against duplicates
        existing = conn.execute(text("""
            SELECT id, delivery_number FROM deliveries
            WHERE dispatch_id = :did AND status IN ('Pending', 'Partially Delivered', 'Delivered')
            ORDER BY id DESC LIMIT 1
        """), {"did": dispatch_id}).fetchone()
        
        if existing:
            conn.close()
            return True, f"ℹ️ Delivery {existing[1]} already exists for this dispatch", existing[0]
        
        disp = get_dispatch(dispatch_id)
        if disp is None:
            conn.close()
            return False, "Dispatch not found", None
        
        if disp['status'] != 'Dispatched':
            conn.close()
            return False, f"Dispatch status is '{disp['status']}' — must be 'Dispatched'", None
        
        items = get_dispatch_items(dispatch_id)
        if items.empty:
            conn.close()
            return False, "Dispatch has no line items", None
        
        delivery_number = generate_delivery_number()
        delivery_date = delivery_date or date.today()
        
        result = conn.execute(text("""
            INSERT INTO deliveries (
                delivery_number, dispatch_id, delivery_date,
                delivered_by, status, notes,
                is_partial, created_at, updated_at
            ) VALUES (
                :num, :did, :ddate,
                :dby, 'Pending', :notes,
                FALSE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "num": delivery_number,
            "did": dispatch_id,
            "ddate": delivery_date,
            "dby": delivered_by,
            "notes": f"Auto-created from dispatch {disp['dispatch_number']}",
        })
        
        delivery_id = result.fetchone()[0]
        
        # Copy line items — default received = dispatched, rejected = 0
        for _, it in items.iterrows():
            conn.execute(text("""
                INSERT INTO delivery_items (
                    delivery_id, product_id, batch_id,
                    quantity_dispatched, quantity_received,
                    quantity_rejected, created_at
                ) VALUES (
                    :dlv, :pid, :bid,
                    :qdisp, :qdisp,
                    0, CURRENT_TIMESTAMP
                )
            """), {
                "dlv": delivery_id,
                "pid": it['product_id'],
                "bid": it['batch_id'],
                "qdisp": it['quantity_dispatched'],
            })
        
        conn.commit()
        log_audit("CREATE_DELIVERY", "deliveries", delivery_id,
                  new_values={"delivery_number": delivery_number,
                              "dispatch_id": dispatch_id})
        
        return True, f"✅ Delivery {delivery_number} created (Pending)", delivery_id
    
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        try: conn.close()
        except: pass


# =========================================================
# UPDATE DELIVERY LINE
# =========================================================
def update_delivery_item(item_id, quantity_received=None, quantity_rejected=None,
                         rejection_reason=None, notes=None):
    """Update a delivery line item before confirmation"""
    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    
    try:
        row = conn.execute(text("""
            SELECT delivery_id, quantity_dispatched FROM delivery_items WHERE id = :id
        """), {"id": item_id}).fetchone()
        
        if not row:
            return False, "Item not found"
        
        delivery_id, qdisp = row
        
        d = conn.execute(text("""
            SELECT status FROM deliveries WHERE id = :id
        """), {"id": delivery_id}).fetchone()
        
        if d and d[0] != 'Pending':
            return False, f"Cannot edit — delivery is '{d[0]}'"
        
        updates = []
        params = {"id": item_id}
        
        if quantity_received is not None:
            updates.append("quantity_received = :qrec")
            params["qrec"] = quantity_received
        if quantity_rejected is not None:
            updates.append("quantity_rejected = :qrej")
            params["qrej"] = quantity_rejected
        if rejection_reason is not None:
            updates.append("rejection_reason = :rrej")
            params["rrej"] = rejection_reason
        if notes is not None:
            updates.append("notes = :notes")
            params["notes"] = notes
        
        if not updates:
            return False, "No fields to update"
        
        conn.execute(text(
            f"UPDATE delivery_items SET {', '.join(updates)} WHERE id = :id"
        ), params)
        conn.commit()
        return True, "✅ Item updated"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


# =========================================================
# CONFIRM DELIVERY
# =========================================================
def confirm_delivery(delivery_id, received_by_name=None, received_by_phone=None,
                     signature_ref=None, photo_url=None, delivery_notes=None):
    """
    Confirm a delivery:
      - Validate all line items
      - Post RETURN movements for rejected/undelivered quantities
      - Mark delivery Delivered or Partially Delivered
    """
    if not received_by_name:
        return False, "Received by name is required"
    
    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    
    try:
        header = conn.execute(text("""
            SELECT delivery_number, dispatch_id, status
            FROM deliveries WHERE id = :id
        """), {"id": delivery_id}).fetchone()
        
        if not header:
            return False, "Delivery not found"
        
        dln_number, dispatch_id, status = header
        
        if status != 'Pending':
            return False, f"Delivery is '{status}' — cannot confirm again"
        
        disp = get_dispatch(dispatch_id)
        if disp is None:
            return False, "Linked dispatch not found"
        
        warehouse_id = disp['warehouse_id']
        
        items = conn.execute(text("""
            SELECT id, product_id, batch_id,
                   quantity_dispatched, quantity_received, quantity_rejected,
                   rejection_reason
            FROM delivery_items WHERE delivery_id = :did
        """), {"did": delivery_id}).fetchall()
        
        if not items:
            return False, "No line items"
        
        # Validate
        for row in items:
            iid, pid, bid, qdisp, qrec, qrej, rreason = row
            qdisp = float(qdisp or 0); qrec = float(qrec or 0); qrej = float(qrej or 0)
            
            if qrec + qrej > qdisp + 0.0001:
                return False, (
                    f"Line {iid}: received ({qrec}) + rejected ({qrej}) "
                    f"exceeds dispatched ({qdisp})"
                )
            if qrej > 0 and not rreason:
                return False, f"Line {iid}: rejection reason required"
        
        conn.commit()
        conn.close()
        
        # Post RETURN movements for shortfall + rejected
        return_errors = []
        total_short = 0.0
        any_partial = False
        
        for row in items:
            iid, pid, bid, qdisp, qrec, qrej, rreason = row
            qdisp = float(qdisp or 0); qrec = float(qrec or 0); qrej = float(qrej or 0)
            shortfall = qdisp - qrec - qrej
            
            if shortfall <= 0.0001:
                continue
            
            any_partial = True
            total_short += shortfall
            
            reason = f"Delivery {dln_number} — "
            reason += f"rejected: {qrej} ({rreason or 'n/a'}), undelivered: {shortfall}"
            
            ok, msg, _ = post_movement(
                product_id=pid,
                warehouse_id=warehouse_id,
                quantity_change=shortfall,   # positive = back to warehouse
                movement_type="RETURN",
                reference_number=dln_number,
                batch_id=bid,
                reason=reason,
                reference_id=delivery_id,
                reference_table="deliveries",
            )
            if not ok:
                return_errors.append(f"Line {iid}: {msg}")
        
        # Update delivery header
        new_status = "Partially Delivered" if any_partial else "Delivered"
        
        conn = get_db_connection()
        conn.execute(text("""
            UPDATE deliveries SET
                status = :status,
                received_by_name = :rname,
                received_by_phone = :rphone,
                signature_ref = :sig,
                photo_url = :photo,
                is_partial = :partial,
                delivery_notes = :notes,
                confirmed_by = :uid,
                confirmed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {
            "status": new_status,
            "rname": received_by_name,
            "rphone": received_by_phone,
            "sig": signature_ref,
            "photo": photo_url,
            "partial": any_partial,
            "notes": delivery_notes,
            "uid": st.session_state.get('user_id'),
            "id": delivery_id,
        })
        conn.commit()
        conn.close()
        
        log_audit("CONFIRM_DELIVERY", "deliveries", delivery_id,
                  new_values={
                      "status": new_status,
                      "is_partial": any_partial,
                      "total_shortfall": total_short,
                      "received_by": received_by_name,
                  })
        
        msg = f"✅ Delivery {dln_number} confirmed — {new_status}"
        if any_partial:
            msg += f" (returned {total_short:.2f} units to stock)"
        if return_errors:
            msg += "  ⚠️ Some return movements failed: " + "; ".join(return_errors)
        
        return True, msg
    
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except: pass
        return False, f"Error: {str(e)}"


# =========================================================
# QUERIES
# =========================================================
def get_deliveries(status_filter=None, search=None):
    query = """
        SELECT 
            d.id,
            d.delivery_number,
            d.delivery_date,
            d.status,
            d.is_partial,
            d.received_by_name,
            d.confirmed_at,
            dsp.dispatch_number,
            dsp.driver_name,
            w.code as warehouse_code,
            c.customer_name,
            so.order_number,
            (SELECT COUNT(*) FROM delivery_items WHERE delivery_id = d.id) as items_count
        FROM deliveries d
        LEFT JOIN dispatches dsp ON d.dispatch_id = dsp.id
        LEFT JOIN warehouses w ON dsp.warehouse_id = w.id
        LEFT JOIN sales_orders so ON dsp.order_id = so.id
        LEFT JOIN customers c ON so.customer_id = c.id
        WHERE 1=1
    """
    params = {}
    
    if status_filter and status_filter != "All":
        query += " AND d.status = :status"
        params["status"] = status_filter
    
    if search:
        query += " AND (LOWER(d.delivery_number) LIKE :s OR LOWER(c.customer_name) LIKE :s OR LOWER(dsp.dispatch_number) LIKE :s)"
        params["s"] = f"%{search.lower()}%"
    
    query += " ORDER BY d.id DESC LIMIT 500"
    return read_sql(query, params if params else None)


def get_delivery(delivery_id):
    df = read_sql("""
        SELECT 
            d.*,
            dsp.dispatch_number,
            dsp.dispatch_date,
            dsp.driver_name,
            dsp.warehouse_id,
            w.code as warehouse_code,
            w.name as warehouse_name,
            so.order_number,
            c.customer_code,
            c.customer_name,
            c.address as customer_address,
            c.phone as customer_phone,
            v.plate_number
        FROM deliveries d
        LEFT JOIN dispatches dsp ON d.dispatch_id = dsp.id
        LEFT JOIN warehouses w ON dsp.warehouse_id = w.id
        LEFT JOIN sales_orders so ON dsp.order_id = so.id
        LEFT JOIN customers c ON so.customer_id = c.id
        LEFT JOIN vehicles v ON dsp.vehicle_id = v.id
        WHERE d.id = :id
    """, {"id": delivery_id})
    return None if df.empty else df.iloc[0]


def get_delivery_items(delivery_id):
    return read_sql("""
        SELECT 
            di.*,
            p.product_code,
            p.product_name,
            p.unit,
            pb.batch_number
        FROM delivery_items di
        JOIN products p ON di.product_id = p.id
        LEFT JOIN product_batches pb ON di.batch_id = pb.id
        WHERE di.delivery_id = :did
        ORDER BY di.id
    """, {"did": delivery_id})


# =========================================================
# PERFORMANCE REPORT
# =========================================================
def get_delivery_performance(from_date=None, to_date=None):
    """Variance + on-time stats"""
    query = """
        SELECT 
            c.customer_name,
            COUNT(DISTINCT d.id) as deliveries_count,
            SUM(CASE WHEN d.is_partial = TRUE THEN 1 ELSE 0 END) as partial_count,
            COALESCE(SUM(di.quantity_dispatched), 0) as total_dispatched,
            COALESCE(SUM(di.quantity_received), 0) as total_received,
            COALESCE(SUM(di.quantity_rejected), 0) as total_rejected
        FROM deliveries d
        LEFT JOIN delivery_items di ON di.delivery_id = d.id
        LEFT JOIN dispatches dsp ON d.dispatch_id = dsp.id
        LEFT JOIN sales_orders so ON dsp.order_id = so.id
        LEFT JOIN customers c ON so.customer_id = c.id
        WHERE d.status IN ('Delivered', 'Partially Delivered')
    """
    params = {}
    
    if from_date:
        query += " AND d.delivery_date >= :fd"
        params["fd"] = from_date
    if to_date:
        query += " AND d.delivery_date <= :td"
        params["td"] = to_date
    
    query += " GROUP BY c.customer_name ORDER BY c.customer_name"
    return read_sql(query, params if params else None)


def generate_delivery_note_html(delivery_id):
    """Printable delivery note / POD"""
    d = get_delivery(delivery_id)
    if d is None:
        return None
    
    items = get_delivery_items(delivery_id)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <title>Delivery Note {d['delivery_number']}</title>
    <style>
        @page {{ size: A4; margin: 15mm; }}
        body {{ font-family: Arial, sans-serif; font-size: 10pt; color: #000; }}
        .header {{ text-align: center; border-bottom: 2px solid #0c4a6e; padding-bottom: 12px; }}
        .header h1 {{ margin: 0; color: #0c4a6e; }}
        .header h2 {{ margin: 4px 0; font-size: 12pt; }}
        .meta {{ display: flex; justify-content: space-between; margin: 20px 0; }}
        .meta div {{ line-height: 1.6; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #0c4a6e; color: white; padding: 8px; text-align: left; font-size: 9pt; }}
        td {{ padding: 8px; border-bottom: 1px solid #e5e7eb; font-size: 9pt; }}
        .variance {{ background: #fef3c7; }}
        .signature {{ margin-top: 50px; display: flex; justify-content: space-between; }}
        .signature div {{ border-top: 1px solid #000; width: 45%; padding-top: 6px; text-align: center; }}
        .footer {{ margin-top: 40px; text-align: center; font-size: 9pt; color: #666; }}
        .status {{ display:inline-block; padding:3px 10px; border-radius:12px; font-size:10pt; font-weight:bold; background:#d1fae5; color:#065f46; }}
        .status.partial {{ background:#fef3c7; color:#92400e; }}
    </style>
    </head>
    <body>
        <div class="header">
            <h1>AMIGOZ WATER DISTILLING COMPANY</h1>
            <h2>DELIVERY NOTE &amp; PROOF OF DELIVERY</h2>
            <h3>{d['delivery_number']}</h3>
        </div>
        <div class="meta">
            <div>
                <strong>Delivery Date:</strong> {d['delivery_date']}<br>
                <strong>Dispatch #:</strong> {d.get('dispatch_number') or '—'}<br>
                <strong>Vehicle:</strong> {d.get('plate_number') or '—'}<br>
                <strong>Driver:</strong> {d.get('driver_name') or '—'}<br>
            </div>
            <div style="text-align: right;">
                <strong>Customer:</strong> {d.get('customer_name') or '—'}<br>
                <strong>Order Ref:</strong> {d.get('order_number') or '—'}<br>
                <strong>Status:</strong>
                <span class="status {'partial' if d.get('is_partial') else ''}">{d['status']}</span><br>
            </div>
        </div>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Product</th>
                    <th>Batch</th>
                    <th style="text-align:right;">Dispatched</th>
                    <th style="text-align:right;">Received</th>
                    <th style="text-align:right;">Rejected</th>
                    <th>Reason</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for idx, it in items.iterrows():
        qd = float(it['quantity_dispatched'] or 0)
        qr = float(it['quantity_received'] or 0)
        qj = float(it['quantity_rejected'] or 0)
        row_class = ' class="variance"' if (qr + qj) < qd else ''
        html += f"""
            <tr{row_class}>
                <td>{idx + 1}</td>
                <td>{it['product_name']}</td>
                <td>{it.get('batch_number') or '—'}</td>
                <td style="text-align:right;">{qd:,.2f}</td>
                <td style="text-align:right;">{qr:,.2f}</td>
                <td style="text-align:right;">{qj:,.2f}</td>
                <td>{it.get('rejection_reason') or ''}</td>
            </tr>
        """
    
    html += f"""
            </tbody>
        </table>
        
        <p><strong>Received by:</strong> {d.get('received_by_name') or '—'}
           &nbsp;&nbsp; <strong>Phone:</strong> {d.get('received_by_phone') or '—'}</p>
        <p><strong>Signature reference:</strong> {d.get('signature_ref') or '—'}</p>
        <p><strong>Notes:</strong> {d.get('delivery_notes') or '—'}</p>
        
        <div class="signature">
            <div>Delivered By (Driver)</div>
            <div>Received By (Customer)</div>
        </div>
        
        <div class="footer">
            <p>Amigoz Water Distilling Company | P.O. Box 0000 | Kenya</p>
        </div>
    </body>
    </html>
    """
    return html
