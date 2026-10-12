# =========================================================
# services_invoices.py
# Invoice generation from sales orders
# =========================================================

import streamlit as st
from datetime import datetime, date, timedelta
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql
from services_sales import get_order, get_order_items


def generate_invoice_number():
    """INV-{YYYY}-{SEQ}"""
    conn = get_db_connection()
    if not conn:
        return f"INV-{datetime.now().year}-0001"
    
    try:
        year = datetime.now().year
        pattern = f"INV-{year}-%"
        
        result = conn.execute(text("""
            SELECT invoice_number FROM invoices
            WHERE invoice_number LIKE :pat
            ORDER BY id DESC LIMIT 1
        """), {"pat": pattern}).fetchone()
        
        if result and result[0]:
            try:
                num = int(result[0].split("-")[-1])
                return f"INV-{year}-{str(num + 1).zfill(4)}"
            except:
                return f"INV-{year}-0001"
        return f"INV-{year}-0001"
    except:
        return f"INV-{year}-0001"
    finally:
        conn.close()


def create_invoice_from_order(order_id):
    """Generate an invoice from a confirmed order"""
    conn = get_db_connection()
    if not conn:
        return False, "DB connection failed", None
    
    try:
        order = get_order(order_id)
        if order is None:
            return False, "Order not found", None
        
        if order['status'] not in ['Confirmed', 'Dispatched']:
            return False, f"Cannot invoice order in '{order['status']}' status", None
        
        items = get_order_items(order_id)
        if items.empty:
            return False, "No items to invoice", None
        
        invoice_number = generate_invoice_number()
        
        # Payment terms → due date
        customer_terms = "30 days"
        customer_row = read_sql("SELECT payment_terms FROM customers WHERE id = :id",
                                {"id": order['customer_id']})
        if not customer_row.empty:
            customer_terms = customer_row.iloc[0]['payment_terms'] or "30 days"
        
        try:
            days = int(''.join(filter(str.isdigit, customer_terms)))
        except:
            days = 30
        
        due_date = date.today() + timedelta(days=days)
        
        result = conn.execute(text("""
            INSERT INTO invoices (
                invoice_number, order_id, customer_id, invoice_date, due_date,
                subtotal, tax_amount, total_amount, amount_paid, balance_due,
                status, notes, created_by, created_at, updated_at
            ) VALUES (
                :num, :oid, :cid, :idate, :ddate,
                :sub, :tax, :total, 0, :total,
                'Unpaid', :notes, :uid,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "num": invoice_number,
            "oid": order_id,
            "cid": order['customer_id'],
            "idate": date.today(),
            "ddate": due_date,
            "sub": order['subtotal'],
            "tax": order['tax_amount'],
            "total": order['total_amount'],
            "notes": f"Generated from order {order['order_number']}",
            "uid": st.session_state.get('user_id'),
        })
        
        invoice_id = result.fetchone()[0]
        
        # Copy items
        for _, it in items.iterrows():
            conn.execute(text("""
                INSERT INTO invoice_items (
                    invoice_id, product_id, description,
                    quantity, unit_price, line_total, created_at
                ) VALUES (
                    :iid, :pid, :desc, :qty, :price, :total, CURRENT_TIMESTAMP
                )
            """), {
                "iid": invoice_id,
                "pid": it['product_id'],
                "desc": it['product_name'],
                "qty": it['quantity_ordered'],
                "price": it['unit_price'],
                "total": it['line_total'],
            })
        
        # Update order status
        conn.execute(text("""
            UPDATE sales_orders 
            SET status = 'Invoiced', updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {"id": order_id})
        
        conn.commit()
        
        log_audit("CREATE_INVOICE", "invoices", invoice_id,
                  new_values={"invoice_number": invoice_number, "order_id": order_id,
                              "total": float(order['total_amount'])})
        
        return True, f"✅ Invoice {invoice_number} created", invoice_id
    
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


def get_invoices(search=None, status_filter=None):
    """List invoices"""
    query = """
        SELECT 
            i.id,
            i.invoice_number,
            i.invoice_date,
            i.due_date,
            i.total_amount,
            i.amount_paid,
            i.balance_due,
            i.status,
            c.customer_code,
            c.customer_name,
            so.order_number
        FROM invoices i
        LEFT JOIN customers c ON i.customer_id = c.id
        LEFT JOIN sales_orders so ON i.order_id = so.id
        WHERE 1=1
    """
    params = {}
    
    if status_filter and status_filter != "All":
        query += " AND i.status = :status"
        params["status"] = status_filter
    
    if search:
        query += " AND (LOWER(i.invoice_number) LIKE :s OR LOWER(c.customer_name) LIKE :s)"
        params["s"] = f"%{search.lower()}%"
    
    query += " ORDER BY i.id DESC LIMIT 500"
    
    return read_sql(query, params if params else None)


def get_invoice(invoice_id):
    """Get invoice header"""
    df = read_sql("""
        SELECT i.*, c.customer_code, c.customer_name,
               c.address as customer_address, c.phone as customer_phone,
               c.email as customer_email, c.tax_pin as customer_tax_pin,
               so.order_number
        FROM invoices i
        LEFT JOIN customers c ON i.customer_id = c.id
        LEFT JOIN sales_orders so ON i.order_id = so.id
        WHERE i.id = :id
    """, {"id": invoice_id})
    return None if df.empty else df.iloc[0]


def get_invoice_items(invoice_id):
    """Get invoice line items"""
    return read_sql("""
        SELECT ii.*, p.product_code, p.unit
        FROM invoice_items ii
        LEFT JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = :iid
        ORDER BY ii.id
    """, {"iid": invoice_id})


def generate_invoice_html(invoice_id):
    """Generate printable HTML invoice"""
    inv = get_invoice(invoice_id)
    if inv is None:
        return None
    
    items = get_invoice_items(invoice_id)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <title>Invoice {inv['invoice_number']}</title>
    <style>
        @page {{ size: A4; margin: 15mm; }}
        body {{ font-family: Arial, sans-serif; font-size: 10pt; color: #000; }}
        .header {{ text-align: center; border-bottom: 2px solid #0c4a6e; padding-bottom: 12px; }}
        .header h1 {{ margin: 0; color: #0c4a6e; }}
        .header h2 {{ margin: 4px 0; font-size: 12pt; }}
        .header h3 {{ margin: 4px 0; font-size: 11pt; }}
        .invoice-meta {{ display: flex; justify-content: space-between; margin: 20px 0; }}
        .invoice-meta div {{ line-height: 1.6; }}
        .customer-block {{ background: #f0f9ff; padding: 10px; border-radius: 6px; margin: 15px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #0c4a6e; color: white; padding: 8px; text-align: left; font-size: 9pt; }}
        td {{ padding: 8px; border-bottom: 1px solid #e5e7eb; font-size: 9pt; }}
        .totals {{ width: 300px; margin-left: auto; margin-top: 20px; }}
        .totals td {{ padding: 6px; }}
        .totals .label {{ text-align: right; font-weight: bold; }}
        .totals .grand {{ background: #0c4a6e; color: white; font-weight: bold; font-size: 11pt; }}
        .footer {{ margin-top: 40px; text-align: center; font-size: 9pt; color: #666; border-top: 1px solid #ccc; padding-top: 12px; }}
        .status {{ display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 10pt; font-weight: bold; }}
        .status.unpaid {{ background: #fee2e2; color: #991b1b; }}
        .status.paid {{ background: #d1fae5; color: #065f46; }}
        .status.partial {{ background: #fef3c7; color: #92400e; }}
    </style>
    </head>
    <body>
        <div class="header">
            <h1>AMIGOZ WATER DISTILLING COMPANY</h1>
            <h2>TAX INVOICE</h2>
            <h3>{inv['invoice_number']}</h3>
        </div>
        
        <div class="invoice-meta">
            <div>
                <strong>Invoice Date:</strong> {inv['invoice_date']}<br>
                <strong>Due Date:</strong> {inv['due_date']}<br>
                <strong>Order Ref:</strong> {inv.get('order_number', 'N/A')}<br>
            </div>
            <div style="text-align: right;">
                <strong>Status:</strong> 
                <span class="status {inv['status'].lower()}">{inv['status']}</span>
            </div>
        </div>
        
        <div class="customer-block">
            <strong>BILL TO:</strong><br>
            {inv['customer_name']}<br>
            {inv.get('customer_address') or ''}<br>
            {inv.get('customer_phone') or ''}<br>
            {inv.get('customer_email') or ''}<br>
            {('Tax PIN: ' + inv['customer_tax_pin']) if inv.get('customer_tax_pin') else ''}
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Description</th>
                    <th style="text-align:right;">Qty</th>
                    <th style="text-align:right;">Unit Price</th>
                    <th style="text-align:right;">Line Total</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for idx, it in items.iterrows():
        html += f"""
            <tr>
                <td>{idx + 1}</td>
                <td>{it['description']}</td>
                <td style="text-align:right;">{float(it['quantity']):,.2f} {it.get('unit', '')}</td>
                <td style="text-align:right;">KES {float(it['unit_price']):,.2f}</td>
                <td style="text-align:right;">KES {float(it['line_total']):,.2f}</td>
            </tr>
        """
    
    html += f"""
            </tbody>
        </table>
        
        <table class="totals">
            <tr>
                <td class="label">Subtotal:</td>
                <td style="text-align:right;">KES {float(inv['subtotal']):,.2f}</td>
            </tr>
            <tr>
                <td class="label">VAT:</td>
                <td style="text-align:right;">KES {float(inv['tax_amount']):,.2f}</td>
            </tr>
            <tr class="grand">
                <td class="label">TOTAL:</td>
                <td style="text-align:right;">KES {float(inv['total_amount']):,.2f}</td>
            </tr>
            <tr>
                <td class="label">Amount Paid:</td>
                <td style="text-align:right;">KES {float(inv['amount_paid']):,.2f}</td>
            </tr>
            <tr>
                <td class="label"><strong>Balance Due:</strong></td>
                <td style="text-align:right;"><strong>KES {float(inv['balance_due']):,.2f}</strong></td>
            </tr>
        </table>
        
        <div class="footer">
            <p><strong>Thank you for your business!</strong></p>
            <p>Amigoz Water Distilling Company | P.O. Box 0000 | Kenya</p>
        </div>
    </body>
    </html>
    """
    
    return html
