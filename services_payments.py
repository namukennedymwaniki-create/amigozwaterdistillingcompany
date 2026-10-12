# =========================================================
# services_payments.py
# Payments Service Layer
# =========================================================
# Principles:
#   - A payment reduces what a customer owes (AR) or what we owe (AP)
#   - Allocations link payments to invoices (AR) or POs (AP)
#   - Overpayments become unallocated credit
#   - Reversals are separate payments with negative effect
# =========================================================

import streamlit as st
from datetime import datetime, date, timedelta
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql


PAYMENT_METHODS = ["Cash", "M-Pesa", "Bank Transfer", "Cheque", "Card", "Other"]
PAYMENT_TYPES = ["Customer Receipt", "Supplier Payment"]


# =========================================================
# NUMBER GENERATION
# =========================================================
def generate_payment_number(is_reversal=False):
    prefix = "PAY-REV" if is_reversal else "PAY"
    conn = get_db_connection()
    if not conn:
        return f"{prefix}-{datetime.now().year}-0001"
    try:
        year = datetime.now().year
        pattern = f"{prefix}-{year}-%"
        result = conn.execute(text("""
            SELECT payment_number FROM payments
            WHERE payment_number LIKE :pat
            ORDER BY id DESC LIMIT 1
        """), {"pat": pattern}).fetchone()
        if result and result[0]:
            try:
                n = int(result[0].split("-")[-1])
                return f"{prefix}-{year}-{str(n + 1).zfill(4)}"
            except:
                return f"{prefix}-{year}-0001"
        return f"{prefix}-{year}-0001"
    except:
        return f"{prefix}-{year}-0001"
    finally:
        conn.close()


# =========================================================
# CUSTOMER RECEIPTS
# =========================================================
def record_customer_payment(customer_id, amount, payment_date=None,
                            payment_method="Cash", reference_number=None,
                            notes=None, allocations=None, auto_allocate=True):
    """
    Record a customer receipt.
    
    allocations: optional list [{invoice_id, amount}, ...]
                 If auto_allocate=True and allocations is None,
                 FIFO-allocate to oldest unpaid invoices.
    """
    if not customer_id:
        return False, "Customer required", None
    if amount <= 0:
        return False, "Amount must be positive", None
    
    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None
    try:
        payment_date = payment_date or date.today()
        payment_number = generate_payment_number()
        
        # Insert payment
        result = conn.execute(text("""
            INSERT INTO payments (
                payment_number, payment_date, payment_type,
                customer_id, amount, payment_method, reference_number,
                notes, unallocated_amount, is_reversal,
                received_by, created_by, created_at, confirmed_at
            ) VALUES (
                :num, :pdate, 'Customer Receipt',
                :cid, :amt, :method, :ref,
                :notes, :amt, FALSE,
                :uid, :uid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "num": payment_number, "pdate": payment_date,
            "cid": customer_id, "amt": amount, "method": payment_method,
            "ref": reference_number, "notes": notes,
            "uid": st.session_state.get('user_id'),
        })
        payment_id = result.fetchone()[0]
        
        # Determine allocations
        if allocations is None and auto_allocate:
            allocations = _auto_allocate_to_invoices(conn, customer_id, amount)
        elif allocations is None:
            allocations = []
        
        allocated_total = 0.0
        for a in allocations:
            alloc_amount = float(a['amount'])
            if alloc_amount <= 0:
                continue
            if allocated_total + alloc_amount > amount + 0.0001:
                return False, "Allocations exceed payment amount", None
            
            # Insert allocation
            conn.execute(text("""
                INSERT INTO payment_allocations (
                    payment_id, invoice_id, amount, notes, created_at
                ) VALUES (
                    :pid, :iid, :amt, :notes, CURRENT_TIMESTAMP
                )
            """), {
                "pid": payment_id, "iid": a['invoice_id'],
                "amt": alloc_amount, "notes": a.get('notes'),
            })
            
            # Update invoice amount_paid + balance_due + status
            _update_invoice_after_payment(conn, a['invoice_id'], alloc_amount)
            
            allocated_total += alloc_amount
        
        unallocated = amount - allocated_total
        
        # Update payment with unallocated amount
        conn.execute(text("""
            UPDATE payments SET unallocated_amount = :un WHERE id = :id
        """), {"un": unallocated, "id": payment_id})
        
        conn.commit()
        log_audit("RECORD_CUSTOMER_PAYMENT", "payments", payment_id,
                  new_values={"payment_number": payment_number,
                              "customer_id": customer_id,
                              "amount": amount,
                              "allocated": allocated_total,
                              "unallocated": unallocated})
        
        msg = f"✅ Payment {payment_number} recorded — KES {amount:,.2f}"
        if unallocated > 0:
            msg += f" (unallocated credit: KES {unallocated:,.2f})"
        return True, msg, payment_id
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


def _auto_allocate_to_invoices(conn, customer_id, amount):
    """FIFO-allocate to oldest unpaid/partial invoices"""
    rows = conn.execute(text("""
        SELECT id, balance_due
        FROM invoices
        WHERE customer_id = :cid
          AND status IN ('Unpaid', 'Partial')
          AND balance_due > 0
        ORDER BY invoice_date ASC, id ASC
    """), {"cid": customer_id}).fetchall()
    
    allocations = []
    remaining = amount
    for invoice_id, balance in rows:
        balance = float(balance or 0)
        if balance <= 0:
            continue
        take = min(balance, remaining)
        allocations.append({"invoice_id": invoice_id, "amount": take})
        remaining -= take
        if remaining <= 0.0001:
            break
    return allocations


def _update_invoice_after_payment(conn, invoice_id, amount):
    """Increment amount_paid; recompute balance_due + status"""
    conn.execute(text("""
        UPDATE invoices
        SET amount_paid = amount_paid + :amt,
            balance_due = total_amount - (amount_paid + :amt),
            status = CASE 
                WHEN (amount_paid + :amt) >= total_amount - 0.01 THEN 'Paid'
                WHEN (amount_paid + :amt) > 0 THEN 'Partial'
                ELSE 'Unpaid'
            END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = :id
    """), {"amt": amount, "id": invoice_id})


# =========================================================
# SUPPLIER PAYMENTS
# =========================================================
def record_supplier_payment(supplier_id, amount, payment_date=None,
                            payment_method="Bank Transfer", reference_number=None,
                            notes=None, allocations=None, auto_allocate=True):
    """
    Record a supplier payment.
    allocations: [{po_id, amount}]
    """
    if not supplier_id:
        return False, "Supplier required", None
    if amount <= 0:
        return False, "Amount must be positive", None
    
    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None
    try:
        payment_date = payment_date or date.today()
        payment_number = generate_payment_number()
        
        result = conn.execute(text("""
            INSERT INTO payments (
                payment_number, payment_date, payment_type,
                supplier_id, amount, payment_method, reference_number,
                notes, unallocated_amount, is_reversal,
                received_by, created_by, created_at, confirmed_at
            ) VALUES (
                :num, :pdate, 'Supplier Payment',
                :sid, :amt, :method, :ref,
                :notes, :amt, FALSE,
                :uid, :uid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "num": payment_number, "pdate": payment_date,
            "sid": supplier_id, "amt": amount, "method": payment_method,
            "ref": reference_number, "notes": notes,
            "uid": st.session_state.get('user_id'),
        })
        payment_id = result.fetchone()[0]
        
        if allocations is None and auto_allocate:
            allocations = _auto_allocate_to_pos(conn, supplier_id, amount)
        elif allocations is None:
            allocations = []
        
        allocated_total = 0.0
        for a in allocations:
            alloc_amount = float(a['amount'])
            if alloc_amount <= 0:
                continue
            if allocated_total + alloc_amount > amount + 0.0001:
                return False, "Allocations exceed payment amount", None
            
            conn.execute(text("""
                INSERT INTO supplier_payment_allocations (
                    payment_id, po_id, amount, notes, created_at
                ) VALUES (
                    :pid, :poid, :amt, :notes, CURRENT_TIMESTAMP
                )
            """), {
                "pid": payment_id, "poid": a['po_id'],
                "amt": alloc_amount, "notes": a.get('notes'),
            })
            allocated_total += alloc_amount
        
        unallocated = amount - allocated_total
        conn.execute(text("""
            UPDATE payments SET unallocated_amount = :un WHERE id = :id
        """), {"un": unallocated, "id": payment_id})
        
        conn.commit()
        log_audit("RECORD_SUPPLIER_PAYMENT", "payments", payment_id,
                  new_values={"payment_number": payment_number,
                              "supplier_id": supplier_id,
                              "amount": amount,
                              "allocated": allocated_total})
        
        msg = f"✅ Payment {payment_number} recorded — KES {amount:,.2f}"
        if unallocated > 0:
            msg += f" (unallocated: KES {unallocated:,.2f})"
        return True, msg, payment_id
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


def _auto_allocate_to_pos(conn, supplier_id, amount):
    """FIFO-allocate to oldest approved/received POs"""
    rows = conn.execute(text("""
        SELECT id, total_amount
        FROM purchase_orders
        WHERE supplier_id = :sid
          AND status IN ('Approved', 'Partially Received', 'Fully Received')
        ORDER BY order_date ASC, id ASC
    """), {"sid": supplier_id}).fetchall()
    
    allocations = []
    remaining = amount
    for po_id, total in rows:
        total = float(total or 0)
        if total <= 0:
            continue
        take = min(total, remaining)
        allocations.append({"po_id": po_id, "amount": take})
        remaining -= take
        if remaining <= 0.0001:
            break
    return allocations


# =========================================================
# REVERSAL
# =========================================================
def reverse_payment(payment_id, reason=None):
    """
    Create a reversal payment. The reversal has negative effect:
    - Invoices previously paid are decremented back
    - A new payment row is created with is_reversal=True
    """
    if not reason:
        return False, "Reversal reason required", None
    
    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None
    try:
        orig = conn.execute(text("""
            SELECT payment_number, payment_type, customer_id, supplier_id,
                   amount, is_reversal
            FROM payments WHERE id = :id
        """), {"id": payment_id}).fetchone()
        if not orig:
            return False, "Payment not found", None
        if orig[5]:
            return False, "Cannot reverse a reversal", None
        
        rev_number = generate_payment_number(is_reversal=True)
        amount = float(orig[4] or 0)
        payment_type = orig[1]
        
        # Create reversal row
        result = conn.execute(text("""
            INSERT INTO payments (
                payment_number, payment_date, payment_type,
                customer_id, supplier_id, amount, payment_method,
                reference_number, notes, unallocated_amount,
                is_reversal, reverses_payment_id,
                created_by, created_at
            ) VALUES (
                :num, CURRENT_DATE, :ptype,
                :cid, :sid, :amt, 'Reversal',
                :ref, :notes, 0,
                TRUE, :orig,
                :uid, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "num": rev_number, "ptype": payment_type,
            "cid": orig[2], "sid": orig[3], "amt": amount,
            "ref": orig[0], "notes": f"Reversal of {orig[0]}: {reason}",
            "orig": payment_id, "uid": st.session_state.get('user_id'),
        })
        rev_id = result.fetchone()[0]
        
        # Reverse invoice allocations
        inv_allocs = conn.execute(text("""
            SELECT invoice_id, amount FROM payment_allocations
            WHERE payment_id = :id
        """), {"id": payment_id}).fetchall()
        
        for invoice_id, alloc_amt in inv_allocs:
            _update_invoice_after_payment(conn, invoice_id, -float(alloc_amt))
            # Reverse allocate
            conn.execute(text("""
                INSERT INTO payment_allocations (
                    payment_id, invoice_id, amount, notes, created_at
                ) VALUES (:pid, :iid, :amt, 'Reversal', CURRENT_TIMESTAMP)
            """), {"pid": rev_id, "iid": invoice_id, "amt": -float(alloc_amt)})
        
        # Reverse supplier allocations
        sp_allocs = conn.execute(text("""
            SELECT po_id, amount FROM supplier_payment_allocations
            WHERE payment_id = :id
        """), {"id": payment_id}).fetchall()
        
        for po_id, alloc_amt in sp_allocs:
            conn.execute(text("""
                INSERT INTO supplier_payment_allocations (
                    payment_id, po_id, amount, notes, created_at
                ) VALUES (:pid, :poid, :amt, 'Reversal', CURRENT_TIMESTAMP)
            """), {"pid": rev_id, "poid": po_id, "amt": -float(alloc_amt)})
        
        conn.commit()
        log_audit("REVERSE_PAYMENT", "payments", rev_id,
                  new_values={"original_payment": orig[0],
                              "reversal_number": rev_number,
                              "reason": reason})
        
        return True, f"✅ Payment {orig[0]} reversed as {rev_number}", rev_id
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


# =========================================================
# QUERIES
# =========================================================
def get_payments(payment_type=None, search=None, from_date=None, to_date=None):
    query = """
        SELECT 
            p.id, p.payment_number, p.payment_date, p.payment_type,
            p.amount, p.unallocated_amount, p.payment_method,
            p.reference_number, p.is_reversal,
            c.customer_code, c.customer_name,
            s.supplier_code, s.supplier_name
        FROM payments p
        LEFT JOIN customers c ON p.customer_id = c.id
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE 1=1
    """
    params = {}
    if payment_type and payment_type != "All":
        query += " AND p.payment_type = :pt"
        params["pt"] = payment_type
    if from_date:
        query += " AND p.payment_date >= :fd"; params["fd"] = from_date
    if to_date:
        query += " AND p.payment_date <= :td"; params["td"] = to_date
    if search:
        query += """ AND (LOWER(p.payment_number) LIKE :s
                        OR LOWER(c.customer_name) LIKE :s
                        OR LOWER(s.supplier_name) LIKE :s)"""
        params["s"] = f"%{search.lower()}%"
    query += " ORDER BY p.id DESC LIMIT 500"
    return read_sql(query, params if params else None)


def get_payment(payment_id):
    df = read_sql("""
        SELECT p.*, 
               c.customer_code, c.customer_name, c.address as customer_address,
               c.phone as customer_phone, c.email as customer_email,
               s.supplier_code, s.supplier_name,
               orig.payment_number as original_payment_number
        FROM payments p
        LEFT JOIN customers c ON p.customer_id = c.id
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        LEFT JOIN payments orig ON p.reverses_payment_id = orig.id
        WHERE p.id = :id
    """, {"id": payment_id})
    return None if df.empty else df.iloc[0]


def get_payment_allocations(payment_id):
    """Return AR allocations with invoice details"""
    return read_sql("""
        SELECT pa.*, i.invoice_number, i.invoice_date, i.total_amount,
               i.balance_due, i.status
        FROM payment_allocations pa
        JOIN invoices i ON pa.invoice_id = i.id
        WHERE pa.payment_id = :id
        ORDER BY pa.id
    """, {"id": payment_id})


def get_supplier_payment_allocations(payment_id):
    return read_sql("""
        SELECT spa.*, po.po_number, po.order_date, po.total_amount,
               po.status
        FROM supplier_payment_allocations spa
        JOIN purchase_orders po ON spa.po_id = po.id
        WHERE spa.payment_id = :id
        ORDER BY spa.id
    """, {"id": payment_id})


# =========================================================
# CUSTOMER STATEMENT (AR)
# =========================================================
def get_customer_statement(customer_id, from_date=None, to_date=None):
    """Combine invoices and payments into a chronological ledger"""
    conn = get_db_connection()
    if not conn:
        return read_sql("SELECT 1 WHERE 1=0")
    try:
        query = """
        SELECT 
            'Invoice' as entry_type,
            i.invoice_date as entry_date,
            i.invoice_number as reference,
            i.total_amount as debit,
            0 as credit,
            i.status as status
        FROM invoices i
        WHERE i.customer_id = :cid
        UNION ALL
        SELECT 
            'Payment' as entry_type,
            p.payment_date as entry_date,
            p.payment_number as reference,
            0 as debit,
            p.amount as credit,
            p.payment_method as status
        FROM payments p
        WHERE p.customer_id = :cid AND p.payment_type = 'Customer Receipt'
        """
        params = {"cid": customer_id}
        
        if from_date:
            query = f"SELECT * FROM ({query}) x WHERE entry_date >= :fd"
            params["fd"] = from_date
        if to_date:
            query = f"SELECT * FROM ({query}) x WHERE entry_date <= :td"
            params["td"] = to_date
        
        query += " ORDER BY entry_date ASC"
        
        df = read_sql(query, params)
        if not df.empty:
            df['running_balance'] = (df['debit'] - df['credit']).cumsum()
        return df
    finally:
        conn.close()


# =========================================================
# AGING REPORT (AR)
# =========================================================
def get_ar_aging(as_of_date=None):
    """Customer aging buckets: 0-30, 31-60, 61-90, 90+"""
    as_of_date = as_of_date or date.today()
    return read_sql("""
        SELECT 
            c.customer_code,
            c.customer_name,
            COUNT(i.id) as open_invoices,
            SUM(CASE WHEN :asof - i.due_date <= 30 THEN i.balance_due ELSE 0 END) as bucket_0_30,
            SUM(CASE WHEN :asof - i.due_date BETWEEN 31 AND 60 THEN i.balance_due ELSE 0 END) as bucket_31_60,
            SUM(CASE WHEN :asof - i.due_date BETWEEN 61 AND 90 THEN i.balance_due ELSE 0 END) as bucket_61_90,
            SUM(CASE WHEN :asof - i.due_date > 90 THEN i.balance_due ELSE 0 END) as bucket_90_plus,
            SUM(i.balance_due) as total_outstanding
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        WHERE i.status IN ('Unpaid', 'Partial') AND i.balance_due > 0
        GROUP BY c.customer_code, c.customer_name
        ORDER BY total_outstanding DESC
    """, {"asof": as_of_date})


# =========================================================
# RECEIPT HTML
# =========================================================
def generate_receipt_html(payment_id):
    p = get_payment(payment_id)
    if p is None:
        return None
    
    allocs = get_payment_allocations(payment_id)
    sp_allocs = get_supplier_payment_allocations(payment_id)
    
    party_name = p.get('customer_name') or p.get('supplier_name') or '—'
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <title>Receipt {p['payment_number']}</title>
    <style>
        @page {{ size: A5; margin: 12mm; }}
        body {{ font-family: Arial, sans-serif; font-size: 10pt; color: #000; }}
        .header {{ text-align: center; border-bottom: 2px solid #0c4a6e; padding-bottom: 10px; }}
        .header h1 {{ margin: 0; color: #0c4a6e; font-size: 15pt; }}
        .header h2 {{ margin: 4px 0; font-size: 11pt; }}
        .header h3 {{ margin: 2px 0; font-size: 10pt; color: #555; }}
        .meta {{ display: flex; justify-content: space-between; margin: 14px 0; font-size: 9pt; }}
        .meta div {{ line-height: 1.55; }}
        table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
        th {{ background: #0c4a6e; color: white; padding: 6px; text-align: left; font-size: 9pt; }}
        td {{ padding: 6px; border-bottom: 1px solid #e5e7eb; font-size: 9pt; }}
        .amount-box {{ background: #f0f9ff; padding: 12px; border-radius: 6px; text-align: center; margin: 14px 0; }}
        .amount-box .amt {{ font-size: 16pt; font-weight: bold; color: #0c4a6e; }}
        .footer {{ margin-top: 24px; text-align: center; font-size: 8pt; color: #666; border-top: 1px solid #ccc; padding-top: 8px; }}
    </style>
    </head>
    <body>
        <div class="header">
            <h1>AMIGOZ WATER DISTILLING COMPANY</h1>
            <h2>{'REVERSAL ' if p.get('is_reversal') else ''}PAYMENT RECEIPT</h2>
            <h3>{p['payment_number']}</h3>
        </div>
        
        <div class="meta">
            <div>
                <strong>Date:</strong> {p['payment_date']}<br>
                <strong>Type:</strong> {p['payment_type']}<br>
                <strong>Method:</strong> {p['payment_method'] or '—'}<br>
            </div>
            <div style="text-align:right;">
                <strong>{'Customer' if p.get('customer_id') else 'Supplier'}:</strong> {party_name}<br>
                <strong>Reference:</strong> {p['reference_number'] or '—'}<br>
                <strong>Status:</strong> {'Reversal' if p.get('is_reversal') else 'Confirmed'}<br>
            </div>
        </div>
        
        <div class="amount-box">
            <div>Amount Received</div>
            <div class="amt">KES {float(p['amount']):,.2f}</div>
        </div>
    """
    
    if not allocs.empty:
        html += """
        <h4>Allocation to Invoices</h4>
        <table>
            <tr><th>Invoice #</th><th>Date</th><th style="text-align:right;">Amount</th></tr>
        """
        for _, a in allocs.iterrows():
            html += f"""
            <tr>
                <td>{a['invoice_number']}</td>
                <td>{a['invoice_date']}</td>
                <td style="text-align:right;">KES {float(a['amount']):,.2f}</td>
            </tr>
            """
        html += "</table>"
    
    if not sp_allocs.empty:
        html += """
        <h4>Allocation to Purchase Orders</h4>
        <table>
            <tr><th>PO #</th><th>Date</th><th style="text-align:right;">Amount</th></tr>
        """
        for _, a in sp_allocs.iterrows():
            html += f"""
            <tr>
                <td>{a['po_number']}</td>
                <td>{a['order_date']}</td>
                <td style="text-align:right;">KES {float(a['amount']):,.2f}</td>
            </tr>
            """
        html += "</table>"
    
    unalloc = float(p.get('unallocated_amount') or 0)
    if unalloc > 0:
        html += f"""
        <p style="background:#fef3c7;padding:8px;border-radius:6px;">
        <strong>Unallocated credit:</strong> KES {unalloc:,.2f}
        </p>
        """
    
    html += f"""
        <div class="footer">
            <p>Received by: {p.get('received_by') or '—'} | Thank you for your business</p>
            <p>Amigoz Water Distilling Company | Kenya</p>
        </div>
    </body>
    </html>
    """
    return html
