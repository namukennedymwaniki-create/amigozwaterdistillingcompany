# =========================================================
# services_dispatch.py
# Dispatch Service Layer — FIFO batch selection + stock OUT
# =========================================================

import streamlit as st
from datetime import datetime, date
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql
from services_inventory import post_movement, get_stock_balance
from services_quality import get_available_stock, is_batch_sellable
from services_reservations import release_reservations_for_reference


DISPATCH_STATUSES = ["Draft", "Picked", "Dispatched", "Delivered", "Cancelled"]


def generate_dispatch_number():
    """DSP-{YYYY}-{SEQ}"""
    conn = get_db_connection()
    if not conn:
        return f"DSP-{datetime.now().year}-0001"
    
    try:
        year = datetime.now().year
        pattern = f"DSP-{year}-%"
        
        result = conn.execute(text("""
            SELECT dispatch_number FROM dispatches
            WHERE dispatch_number LIKE :pat
            ORDER BY id DESC LIMIT 1
        """), {"pat": pattern}).fetchone()
        
        if result and result[0]:
            try:
                num = int(result[0].split("-")[-1])
                return f"DSP-{year}-{str(num + 1).zfill(4)}"
            except:
                return f"DSP-{year}-0001"
        return f"DSP-{year}-0001"
    except:
        return f"DSP-{year}-0001"
    finally:
        conn.close()


def get_fifo_batches(product_id, warehouse_id, quantity_needed):
    """
    Return batches in FIFO order (oldest expiry first) that are:
      - Released + non-expired
      - Have enough stock in this warehouse
    Returns list of dicts: [{batch_id, batch_number, available, expiry_date}, ...]
    """
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        rows = conn.execute(text("""
            SELECT 
                pb.id,
                pb.batch_number,
                pb.expiry_date,
                COALESCE(SUM(sm.quantity_change), 0) as balance
            FROM product_batches pb
            LEFT JOIN stock_movements sm 
                ON sm.batch_id = pb.id 
                AND sm.warehouse_id = :wid
                AND sm.is_posted = 1
            WHERE pb.product_id = :pid
              AND pb.quality_status = 'Released'
              AND (pb.expiry_date IS NULL OR pb.expiry_date >= :today)
            GROUP BY pb.id, pb.batch_number, pb.expiry_date
            HAVING COALESCE(SUM(sm.quantity_change), 0) > 0
            ORDER BY pb.expiry_date ASC NULLS LAST, pb.id ASC
        """), {
            "wid": warehouse_id,
            "pid": product_id,
            "today": date.today(),
        }).fetchall()
        
        batches = []
        remaining = quantity_needed
        
        for row in rows:
            available = float(row[3] or 0)
            if available <= 0:
                continue
            
            take = min(available, remaining)
            batches.append({
                "batch_id": row[0],
                "batch_number": row[1],
                "expiry_date": row[2],
                "available": available,
                "suggested_qty": take,
            })
            remaining -= take
            if remaining <= 0:
                break
        
        return batches
    
    except Exception as e:
        print(f"FIFO error: {e}")
        return []
    finally:
        conn.close()


def create_dispatch(order_id=None, customer_name=None, warehouse_id=None,
                    dispatch_date=None, vehicle_id=None, driver_name=None,
                    notes=None, items=None):
    """
    Create a dispatch header (Draft status).
    items: list of dicts [{product_id, batch_id, quantity}, ...]
    """
    if not warehouse_id:
        return False, "Warehouse required", None
    
    if not items:
        return False, "At least one line item required", None
    
    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None
    
    try:
        dispatch_number = generate_dispatch_number()
        dispatch_date = dispatch_date or date.today()
        
        result = conn.execute(text("""
            INSERT INTO dispatches (
                dispatch_number, order_id, warehouse_id, dispatch_date,
                driver_name, status, notes, created_by,
                created_at, updated_at
            ) VALUES (
                :num, :oid, :wid, :ddate,
                :drv, 'Draft', :notes, :uid,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "num": dispatch_number,
            "oid": order_id,
            "wid": warehouse_id,
            "ddate": dispatch_date,
            "drv": driver_name,
            "notes": notes,
            "uid": st.session_state.get('user_id'),
        })
        
        dispatch_id = result.fetchone()[0]
        
        # Insert line items
        for it in items:
            conn.execute(text("""
                INSERT INTO dispatch_items (
                    dispatch_id, product_id, batch_id, quantity_dispatched, created_at
                ) VALUES (
                    :did, :pid, :bid, :qty, CURRENT_TIMESTAMP
                )
            """), {
                "did": dispatch_id,
                "pid": it['product_id'],
                "bid": it.get('batch_id'),
                "qty": it['quantity'],
            })
        
        conn.commit()
        log_audit("CREATE_DISPATCH", "dispatches", dispatch_id,
                  new_values={"dispatch_number": dispatch_number})
        
        return True, f"✅ Dispatch {dispatch_number} created (Draft)", dispatch_id
    
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


def mark_picked(dispatch_id, picked_by=None):
    """Mark a dispatch as picked (ready for dispatch)"""
    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    
    try:
        conn.execute(text("""
            UPDATE dispatches
            SET status = 'Picked',
                picked_by = :picked,
                picked_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id AND status = 'Draft'
        """), {
            "id": dispatch_id,
            "picked": picked_by or st.session_state.get('user_id'),
        })
        conn.commit()
        log_audit("DISPATCH_PICKED", "dispatches", dispatch_id)
        return True, "✅ Marked as picked"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


def confirm_dispatch(dispatch_id, override_negative=False):
    """
    Confirm a dispatch:
    - Post stock OUT movements for each line item
    - Release any active reservations linked to the same reference
    - Set status to 'Dispatched'
    """
    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    
    try:
        # Load header
        header = conn.execute(text("""
            SELECT dispatch_number, order_id, warehouse_id, status
            FROM dispatches WHERE id = :id
        """), {"id": dispatch_id}).fetchone()
        
        if not header:
            return False, "Dispatch not found"
        
        dispatch_number, order_id, warehouse_id, status = header
        
        if status not in ['Draft', 'Picked']:
            return False, f"Cannot dispatch in status '{status}'"
        
        # Load items
        items = conn.execute(text("""
            SELECT id, product_id, batch_id, quantity_dispatched
            FROM dispatch_items WHERE dispatch_id = :did
        """), {"did": dispatch_id}).fetchall()
        
        if not items:
            return False, "No line items"
        
        conn.commit()
        conn.close()
        
        # Post movements (outside the transaction above)
        errors = []
        for item_id, product_id, batch_id, qty in items:
            ok, msg, _ = post_movement(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity_change=-float(qty),
                movement_type="DISPATCH",
                reference_number=dispatch_number,
                batch_id=batch_id,
                reason=f"Dispatch {dispatch_number}",
                reference_id=dispatch_id,
                reference_table="dispatches",
            )
            if not ok:
                errors.append(f"Item {item_id}: {msg}")
        
        if errors:
            return False, "❌ Some movements failed:\n" + "\n".join(errors)
        
        # Update status + release linked reservations
        conn = get_db_connection()
        conn.execute(text("""
            UPDATE dispatches
            SET status = 'Dispatched',
                dispatched_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {"id": dispatch_id})
        conn.commit()
        conn.close()
        
        if order_id:
            release_reservations_for_reference("sales_orders", order_id,
                                              reason=f"Dispatched as {dispatch_number}")
        
        log_audit("CONFIRM_DISPATCH", "dispatches", dispatch_id,
                  new_values={"dispatch_number": dispatch_number,
                              "warehouse_id": warehouse_id})
        
        return True, f"✅ Dispatch {dispatch_number} posted. Stock reduced."
    
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except:
            pass
        return False, f"Error: {str(e)}"


def mark_delivered(dispatch_id, received_by=None, notes=None):
    """Mark dispatch as delivered"""
    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    
    try:
        conn.execute(text("""
            UPDATE dispatches
            SET status = 'Delivered',
                delivered_at = CURRENT_TIMESTAMP,
                notes = COALESCE(:notes, notes),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id AND status = 'Dispatched'
        """), {"id": dispatch_id, "notes": notes})
        conn.commit()
        log_audit("DISPATCH_DELIVERED", "dispatches", dispatch_id,
                  new_values={"received_by": received_by})
        return True, "✅ Marked as delivered"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


def get_dispatches(status_filter=None, search=None):
    """List dispatches"""
    query = """
        SELECT 
            d.id,
            d.dispatch_number,
            d.dispatch_date,
            d.status,
            w.code as warehouse_code,
            w.name as warehouse_name,
            so.order_number,
            c.customer_name,
            v.plate_number,
            d.driver_name,
            (SELECT COUNT(*) FROM dispatch_items WHERE dispatch_id = d.id) as items_count
        FROM dispatches d
        LEFT JOIN warehouses w ON d.warehouse_id = w.id
        LEFT JOIN sales_orders so ON d.order_id = so.id
        LEFT JOIN customers c ON so.customer_id = c.id
        LEFT JOIN vehicles v ON d.vehicle_id = v.id
        WHERE 1=1
    """
    params = {}
    
    if status_filter and status_filter != "All":
        query += " AND d.status = :status"
        params["status"] = status_filter
    
    if search:
        query += " AND (LOWER(d.dispatch_number) LIKE :s OR LOWER(c.customer_name) LIKE :s)"
        params["s"] = f"%{search.lower()}%"
    
    query += " ORDER BY d.id DESC LIMIT 500"
    
    return read_sql(query, params if params else None)


def get_dispatch(dispatch_id):
    """Get dispatch header"""
    df = read_sql("""
        SELECT 
            d.*,
            w.code as warehouse_code,
            w.name as warehouse_name,
            so.order_number,
            c.customer_name,
            c.address as customer_address,
            c.phone as customer_phone,
            v.plate_number,
            v.description as vehicle_description
        FROM dispatches d
        LEFT JOIN warehouses w ON d.warehouse_id = w.id
        LEFT JOIN sales_orders so ON d.order_id = so.id
        LEFT JOIN customers c ON so.customer_id = c.id
        LEFT JOIN vehicles v ON d.vehicle_id = v.id
        WHERE d.id = :id
    """, {"id": dispatch_id})
    return None if df.empty else df.iloc[0]


def get_dispatch_items(dispatch_id):
    """Get dispatch line items"""
    return read_sql("""
        SELECT 
            di.id,
            di.product_id,
            di.batch_id,
            di.quantity_dispatched,
            p.product_code,
            p.product_name,
            p.unit,
            pb.batch_number
        FROM dispatch_items di
        JOIN products p ON di.product_id = p.id
        LEFT JOIN product_batches pb ON di.batch_id = pb.id
        WHERE di.dispatch_id = :did
        ORDER BY di.id
    """, {"did": dispatch_id})


def get_in_transit():
    """Dispatches not yet delivered"""
    return read_sql("""
        SELECT 
            d.id,
            d.dispatch_number,
            d.dispatch_date,
            d.status,
            w.code as warehouse_code,
            c.customer_name,
            v.plate_number,
            d.driver_name,
            (SELECT COUNT(*) FROM dispatch_items WHERE dispatch_id = d.id) as items_count
        FROM dispatches d
        LEFT JOIN warehouses w ON d.warehouse_id = w.id
        LEFT JOIN sales_orders so ON d.order_id = so.id
        LEFT JOIN customers c ON so.customer_id = c.id
        LEFT JOIN vehicles v ON d.vehicle_id = v.id
        WHERE d.status IN ('Picked', 'Dispatched')
        ORDER BY d.dispatch_date DESC
    """)


def generate_dispatch_note_html(dispatch_id):
    """Generate printable HTML dispatch note"""
    d = get_dispatch(dispatch_id)
    if d is None:
        return None
    
    items = get_dispatch_items(dispatch_id)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <title>Dispatch Note {d['dispatch_number']}</title>
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
        .signature {{ margin-top: 60px; display: flex; justify-content: space-between; }}
        .signature div {{ border-top: 1px solid #000; width: 45%; padding-top: 6px; text-align: center; }}
        .footer {{ margin-top: 40px; text-align: center; font-size: 9pt; color: #666; }}
    </style>
    </head>
    <body>
        <div class="header">
            <h1>AMIGOZ WATER DISTILLING COMPANY</h1>
            <h2>DISPATCH NOTE</h2>
            <h3>{d['dispatch_number']}</h3>
        </div>
        
        <div class="meta">
            <div>
                <strong>Dispatch Date:</strong> {d['dispatch_date']}<br>
                <strong>Warehouse:</strong> {d.get('warehouse_name', 'N/A')}<br>
                <strong>Status:</strong> {d['status']}<br>
            </div>
            <div style="text-align: right;">
                <strong>Customer:</strong> {d.get('customer_name') or 'N/A'}<br>
                <strong>Order Ref:</strong> {d.get('order_number') or 'N/A'}<br>
                <strong>Vehicle:</strong> {d.get('plate_number') or 'N/A'}<br>
                <strong>Driver:</strong> {d.get('driver_name') or 'N/A'}<br>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Product</th>
                    <th>Batch</th>
                    <th style="text-align:right;">Quantity</th>
                    <th style="text-align:right;">Unit</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for idx, it in items.iterrows():
        html += f"""
            <tr>
                <td>{idx + 1}</td>
                <td>{it['product_name']}</td>
                <td>{it.get('batch_number') or '—'}</td>
                <td style="text-align:right;">{float(it['quantity_dispatched']):,.2f}</td>
                <td style="text-align:right;">{it.get('unit') or ''}</td>
            </tr>
        """
    
    html += f"""
            </tbody>
        </table>
        
        <div class="signature">
            <div>Dispatched By</div>
            <div>Received By</div>
        </div>
        
        <div class="footer">
            <p>Amigoz Water Distilling Company | P.O. Box 0000 | Kenya</p>
        </div>
    </body>
    </html>
    """
    
    return html
