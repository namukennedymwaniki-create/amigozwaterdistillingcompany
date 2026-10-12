# =========================================================
# services_test_data.py
# Test Data Generator
# =========================================================
# All test records are tagged:
#   - users:        username starts with 'test_'
#   - customers:    customer_code starts with 'TST-'
#   - suppliers:    supplier_code starts with 'TST-'
#   - products:     product_code starts with 'TPRD-'
#   - POs:          po_number starts with 'TPO-'
#   - GRNs:         grn_number starts with 'TGRN-'
#   - SOs:          order_number starts with 'TSO-'
#   - Dispatches:   dispatch_number starts with 'TDSP-'
#   - Deliveries:   delivery_number starts with 'TDLV-'
#   - Issues:       issue_number starts with 'TCIS-'
#   - Returns:      return_number starts with 'TCRT-'
#   - Payments:     payment_number starts with 'TPAY-'
#   - Notes:        '[TEST]' marker in notes field
# =========================================================

import streamlit as st
import random
from datetime import datetime, date, timedelta
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql


# =========================================================
# REFERENCE DATA
# =========================================================
FIRST_NAMES = [
    "Alice", "Brian", "Catherine", "David", "Esther", "Francis", "Grace",
    "Henry", "Irene", "James", "Kevin", "Lucy", "Martin", "Nancy", "Oscar",
    "Peter", "Quincy", "Rachel", "Samuel", "Teresa", "Victor", "Winnie",
]

LAST_NAMES = [
    "Kimani", "Wanjiku", "Otieno", "Mwangi", "Njoroge", "Kariuki", "Odhiambo",
    "Wambui", "Achieng", "Kipchoge", "Mwenda", "Njuguna", "Onyango", "Were",
]

CUSTOMER_NAMES = [
    "Nairobi Retail Hub", "Embu Distributors Ltd", "Mombasa Wholesale Mart",
    "Kisumu Hotel Supplies", "Nakuru Supermarket Chain", "Eldoret Corporate Park",
    "Thika Industrial Canteen", "Machakos County Offices", "Meru Teachers SACCO",
    "Nyeri Coffee Union", "Karibu Resort", "Sunrise Academy", "Hope Clinic",
    "Zion Church Hall", "Riverside Estate Residents Assn", "Kilimani Gym",
]

SUPPLIER_NAMES = [
    "Kenya Bottling Co.", "PolyPlast Industries", "SafeWater Chemicals Ltd",
    "Nairobi Packaging Ltd", "East Africa Labels", "Green Cap Manufacturers",
    "Mount Kenya Logistics", "Safari Transport Ltd", "Prime Equipment Kenya",
    "AquaTest Labs",
]

PRODUCT_TEMPLATES = [
    ("TPRD-500ML", "500ml Bottled Water", "Bottled Water", "500ml", "pcs", 30, 50, 200),
    ("TPRD-1L",    "1 Litre Bottled Water", "Bottled Water", "1L",    "pcs", 50, 80, 150),
    ("TPRD-5L",    "5 Litre Bottled Water", "Bottled Water", "5L",    "pcs", 150, 220, 100),
    ("TPRD-10L",   "10 Litre Bottled Water", "Bottled Water", "10L",  "pcs", 200, 280, 80),
    ("TPRD-20L",   "20 Litre Bottled Water", "Bottled Water", "20L",  "pcs", 300, 400, 60),
    ("TPRD-SACH",  "Sachet Water (Pack)",   "Sachet Water", "500ml", "pack", 100, 150, 300),
    ("TPRD-DISP",  "Water Dispenser (Top)", "Accessories", "Standard", "pcs", 2500, 3200, 15),
]

PRODUCT_TPRD = "TPRD"  # prefix


# =========================================================
# HELPERS
# =========================================================
def _rand_date(days_back=90):
    return date.today() - timedelta(days=random.randint(1, days_back))


def _rand_phone():
    return f"+2547{random.randint(10000000, 99999999)}"


def _rand_email(name):
    safe = name.lower().replace(" ", ".").replace("&", "and")[:20]
    return f"{safe}@example.test"


# =========================================================
# PREVIEW / DRY RUN
# =========================================================
def preview_plan(n_users=5, n_customers=10, n_suppliers=5, n_products=7,
                 n_pos=4, n_grns=4, n_sos=10, n_dispatches=8,
                 n_deliveries=8, n_container_issues=5):
    """Returns a dict summarising what would be created"""
    return {
        "users": n_users,
        "customers": n_customers,
        "suppliers": n_suppliers,
        "products": min(n_products, len(PRODUCT_TEMPLATES)),
        "purchase_orders": n_pos,
        "goods_received_notes": n_grns,
        "sales_orders": n_sos,
        "dispatches": n_dispatches,
        "deliveries": n_deliveries,
        "container_issues": n_container_issues,
        "container_returns": max(1, n_container_issues // 2),
        "payments": n_sos,
    }


# =========================================================
# GENERATE: USERS
# =========================================================
def generate_users(count=5):
    """Create test users. Returns list of created user IDs."""
    from services_users import create_user, get_roles
    
    conn = get_db_connection()
    if not conn:
        return []
    try:
        roles_df = get_roles(active_only=True)
        role_map = {r['name']: r['id'] for _, r in roles_df.iterrows()}
        role_names = [r for r in role_map.keys() if r != "Administrator"]
        
        created = []
        for i in range(count):
            fn = random.choice(FIRST_NAMES)
            ln = random.choice(LAST_NAMES)
            uname = f"test_{fn.lower()}_{i+1}"
            role = random.choice(role_names) if role_names else "Sales Officer"
            
            ok, msg, uid, _ = create_user(
                username=uname,
                email=_rand_email(f"{fn} {ln}"),
                password="TestPass123!",
                first_name=fn,
                last_name=ln,
                phone=_rand_phone(),
                role_id=role_map.get(role),
                is_superuser=False,
                must_change_password=False,
                notes="[TEST] Auto-generated test user",
            )
            if ok and uid:
                created.append(uid)
        return created
    finally:
        conn.close()


# =========================================================
# GENERATE: CUSTOMERS
# =========================================================
def generate_customers(count=10):
    """Create test customers with TST- prefix codes"""
    from services_customers import create_customer
    
    created = []
    for i in range(count):
        name = f"[TEST] {random.choice(CUSTOMER_NAMES)} {i+1}"
        ctype = random.choice(["Retail", "Wholesale", "Distributor",
                                "Government", "Institution"])
        
        # Direct insert (create_customer uses CUST- generator)
        conn = get_db_connection()
        if not conn:
            continue
        try:
            code = f"TST-CUST-{str(i+1).zfill(4)}"
            credit = random.choice([0, 0, 50000, 100000, 250000])
            result = conn.execute(text("""
                INSERT INTO customers (
                    customer_code, customer_name, customer_type,
                    contact_person, phone, email, address, town,
                    credit_limit, payment_terms, is_active, notes,
                    created_at, updated_at
                ) VALUES (
                    :code, :name, :ctype,
                    :contact, :phone, :email, :addr, :town,
                    :credit, :terms, 1, :notes,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                ) RETURNING id
            """), {
                "code": code, "name": name, "ctype": ctype,
                "contact": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
                "phone": _rand_phone(),
                "email": _rand_email(name),
                "addr": f"P.O. Box {random.randint(100, 9999)}",
                "town": random.choice(["Nairobi", "Embu", "Nakuru", "Mombasa",
                                        "Kisumu", "Eldoret", "Thika"]),
                "credit": credit,
                "terms": random.choice(["Cash", "30 days", "60 days"]),
                "notes": "[TEST] Auto-generated test customer",
            })
            cid = result.fetchone()[0]
            conn.commit()
            created.append(cid)
        except Exception as e:
            conn.rollback()
            print(f"Customer {i} error: {e}")
        finally:
            conn.close()
    
    return created


# =========================================================
# GENERATE: SUPPLIERS
# =========================================================
def generate_suppliers(count=5):
    conn = get_db_connection()
    if not conn:
        return []
    created = []
    try:
        for i in range(count):
            name = f"[TEST] {random.choice(SUPPLIER_NAMES)} {i+1}"
            code = f"TST-SUP-{str(i+1).zfill(4)}"
            result = conn.execute(text("""
                INSERT INTO suppliers (
                    supplier_code, supplier_name, contact_person,
                    phone, email, address, town, payment_terms,
                    is_active, notes, created_at, updated_at
                ) VALUES (
                    :code, :name, :contact,
                    :phone, :email, :addr, :town, :terms,
                    1, :notes, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                ) RETURNING id
            """), {
                "code": code, "name": name,
                "contact": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
                "phone": _rand_phone(),
                "email": _rand_email(name),
                "addr": f"P.O. Box {random.randint(100, 9999)}",
                "town": random.choice(["Nairobi", "Thika", "Mombasa"]),
                "terms": random.choice(["30 days", "60 days"]),
                "notes": "[TEST] Auto-generated test supplier",
            })
            sid = result.fetchone()[0]
            created.append(sid)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Supplier gen error: {e}")
    finally:
        conn.close()
    return created


# =========================================================
# GENERATE: PRODUCTS
# =========================================================
def generate_products():
    conn = get_db_connection()
    if not conn:
        return []
    created = []
    try:
        # Fetch categories
        cats = conn.execute(text(
            "SELECT id, name FROM product_categories"
        )).fetchall()
        cat_map = {name: cid for cid, name in cats}
        
        for code, name, cat, size, unit, cost, price, reorder in PRODUCT_TEMPLATES:
            existing = conn.execute(text(
                "SELECT id FROM products WHERE product_code = :c"
            ), {"c": code}).fetchone()
            if existing:
                created.append(existing[0])
                continue
            
            batch_tracked = cat in ("Bottled Water", "Sachet Water")
            
            result = conn.execute(text("""
                INSERT INTO products (
                    product_code, product_name, category_id, size, unit,
                    pack_size, cost_price, selling_price,
                    reorder_level, reorder_quantity,
                    is_batch_tracked, is_active, description,
                    created_at, updated_at
                ) VALUES (
                    :code, :name, :cat, :size, :unit,
                    1, :cost, :price,
                    :reorder, :reorder_qty,
                    :bt, 1, :desc,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                ) RETURNING id
            """), {
                "code": code, "name": f"[TEST] {name}", "cat": cat_map.get(cat),
                "size": size, "unit": unit,
                "cost": cost, "price": price,
                "reorder": reorder, "reorder_qty": reorder * 3,
                "bt": batch_tracked,
                "desc": "[TEST] Auto-generated test product",
            })
            pid = result.fetchone()[0]
            created.append(pid)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Product gen error: {e}")
    finally:
        conn.close()
    return created


# =========================================================
# GENERATE: OPENING STOCK
# =========================================================
def generate_opening_stock():
    """Give each test product 500-2000 units at MAIN warehouse"""
    from services_inventory import post_opening_stock
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        products = conn.execute(text("""
            SELECT id FROM products WHERE product_code LIKE 'TPRD-%'
        """)).fetchall()
        
        count = 0
        for (pid,) in products:
            qty = random.randint(500, 2000)
            # use a TEST prefix (services_inventory generates OPEN- prefix, override by passing reason)
            ok, msg = post_opening_stock(
                product_id=pid,
                quantity=qty,
                unit_cost=0,
                reason="[TEST] Opening stock for test data",
            )
            if ok:
                count += 1
        return count
    finally:
        conn.close()


# =========================================================
# GENERATE: CUSTOMER SALES ORDERS + INVOICES
# =========================================================
def generate_sales_orders(count=10):
    """Create, confirm, dispatch, and invoice test orders"""
    from services_sales import (
        create_sales_order, confirm_order, get_order
    )
    from services_dispatch import create_dispatch, confirm_dispatch
    from services_invoices import create_invoice_from_order
    from services_quality import get_available_stock
    from services_inventory import get_stock_balance
    
    conn = get_db_connection()
    if not conn:
        return {"orders": 0, "dispatched": 0, "invoiced": 0}
    try:
        customers = conn.execute(text("""
            SELECT id FROM customers WHERE customer_code LIKE 'TST-CUST-%'
        """)).fetchall()
        products = conn.execute(text("""
            SELECT id, product_code, selling_price, is_batch_tracked
            FROM products WHERE product_code LIKE 'TPRD-%'
        """)).fetchall()
        warehouses = conn.execute(text(
            "SELECT id, code FROM warehouses WHERE is_active = 1"
        )).fetchall()
        
        if not (customers and products and warehouses):
            return {"orders": 0, "dispatched": 0, "invoiced": 0}
        
        # Prefer MAIN
        main_wh = next((w for w in warehouses if w[1] == 'MAIN'), warehouses[0])
        main_wh_id = main_wh[0]
        
        stats = {"orders": 0, "confirmed": 0, "dispatched": 0, "invoiced": 0}
        
        for i in range(count):
            cust_id = random.choice(customers)[0]
            order_date = _rand_date(60)
            
            # Pick 1-3 products
            n_items = random.randint(1, 3)
            picked = random.sample(products, min(n_items, len(products)))
            
            items = []
            for pid, pcode, price, bt in picked:
                # Ensure stock
                stock = get_stock_balance(pid, main_wh_id)
                if stock < 10:
                    continue
                qty = random.randint(5, min(50, int(stock)))
                items.append({
                    "product_id": pid,
                    "quantity": qty,
                    "unit_price": float(price or 0),
                })
            
            if not items:
                continue
            
            ok, msg, order_id = create_sales_order(
                customer_id=cust_id,
                order_date=order_date,
                delivery_date=order_date + timedelta(days=random.randint(1, 5)),
                vat_enabled=random.choice([True, False]),
                tax_rate=16,
                notes="[TEST] Auto-generated sales order",
                items=items,
            )
            if not ok:
                continue
            stats["orders"] += 1
            
            # Confirm
            ok, msg = confirm_order(order_id)
            if ok:
                stats["confirmed"] += 1
            else:
                continue
            
            # Dispatch (50% of orders)
            if random.random() < 0.5:
                order = get_order(order_id)
                # Create dispatch for the items
                dispatch_items = []
                for it in items:
                    dispatch_items.append({
                        "product_id": it["product_id"],
                        "batch_id": None,
                        "quantity": it["quantity"],
                    })
                ok, msg, disp_id = create_dispatch(
                    order_id=order_id,
                    warehouse_id=main_wh_id,
                    dispatch_date=order_date + timedelta(days=1),
                    notes="[TEST] Auto-generated dispatch",
                    items=dispatch_items,
                )
                if ok:
                    ok2, _ = confirm_dispatch(disp_id)
                    if ok2:
                        stats["dispatched"] += 1
                        
                        # Invoice
                        ok3, _, _ = create_invoice_from_order(order_id)
                        if ok3:
                            stats["invoiced"] += 1
        
        return stats
    except Exception as e:
        print(f"Sales gen error: {e}")
        return {"orders": 0, "dispatched": 0, "invoiced": 0}
    finally:
        conn.close()


# =========================================================
# GENERATE: PURCHASE ORDERS + GRN
# =========================================================
def generate_purchase_orders(count=4):
    """Create POs, approve them, create GRNs, confirm GRNs"""
    from services_procurement import (
        create_purchase_order, approve_purchase_order,
        create_grn, confirm_grn,
    )
    
    conn = get_db_connection()
    if not conn:
        return {"pos": 0, "grns": 0}
    try:
        suppliers = conn.execute(text("""
            SELECT id FROM suppliers WHERE supplier_code LIKE 'TST-SUP-%'
        """)).fetchall()
        products = conn.execute(text("""
            SELECT id, cost_price FROM products WHERE product_code LIKE 'TPRD-%'
        """)).fetchall()
        warehouses = conn.execute(text(
            "SELECT id, code FROM warehouses WHERE is_active = 1"
        )).fetchall()
        
        if not (suppliers and products and warehouses):
            return {"pos": 0, "grns": 0}
        
        main_wh = next((w for w in warehouses if w[1] == 'MAIN'), warehouses[0])
        
        stats = {"pos": 0, "approved": 0, "grns": 0, "grns_confirmed": 0}
        
        for i in range(count):
            sup_id = random.choice(suppliers)[0]
            order_date = _rand_date(45)
            
            n_items = random.randint(1, 3)
            picked = random.sample(products, min(n_items, len(products)))
            
            items = []
            for pid, cost in picked:
                qty = random.randint(100, 500)
                items.append({
                    "product_id": pid,
                    "quantity_ordered": qty,
                    "unit_cost": float(cost or 0),
                })
            
            ok, msg, po_id = create_purchase_order(
                supplier_id=sup_id,
                order_date=order_date,
                expected_date=order_date + timedelta(days=7),
                notes="[TEST] Auto-generated purchase order",
                items=items,
            )
            if not ok:
                continue
            stats["pos"] += 1
            
            # Approve
            ok, msg = approve_purchase_order(po_id)
            if not ok:
                continue
            stats["approved"] += 1
            
            # Create GRN for all items
            grn_items = []
            for pid, cost in picked:
                qty = random.randint(50, 200)
                grn_items.append({
                    "product_id": pid,
                    "quantity_received": qty,
                    "quantity_rejected": 0,
                    "unit_cost": float(cost or 0),
                })
            
            ok, msg, grn_id = create_grn(
                po_id=po_id,
                warehouse_id=main_wh[0],
                received_date=order_date + timedelta(days=random.randint(1, 7)),
                notes="[TEST] Auto-generated GRN",
                items=grn_items,
            )
            if ok:
                stats["grns"] += 1
                ok2, _ = confirm_grn(grn_id)
                if ok2:
                    stats["grns_confirmed"] += 1
        
        return stats
    except Exception as e:
        print(f"PO gen error: {e}")
        return {"pos": 0, "grns": 0}
    finally:
        conn.close()


# =========================================================
# GENERATE: PAYMENTS
# =========================================================
def generate_payments(count=5):
    """Record customer payments against test invoices"""
    from services_payments import record_customer_payment
    
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        # Find unpaid/partial invoices for test customers
        invoices = conn.execute(text("""
            SELECT i.id, i.customer_id, i.balance_due
            FROM invoices i
            JOIN customers c ON i.customer_id = c.id
            WHERE c.customer_code LIKE 'TST-CUST-%'
              AND i.status IN ('Unpaid', 'Partial')
              AND i.balance_due > 0
            ORDER BY i.invoice_date ASC
        """)).fetchall()
        
        created = 0
        for inv_id, cust_id, balance in invoices[:count]:
            balance = float(balance or 0)
            if balance <= 0:
                continue
            # Pay full or partial
            amount = balance if random.random() < 0.6 else round(balance * 0.5, 2)
            ok, msg, _ = record_customer_payment(
                customer_id=cust_id,
                amount=amount,
                payment_date=date.today() - timedelta(days=random.randint(1, 20)),
                payment_method=random.choice(["Cash", "M-Pesa", "Bank Transfer"]),
                reference_number=f"TESTREF{random.randint(1000, 9999)}",
                notes="[TEST] Auto-generated payment",
                auto_allocate=True,
            )
            if ok:
                created += 1
        return created
    finally:
        conn.close()


# =========================================================
# GENERATE: CONTAINER ISSUES + RETURNS
# =========================================================
def generate_containers(count=5):
    """Issue containers to test customers, then return some"""
    from services_containers import (
        issue_containers, return_containers, get_issue_items,
    )
    
    conn = get_db_connection()
    if not conn:
        return {"issues": 0, "returns": 0}
    try:
        customers = conn.execute(text("""
            SELECT id FROM customers WHERE customer_code LIKE 'TST-CUST-%'
        """)).fetchall()
        containers = conn.execute(text(
            "SELECT id, deposit_amount FROM containers WHERE is_active = 1"
        )).fetchall()
        
        if not (customers and containers):
            return {"issues": 0, "returns": 0}
        
        stats = {"issues": 0, "returns": 0}
        
        for i in range(count):
            cust_id = random.choice(customers)[0]
            n_types = random.randint(1, 2)
            picked = random.sample(containers, min(n_types, len(containers)))
            
            items = []
            for cid, _dep in picked:
                items.append({
                    "container_id": cid,
                    "quantity": random.randint(5, 20),
                })
            
            ok, msg, issue_id = issue_containers(
                customer_id=cust_id,
                issue_date=date.today() - timedelta(days=random.randint(5, 30)),
                notes="[TEST] Auto-generated container issue",
                items=items,
            )
            if not ok:
                continue
            stats["issues"] += 1
            
            # Return 60% of issues
            if random.random() < 0.6:
                issue_items = get_issue_items(issue_id)
                if issue_items.empty:
                    continue
                return_lines = []
                for _, it in issue_items.iterrows():
                    outstanding = float(it['outstanding'] or 0)
                    if outstanding <= 0:
                        continue
                    return_qty = int(outstanding * random.choice([0.5, 1.0]))
                    lost_qty = int(outstanding) - return_qty if random.random() < 0.3 else 0
                    if return_qty + lost_qty <= 0:
                        continue
                    return_lines.append({
                        "issue_item_id": it['id'],
                        "container_id": it['container_id'],
                        "quantity_returned": return_qty,
                        "quantity_lost": lost_qty,
                        "loss_reason": "Broken" if lost_qty > 0 else None,
                    })
                if return_lines:
                    ok, _, _ = return_containers(
                        issue_id=issue_id,
                        return_date=date.today() - timedelta(days=random.randint(1, 5)),
                        notes="[TEST] Auto-generated container return",
                        items=return_lines,
                    )
                    if ok:
                        stats["returns"] += 1
        
        return stats
    except Exception as e:
        print(f"Container gen error: {e}")
        return {"issues": 0, "returns": 0}
    finally:
        conn.close()


# =========================================================
# ORCHESTRATOR — FULL TEST DATA RUN
# =========================================================
def generate_all(progress_callback=None, **kwargs):
    """
    Run the full test data generation pipeline.
    Returns a summary dict.
    """
    results = {
        "users": 0,
        "customers": 0,
        "suppliers": 0,
        "products": 0,
        "opening_stock": 0,
        "purchase_orders": {},
        "sales_orders": {},
        "payments": 0,
        "containers": {},
    }
    
    def progress(msg):
        if progress_callback:
            progress_callback(msg)
    
    try:
        progress("👤 Creating test users...")
        results["users"] = len(generate_users(kwargs.get("n_users", 5)))
    except Exception as e:
        print(f"users: {e}")
    
    try:
        progress("👥 Creating test customers...")
        results["customers"] = len(generate_customers(kwargs.get("n_customers", 10)))
    except Exception as e:
        print(f"customers: {e}")
    
    try:
        progress("🏭 Creating test suppliers...")
        results["suppliers"] = len(generate_suppliers(kwargs.get("n_suppliers", 5)))
    except Exception as e:
        print(f"suppliers: {e}")
    
    try:
        progress("📦 Creating test products...")
        results["products"] = len(generate_products())
    except Exception as e:
        print(f"products: {e}")
    
    try:
        progress("📥 Posting opening stock...")
        results["opening_stock"] = generate_opening_stock()
    except Exception as e:
        print(f"opening_stock: {e}")
    
    try:
        progress("🛒 Creating purchase orders and receiving goods...")
        results["purchase_orders"] = generate_purchase_orders(kwargs.get("n_pos", 4))
    except Exception as e:
        print(f"purchase_orders: {e}")
    
    try:
        progress("💰 Creating sales orders, dispatches, invoices...")
        results["sales_orders"] = generate_sales_orders(kwargs.get("n_sos", 10))
    except Exception as e:
        print(f"sales_orders: {e}")
    
    try:
        progress("💳 Recording payments...")
        results["payments"] = generate_payments(kwargs.get("n_sos", 10))
    except Exception as e:
        print(f"payments: {e}")
    
    try:
        progress("🍶 Creating container issues and returns...")
        results["containers"] = generate_containers(kwargs.get("n_container_issues", 5))
    except Exception as e:
        print(f"containers: {e}")
    
    progress("✅ Test data generation complete")
    return results


# =========================================================
# CLEANUP — REMOVE ALL TEST DATA
# =========================================================
def cleanup_test_data():
    """
    Remove all records tagged as [TEST] or with TST-/TPRD-/TEST- prefixes.
    Deletes children first to respect FK constraints.
    Returns dict of deleted counts.
    """
    conn = get_db_connection()
    if not conn:
        return {"error": "No DB connection"}
    deleted = {}
    try:
        # Order matters — children first
        deletes = [
            # Payments
            ("payment_allocations", "payment_id IN (SELECT id FROM payments WHERE payment_number LIKE 'TPAY-%' OR notes LIKE '%[TEST]%')"),
            ("supplier_payment_allocations", "payment_id IN (SELECT id FROM payments WHERE payment_number LIKE 'TPAY-%' OR notes LIKE '%[TEST]%')"),
            ("payments", "payment_number LIKE 'TPAY-%' OR notes LIKE '%[TEST]%'"),
            
            # Containers
            ("container_return_items", "return_id IN (SELECT id FROM container_returns WHERE return_number LIKE 'TCRT-%' OR notes LIKE '%[TEST]%')"),
            ("container_returns", "return_number LIKE 'TCRT-%' OR notes LIKE '%[TEST]%'"),
            ("container_issue_items", "issue_id IN (SELECT id FROM container_issues WHERE issue_number LIKE 'TCIS-%' OR notes LIKE '%[TEST]%')"),
            ("container_issues", "issue_number LIKE 'TCIS-%' OR notes LIKE '%[TEST]%'"),
            
            # Delivery
            ("delivery_items", "delivery_id IN (SELECT id FROM deliveries WHERE delivery_number LIKE 'TDLV-%' OR notes LIKE '%[TEST]%')"),
            ("deliveries", "delivery_number LIKE 'TDLV-%' OR notes LIKE '%[TEST]%'"),
            
            # Dispatch
            ("dispatch_items", "dispatch_id IN (SELECT id FROM dispatches WHERE dispatch_number LIKE 'TDSP-%' OR notes LIKE '%[TEST]%')"),
            ("dispatches", "dispatch_number LIKE 'TDSP-%' OR notes LIKE '%[TEST]%'"),
            
            # Invoice
            ("invoice_items", "invoice_id IN (SELECT id FROM invoices WHERE notes LIKE '%[TEST]%' OR order_id IN (SELECT id FROM sales_orders WHERE order_number LIKE 'TSO-%' OR notes LIKE '%[TEST]%'))"),
            ("invoices", "notes LIKE '%[TEST]%' OR order_id IN (SELECT id FROM sales_orders WHERE order_number LIKE 'TSO-%' OR notes LIKE '%[TEST]%')"),
            
            # Sales orders
            ("sales_order_items", "order_id IN (SELECT id FROM sales_orders WHERE order_number LIKE 'TSO-%' OR notes LIKE '%[TEST]%')"),
            ("stock_reservations", "reference_table = 'sales_orders' AND reference_id IN (SELECT id FROM sales_orders WHERE order_number LIKE 'TSO-%' OR notes LIKE '%[TEST]%')"),
            ("sales_orders", "order_number LIKE 'TSO-%' OR notes LIKE '%[TEST]%'"),
            
            # GRN
            ("goods_received_note_items", "grn_id IN (SELECT id FROM goods_received_notes WHERE grn_number LIKE 'TGRN-%' OR notes LIKE '%[TEST]%')"),
            ("goods_received_notes", "grn_number LIKE 'TGRN-%' OR notes LIKE '%[TEST]%'"),
            
            # PO
            ("purchase_order_items", "po_id IN (SELECT id FROM purchase_orders WHERE po_number LIKE 'TPO-%' OR notes LIKE '%[TEST]%')"),
            ("purchase_orders", "po_number LIKE 'TPO-%' OR notes LIKE '%[TEST]%'"),
            
            # Stock movements and batches for test products
            ("stock_movements", "notes LIKE '%[TEST]%' OR reason LIKE '%[TEST]%' OR reference_number LIKE 'TEST-%' OR product_id IN (SELECT id FROM products WHERE product_code LIKE 'TPRD-%')"),
            ("product_batches", "notes LIKE '%[TEST]%' OR product_id IN (SELECT id FROM products WHERE product_code LIKE 'TPRD-%')"),
            
            # Products
            ("products", "product_code LIKE 'TPRD-%'"),
            
            # Customers / suppliers
            ("customers", "customer_code LIKE 'TST-CUST-%'"),
            ("suppliers", "supplier_code LIKE 'TST-SUP-%'"),
            
            # Users
            ("user_login_history", "user_id IN (SELECT id FROM users WHERE username LIKE 'test_%')"),
            ("users", "username LIKE 'test_%'"),
            
            # Audit logs related to test data
            ("audit_logs", "new_values LIKE '%[TEST]%' OR username LIKE 'test_%'"),
        ]
        
        for table, condition in deletes:
            try:
                result = conn.execute(text(f"DELETE FROM {table} WHERE {condition}"))
                count = result.rowcount
                deleted[table] = count
            except Exception as e:
                deleted[table] = f"error: {e}"
                conn.rollback()
                continue
        
        conn.commit()
        return deleted
    except Exception as e:
        conn.rollback()
        return {"fatal": str(e)}
    finally:
        conn.close()


def count_test_data():
    """Preview what would be deleted"""
    queries = {
        "test users":       "SELECT COUNT(*) FROM users WHERE username LIKE 'test_%'",
        "test customers":   "SELECT COUNT(*) FROM customers WHERE customer_code LIKE 'TST-CUST-%'",
        "test suppliers":   "SELECT COUNT(*) FROM suppliers WHERE supplier_code LIKE 'TST-SUP-%'",
        "test products":    "SELECT COUNT(*) FROM products WHERE product_code LIKE 'TPRD-%'",
        "test sales orders":"SELECT COUNT(*) FROM sales_orders WHERE order_number LIKE 'TSO-%' OR notes LIKE '%[TEST]%'",
        "test POs":         "SELECT COUNT(*) FROM purchase_orders WHERE po_number LIKE 'TPO-%' OR notes LIKE '%[TEST]%'",
        "test GRNs":        "SELECT COUNT(*) FROM goods_received_notes WHERE grn_number LIKE 'TGRN-%' OR notes LIKE '%[TEST]%'",
        "test dispatches":  "SELECT COUNT(*) FROM dispatches WHERE dispatch_number LIKE 'TDSP-%' OR notes LIKE '%[TEST]%'",
        "test deliveries":  "SELECT COUNT(*) FROM deliveries WHERE delivery_number LIKE 'TDLV-%' OR notes LIKE '%[TEST]%'",
        "test invoices":    "SELECT COUNT(*) FROM invoices WHERE notes LIKE '%[TEST]%'",
        "test payments":    "SELECT COUNT(*) FROM payments WHERE payment_number LIKE 'TPAY-%' OR notes LIKE '%[TEST]%'",
        "test container issues": "SELECT COUNT(*) FROM container_issues WHERE issue_number LIKE 'TCIS-%' OR notes LIKE '%[TEST]%'",
        "test container returns":"SELECT COUNT(*) FROM container_returns WHERE return_number LIKE 'TCRT-%' OR notes LIKE '%[TEST]%'",
        "test stock moves": "SELECT COUNT(*) FROM stock_movements WHERE notes LIKE '%[TEST]%' OR reference_number LIKE 'TEST-%'",
    }
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        result = {}
        for label, q in queries.items():
            try:
                result[label] = int(conn.execute(text(q)).scalar() or 0)
            except Exception as e:
                result[label] = f"error: {e}"
        return result
    finally:
        conn.close()
