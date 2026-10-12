# =========================================================
# services_customers.py
# Customer Management Service Layer
# =========================================================

import streamlit as st
from datetime import datetime, date
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql


CUSTOMER_TYPES = ["Retail", "Wholesale", "Distributor", "Government", "Institution", "Other"]


def generate_customer_code():
    """Auto-generate customer code: CUST-{SEQ}"""
    conn = get_db_connection()
    if not conn:
        return "CUST-0001"
    
    try:
        result = conn.execute(text("""
            SELECT customer_code FROM customers
            WHERE customer_code LIKE 'CUST-%'
            ORDER BY id DESC LIMIT 1
        """)).fetchone()
        
        if result and result[0]:
            try:
                num = int(result[0].split("-")[-1])
                return f"CUST-{str(num + 1).zfill(4)}"
            except:
                return "CUST-0001"
        return "CUST-0001"
    except:
        return "CUST-0001"
    finally:
        conn.close()


def create_customer(customer_name, customer_type="Retail", contact_person=None,
                    phone=None, email=None, address=None, town=None,
                    credit_limit=0, payment_terms="30 days", tax_pin=None, notes=None):
    """Create new customer"""
    if not customer_name:
        return False, "Customer name required", None
    
    conn = get_db_connection()
    if not conn:
        return False, "DB connection failed", None
    
    try:
        code = generate_customer_code()
        
        result = conn.execute(text("""
            INSERT INTO customers (
                customer_code, customer_name, customer_type, contact_person,
                phone, email, address, town, credit_limit, payment_terms,
                tax_pin, is_active, notes, created_at, updated_at
            ) VALUES (
                :code, :name, :ctype, :contact,
                :phone, :email, :address, :town, :credit, :terms,
                :pin, 1, :notes, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "code": code,
            "name": customer_name.strip(),
            "ctype": customer_type,
            "contact": contact_person,
            "phone": phone,
            "email": email,
            "address": address,
            "town": town,
            "credit": credit_limit,
            "terms": payment_terms,
            "pin": tax_pin,
            "notes": notes,
        })
        
        customer_id = result.fetchone()[0]
        conn.commit()
        
        log_audit("CREATE_CUSTOMER", "customers", customer_id,
                  new_values={"customer_code": code, "name": customer_name})
        
        return True, f"✅ Customer '{customer_name}' created ({code})", customer_id
    
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


def update_customer(customer_id, **kwargs):
    """Update customer fields"""
    if not kwargs:
        return False, "No changes provided"
    
    conn = get_db_connection()
    if not conn:
        return False, "DB connection failed"
    
    try:
        allowed = ["customer_name", "customer_type", "contact_person", "phone",
                   "email", "address", "town", "credit_limit", "payment_terms",
                   "tax_pin", "is_active", "notes"]
        
        updates = []
        params = {"id": customer_id}
        
        for key, val in kwargs.items():
            if key in allowed:
                updates.append(f"{key} = :{key}")
                params[key] = val
        
        if not updates:
            return False, "No valid fields to update"
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        query = f"UPDATE customers SET {', '.join(updates)} WHERE id = :id"
        
        conn.execute(text(query), params)
        conn.commit()
        
        log_audit("UPDATE_CUSTOMER", "customers", customer_id, new_values=kwargs)
        
        return True, "✅ Customer updated"
    
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}"
    finally:
        conn.close()


def get_customers(search=None, active_only=True, customer_type=None):
    """List customers with filters"""
    query = "SELECT * FROM customers WHERE 1=1"
    params = {}
    
    if active_only:
        query += " AND is_active = 1"
    
    if search:
        query += " AND (LOWER(customer_name) LIKE :search OR LOWER(customer_code) LIKE :search)"
        params["search"] = f"%{search.lower()}%"
    
    if customer_type and customer_type != "All":
        query += " AND customer_type = :ctype"
        params["ctype"] = customer_type
    
    query += " ORDER BY customer_name"
    
    return read_sql(query, params if params else None)


def get_customer(customer_id):
    """Get single customer"""
    df = read_sql("SELECT * FROM customers WHERE id = :id", {"id": customer_id})
    return None if df.empty else df.iloc[0]


def check_credit_available(customer_id, order_amount):
    """
    Check if customer has enough credit for an order.
    Returns (ok, available, message)
    """
    customer = get_customer(customer_id)
    if customer is None:
        return False, 0, "Customer not found"
    
    limit = float(customer.get('credit_limit') or 0)
    
    if limit == 0:
        # No limit set — assume OK
        return True, 0, "No credit limit set"
    
    # Calculate current outstanding (unpaid invoices)
    conn = get_db_connection()
    if not conn:
        return True, 0, "DB error — assuming OK"
    
    try:
        result = conn.execute(text("""
            SELECT COALESCE(SUM(balance_due), 0) 
            FROM invoices
            WHERE customer_id = :cid AND status IN ('Unpaid', 'Partial')
        """), {"cid": customer_id}).scalar()
        
        outstanding = float(result or 0)
        available = limit - outstanding
        conn.close()
        
        if available >= order_amount:
            return True, available, f"✅ Available credit: KES {available:,.2f}"
        else:
            return False, available, (
                f"❌ Credit limit exceeded. "
                f"Limit: KES {limit:,.2f}, "
                f"Outstanding: KES {outstanding:,.2f}, "
                f"New order: KES {order_amount:,.2f}, "
                f"Available: KES {available:,.2f}"
            )
    except Exception as e:
        try:
            conn.close()
        except:
            pass
        return True, 0, f"Credit check error: {e}"
