# =========================================================
# services_test_data.py
# Test Data Generator — Full Coverage
# =========================================================
# Every table gets populated. All booleans use Python True/False.
# All stock changes go through the ledger (post_movement).
# Every record is tagged [TEST] for safe cleanup.
#
# Idempotent:
#   - Customers, suppliers, products, opening stock skip if already exist.
#   - All other generators append safely on re-run.
#   - No duplicate-key crashes.
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
    ("TPRD-500ML", "500ml Bottled Water", "Bottled Water", "500ml", "pcs", 30, 50, 200, True),
    ("TPRD-1L",    "1 Litre Bottled Water", "Bottled Water", "1L",    "pcs", 50, 80, 150, True),
    ("TPRD-5L",    "5 Litre Bottled Water", "Bottled Water", "5L",    "pcs", 150, 220, 100, True),
    ("TPRD-10L",   "10 Litre Bottled Water", "Bottled Water", "10L",  "pcs", 200, 280, 80, True),
    ("TPRD-20L",   "20 Litre Bottled Water", "Bottled Water", "20L",  "pcs", 300, 400, 60, True),
    ("TPRD-SACH",  "Sachet Water (Pack)",   "Sachet Water", "500ml", "pack", 100, 150, 300, True),
    ("TPRD-DISP",  "Water Dispenser (Top)", "Accessories", "Standard", "pcs", 2500, 3200, 15, False),
    ("TPRD-PUMP",  "Manual Water Pump",     "Accessories", "Standard", "pcs", 800, 1200, 10, False),
    ("TPRD-COOL",  "Water Cooler",          "Accessories", "Standard", "pcs", 5000, 7000, 5, False),
]

VEHICLE_TEMPLATES = [
    ("KDA 123X", "3-ton truck", 3000),
    ("KDB 456Y", "5-ton truck", 5000),
    ("KDC 789Z", "1-ton van", 1000),
    ("KDD 012W", "Pickup", 800),
]

DAMAGE_REASONS = [
    "Broken during handling",
    "Damaged in transit",
    "Expired stock",
    "Manufacturing defect",
    "Customer return damaged",
]

ADJUSTMENT_REASONS = [
    "Physical count variance",
    "Record correction",
    "Inventory audit adjustment",
    "System reconciliation",
]


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


def _ok(result):
    """Extract success bool from (ok, msg) or (ok, msg, id) tuples."""
    if isinstance(result, tuple):
        return bool(result[0])
    return bool(result)


# =========================================================
# PREVIEW / DRY RUN
# =========================================================
def preview_plan(n_users=5, n_customers=10, n_suppliers=5, n_products=9,
                 n_pos=6, n_grns=6, n_sos=15, n_dispatches=12,
                 n_deliveries=10, n_container_issues=8, n_payments=10,
                 n_adjustments=4, n_damages=4):
    return {
        "users": n_users,
        "customers": n_customers,
        "suppliers": n_suppliers,
        "products": min(n_products, len(PRODUCT_TEMPLATES)),
        "vehicles": len(VEHICLE_TEMPLATES),
        "drivers": 3,
        "purchase_orders": n_pos,
        "goods_received_notes": n_grns,
        "sales_orders": n_sos,
        "dispatches": n_dispatches,
        "deliveries": n_deliveries,
        "container_issues": n_container_issues,
        "container_returns": max(2, n_container_issues // 2),
        "customer_payments": n_payments,
        "supplier_payments": 3,
        "stock_adjustments": n_adjustments,
        "damage_records": n_damages,
    }


# =========================================================
# GENERATE: USERS
# =========================================================
def generate_users(count=5):
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

            # Skip if user exists
            existing = conn.execute(text(
                "SELECT id FROM users WHERE LOWER(username) = LOWER(:u)"
            ), {"u": uname}).fetchone()
            if existing:
                created.append(existing[0])
                continue

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
# GENERATE: VEHICLES + DRIVERS
# =========================================================
def generate_vehicles_and_drivers():
    from services_vehicles import create_vehicle, create_driver

    created_vehicles = []
    created_drivers = []

    conn = get_db_connection()
    if not conn:
        return {"vehicles": [], "drivers": []}

    try:
        # Vehicles
        for plate, desc, cap in VEHICLE_TEMPLATES:
            existing = conn.execute(text(
                "SELECT id FROM vehicles WHERE LOWER(plate_number) = LOWER(:p)"
            ), {"p": plate}).fetchone()
            if existing:
                created_vehicles.append(existing[0])
                continue
            ok, msg, vid = create_vehicle(plate, desc, cap,
                                           notes="[TEST] Auto-generated vehicle")
            if ok and vid:
                created_vehicles.append(vid)

        # Drivers
        for i in range(3):
            fn = random.choice(FIRST_NAMES)
            ln = random.choice(LAST_NAMES)
            name = f"{fn} {ln}"
            # No unique constraint on driver names, but skip if exists
            existing = conn.execute(text(
                "SELECT id FROM drivers WHERE name = :n AND notes LIKE '%[TEST]%'"
            ), {"n": name}).fetchone()
            if existing:
                created_drivers.append(existing[0])
                continue

            ok, msg, did = create_driver(
                name=name,
                phone=_rand_phone(),
                license_number=f"DL{random.randint(100000, 999999)}",
                notes="[TEST] Auto-generated driver",
            )
            if ok and did:
                created_drivers.append(did)
    finally:
        conn.close()

    return {"vehicles": created_vehicles, "drivers": created_drivers}


# =========================================================
# GENERATE: CUSTOMERS (idempotent)
# =========================================================
def generate_customers(count=10):
    created = []
    for i in range(count):
        name = f"[TEST] {random.choice(CUSTOMER_NAMES)} {i+1}"
        ctype = random.choice(["Retail", "Wholesale", "Distributor",
                                "Government", "Institution"])
        conn = get_db_connection()
        if not conn:
            continue
        try:
            code = f"TST-CUST-{str(i+1).zfill(4)}"

            # Skip if already exists
            existing = conn.execute(text(
                "SELECT id FROM customers WHERE customer_code = :c"
            ), {"c": code}).fetchone()
            if existing:
                created.append(existing[0])
                continue

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
                    :credit, :terms, :active, :notes,
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
                "active": True,
                "notes": "[TEST] Auto-generated test customer",
            })
            cid = result.fetchone()[0]
            conn.commit()
            created.append(cid)
        except Exception as e:
            conn.rollback()
            raise Exception(f"Customer {i} insert failed: {type(e).__name__}: {e}")
        finally:
            conn.close()
    return created


# =========================================================
# GENERATE: SUPPLIERS (idempotent)
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

            # Skip if already exists
            existing = conn.execute(text(
                "SELECT id FROM suppliers WHERE supplier_code = :c"
            ), {"c": code}).fetchone()
            if existing:
                created.append(existing[0])
                continue

            result = conn.execute(text("""
                INSERT INTO suppliers (
                    supplier_code, supplier_name, contact_person,
                    phone, email, address, town, payment_terms,
                    is_active, notes, created_at, updated_at
                ) VALUES (
                    :code, :name, :contact,
                    :phone, :email, :addr, :town, :terms,
                    :active, :notes, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                ) RETURNING id
            """), {
                "code": code, "name": name,
                "contact": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
                "phone": _rand_phone(),
                "email": _rand_email(name),
                "addr": f"P.O. Box {random.randint(100, 9999)}",
                "town": random.choice(["Nairobi", "Thika", "Mombasa"]),
                "terms": random.choice(["30 days", "60 days"]),
                "active": True,
                "notes": "[TEST] Auto-generated test supplier",
            })
            sid = result.fetchone()[0]
            created.append(sid)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise Exception(f"Supplier insert failed: {type(e).__name__}: {e}")
    finally:
        conn.close()
    return created


# =========================================================
# GENERATE: PRODUCTS (idempotent)
# =========================================================
def generate_products():
    conn = get_db_connection()
    if not conn:
        return []
    created = []
    try:
        cats = conn.execute(text(
            "SELECT id, name FROM product_categories"
        )).fetchall()
        cat_map = {name: cid for cid, name in cats}

        for code, name, cat, size, unit, cost, price, reorder, batch_tracked in PRODUCT_TEMPLATES:
            existing = conn.execute(text(
                "SELECT id FROM products WHERE product_code = :c"
            ), {"c": code}).fetchone()
            if existing:
                created.append(existing[0])
                continue

            result = conn.execute(text("""
                INSERT INTO products (
                    product_code, product_name, category_id, size, unit,
                    pack_size, cost_price, selling_price,
                    reorder_level, reorder_quantity,
                    is_batch_tracked, is_active, description,
                    created_at, updated_at
                ) VALUES (
                    :code, :name, :cat, :size, :unit,
                    :pack, :cost, :price,
                    :reorder, :reorder_qty,
                    :bt, :active, :desc,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                ) RETURNING id
            """), {
                "code": code, "name": f"[TEST] {name}", "cat": cat_map.get(cat),
                "size": size, "unit": unit,
                "pack": 1, "cost": cost, "price": price,
                "reorder": reorder, "reorder_qty": reorder * 3,
                "bt": bool(batch_tracked),
                "active": True,
                "desc": "[TEST] Auto-generated test product",
            })
            pid = result.fetchone()[0]
            created.append(pid)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise Exception(f"Product insert failed: {type(e).__name__}: {e}")
    finally:
        conn.close()
    return created


# =========================================================
# GENERATE: OPENING STOCK (idempotent, batches Released)
# =========================================================
def generate_opening_stock():
    from services_inventory import post_opening_stock
    from services_quality import generate_batch_number

    conn = get_db_connection()
    if not conn:
        return 0
    try:
        products = conn.execute(text("""
            SELECT id, product_code, is_batch_tracked
            FROM products WHERE product_code LIKE 'TPRD-%'
        """)).fetchall()

        count = 0
        for pid, pcode, is_batch in products:
            # Skip if opening stock already posted for this product
            already = conn.execute(text("""
                SELECT 1 FROM stock_movements
                WHERE product_id = :pid
                  AND movement_type = 'OPENING'
                  AND reason LIKE '%[TEST]%'
                LIMIT 1
            """), {"pid": int(pid)}).fetchone()
            if already:
                count += 1
                continue

            qty = random.randint(500, 2000)
            batch_number = None
            if is_batch:
                batch_number = generate_batch_number(pcode)

            # post_opening_stock returns (ok, msg, movement_id)
            # Force batch status = Released so sellable stock is available
            result = post_opening_stock(
                product_id=int(pid),
                quantity=qty,
                unit_cost=0,
                batch_number=batch_number,
                production_date=date.today() - timedelta(days=random.randint(1, 30)),
                expiry_date=date.today() + timedelta(days=random.randint(180, 730)),
                reason="[TEST] Opening stock for test data",
                batch_status="Released",
            )
            if _ok(result):
                count += 1

        # Force any lingering Quarantined [TEST] batches to Released
        conn.execute(text("""
            UPDATE product_batches
            SET quality_status = 'Released'
            WHERE notes LIKE '%[TEST]%'
              AND quality_status = 'Quarantined'
        """))
        conn.commit()

        return count
    finally:
        conn.close()


# =========================================================
# GENERATE: STOCK ADJUSTMENTS
# =========================================================
def generate_adjustments(count=4):
    from services_inventory import post_adjustment, get_stock_balance

    conn = get_db_connection()
    if not conn:
        return 0
    try:
        products = conn.execute(text("""
            SELECT id FROM products WHERE product_code LIKE 'TPRD-%'
        """)).fetchall()
        warehouses = conn.execute(text(
            "SELECT id FROM warehouses WHERE is_active = TRUE"
        )).fetchall()
        if not (products and warehouses):
            return 0

        created = 0
        for _ in range(count):
            pid = random.choice(products)[0]
            wid = random.choice(warehouses)[0]
            current = get_stock_balance(pid, wid)
            if current <= 0:
                continue
            variance = random.choice([-1, 1]) * int(current * random.uniform(0.05, 0.15))
            new_qty = max(0, current + variance)

            result = post_adjustment(
                product_id=int(pid),
                warehouse_id=int(wid),
                new_quantity=new_qty,
                reason=f"[TEST] {random.choice(ADJUSTMENT_REASONS)}",
            )
            if _ok(result):
                created += 1
        return created
    finally:
        conn.close()


# =========================================================
# GENERATE: DAMAGE RECORDS
# =========================================================
def generate_damage_records(count=4):
    from services_inventory import post_damaged_goods, get_stock_balance

    conn = get_db_connection()
    if not conn:
        return 0
    try:
        products = conn.execute(text("""
            SELECT id FROM products WHERE product_code LIKE 'TPRD-%'
        """)).fetchall()
        warehouses = conn.execute(text(
            "SELECT id FROM warehouses WHERE is_active = TRUE"
        )).fetchall()
        if not (products and warehouses):
            return 0

        created = 0
        for i in range(count):
            pid = random.choice(products)[0]
            wid = random.choice(warehouses)[0]
            stock = get_stock_balance(pid, wid)
            if stock < 10:
                continue
            qty = random.randint(1, min(20, int(stock * 0.05)))

            result = post_damaged_goods(
                product_id=int(pid),
                warehouse_id=int(wid),
                quantity=qty,
                reason=f"[TEST] {random.choice(DAMAGE_REASONS)}",
                reference_number=f"TEST-DMG-{date.today().strftime('%Y%m%d')}-{i+1}",
            )
            if _ok(result):
                created += 1
        return created
    finally:
        conn.close()


# =========================================================
# GENERATE: PURCHASE ORDERS + GRN
# =========================================================
def generate_purchase_orders(count=6):
    from services_procurement import (
        create_purchase_order, approve_purchase_order,
        create_grn, confirm_grn,
    )

    conn = get_db_connection()
    if not conn:
        return {"pos": 0, "grns": 0, "grns_confirmed": 0}
    try:
        suppliers = conn.execute(text("""
            SELECT id FROM suppliers WHERE supplier_code LIKE 'TST-SUP-%'
        """)).fetchall()
        products = conn.execute(text("""
            SELECT id, cost_price FROM products WHERE product_code LIKE 'TPRD-%'
        """)).fetchall()
        warehouses = conn.execute(text(
            "SELECT id, code FROM warehouses WHERE is_active = TRUE"
        )).fetchall()

        if not (suppliers and products and warehouses):
            return {"pos": 0, "grns": 0, "grns_confirmed": 0}

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
                    "product_id": int(pid),
                    "quantity_ordered": qty,
                    "unit_cost": float(cost or 0),
                })

            ok, msg, po_id = create_purchase_order(
                supplier_id=int(sup_id),
                order_date=order_date,
                expected_date=order_date + timedelta(days=7),
                notes="[TEST] Auto-generated purchase order",
                items=items,
            )
            if not ok:
                continue
            stats["pos"] += 1

            if not _ok(approve_purchase_order(po_id)):
                continue
            stats["approved"] += 1

            # 80% of POs get a GRN
            if random.random() < 0.8:
                grn_items = []
                for pid, cost in picked:
                    qty = random.randint(50, 200)
                    grn_items.append({
                        "product_id": int(pid),
                        "quantity_received": qty,
                        "quantity_rejected": random.choice([0, 0, 0, 5]),
                        "unit_cost": float(cost or 0),
                    })

                ok, msg, grn_id = create_grn(
                    po_id=int(po_id),
                    warehouse_id=int(main_wh[0]),
                    received_date=order_date + timedelta(days=random.randint(1, 7)),
                    notes="[TEST] Auto-generated GRN",
                    items=grn_items,
                )
                if ok:
                    stats["grns"] += 1
                    if _ok(confirm_grn(grn_id)):
                        stats["grns_confirmed"] += 1

        return stats
    except Exception as e:
        print(f"PO gen error: {e}")
        import traceback
        traceback.print_exc()
        return {"pos": 0, "grns": 0, "grns_confirmed": 0}
    finally:
        conn.close()


# =========================================================
# GENERATE: SALES ORDERS + DISPATCH + DELIVERY + INVOICE
# =========================================================
def generate_sales_orders(count=15):
    from services_sales import create_sales_order, confirm_order
    from services_dispatch import create_dispatch, confirm_dispatch
    from services_delivery import (
        create_delivery_from_dispatch, confirm_delivery,
        update_delivery_item, get_delivery_items,
    )
    from services_invoices import create_invoice_from_order
    from services_inventory import get_stock_balance

    conn = get_db_connection()
    if not conn:
        return {"orders": 0, "dispatched": 0, "delivered": 0, "invoiced": 0}
    try:
        customers = conn.execute(text("""
            SELECT id FROM customers WHERE customer_code LIKE 'TST-CUST-%'
        """)).fetchall()
        products = conn.execute(text("""
            SELECT id, product_code, selling_price, is_batch_tracked
            FROM products WHERE product_code LIKE 'TPRD-%'
        """)).fetchall()
        warehouses = conn.execute(text(
            "SELECT id, code FROM warehouses WHERE is_active = TRUE"
        )).fetchall()
        vehicles = conn.execute(text(
            "SELECT id FROM vehicles WHERE plate_number LIKE 'KD%'"
        )).fetchall()
        drivers = conn.execute(text("SELECT id FROM drivers")).fetchall()

        if not (customers and products and warehouses):
            return {"orders": 0, "dispatched": 0, "delivered": 0, "invoiced": 0}

        main_wh = next((w for w in warehouses if w[1] == 'MAIN'), warehouses[0])
        main_wh_id = main_wh[0]

        stats = {"orders": 0, "confirmed": 0, "dispatched": 0,
                 "delivered": 0, "partial": 0, "invoiced": 0}

        for i in range(count):
            cust_id = random.choice(customers)[0]
            order_date = _rand_date(60)
            n_items = random.randint(1, 3)
            picked = random.sample(products, min(n_items, len(products)))

            items = []
            for pid, pcode, price, bt in picked:
                stock = get_stock_balance(pid, main_wh_id)
                if stock < 20:
                    continue
                qty = random.randint(5, min(50, int(stock / 2)))
                items.append({
                    "product_id": int(pid),
                    "quantity": qty,
                    "unit_price": float(price or 0),
                })

            if not items:
                continue

            ok, msg, order_id = create_sales_order(
                customer_id=int(cust_id),
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

            if not _ok(confirm_order(order_id)):
                continue
            stats["confirmed"] += 1

            if random.random() > 0.7:
                continue

            dispatch_items = [{
                "product_id": int(it["product_id"]),
                "batch_id": None,
                "quantity": it["quantity"],
            } for it in items]

            vehicle_id = random.choice(vehicles)[0] if vehicles else None
            driver_name = None
            if drivers:
                driver_name = f"Driver {random.choice(drivers)[0]}"

            ok, msg, disp_id = create_dispatch(
                order_id=int(order_id),
                warehouse_id=int(main_wh_id),
                dispatch_date=order_date + timedelta(days=1),
                vehicle_id=int(vehicle_id) if vehicle_id else None,
                driver_name=driver_name,
                notes="[TEST] Auto-generated dispatch",
                items=dispatch_items,
            )
            if not ok:
                continue
            if not _ok(confirm_dispatch(disp_id)):
                continue
            stats["dispatched"] += 1

            # 80% of dispatches get delivery
            if random.random() > 0.8:
                inv_res = create_invoice_from_order(order_id)
                if _ok(inv_res):
                    stats["invoiced"] += 1
                continue

            ok, msg, dlv_id = create_delivery_from_dispatch(
                dispatch_id=int(disp_id),
                delivery_date=order_date + timedelta(days=2),
            )
            if not ok:
                continue

            # 30% partial deliveries
            is_partial = random.random() < 0.3
            if is_partial:
                d_items = get_delivery_items(dlv_id)
                if not d_items.empty:
                    it = d_items.iloc[0]
                    qd = float(it['quantity_dispatched'] or 0)
                    shortfall = int(qd * random.uniform(0.1, 0.4))
                    qrec = max(0, int(qd) - shortfall)
                    update_delivery_item(
                        int(it['id']),
                        quantity_received=qrec,
                        quantity_rejected=shortfall,
                        rejection_reason=random.choice(["Damaged", "Short delivery", "Refused"]),
                    )

            ok, msg = confirm_delivery(
                delivery_id=int(dlv_id),
                received_by_name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
                received_by_phone=_rand_phone(),
                signature_ref=f"TESTREF-{random.randint(1000, 9999)}",
                delivery_notes="[TEST] Auto-generated delivery confirmation",
            )
            if ok:
                stats["delivered"] += 1
                if is_partial:
                    stats["partial"] += 1

                inv_res = create_invoice_from_order(order_id)
                if _ok(inv_res):
                    stats["invoiced"] += 1

        return stats
    except Exception as e:
        print(f"Sales gen error: {e}")
        import traceback
        traceback.print_exc()
        return {"orders": 0, "dispatched": 0, "delivered": 0, "invoiced": 0}
    finally:
        conn.close()


# =========================================================
# GENERATE: CUSTOMER PAYMENTS
# =========================================================
def generate_customer_payments(count=10):
    from services_payments import record_customer_payment

    conn = get_db_connection()
    if not conn:
        return 0
    try:
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
            amount = balance if random.random() < 0.5 else round(balance * random.uniform(0.3, 0.7), 2)
            ok, msg, _ = record_customer_payment(
                customer_id=int(cust_id),
                amount=amount,
                payment_date=date.today() - timedelta(days=random.randint(1, 20)),
                payment_method=random.choice(["Cash", "M-Pesa", "Bank Transfer", "Cheque"]),
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
# GENERATE: SUPPLIER PAYMENTS
# =========================================================
def generate_supplier_payments(count=3):
    from services_payments import record_supplier_payment

    conn = get_db_connection()
    if not conn:
        return 0
    try:
        pos = conn.execute(text("""
            SELECT po.id, po.supplier_id, po.total_amount
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            WHERE s.supplier_code LIKE 'TST-SUP-%'
              AND po.status IN ('Fully Received', 'Partially Received')
            ORDER BY po.order_date ASC
        """)).fetchall()

        created = 0
        for po_id, sup_id, total in pos[:count]:
            total = float(total or 0)
            if total <= 0:
                continue
            amount = total if random.random() < 0.7 else round(total * 0.5, 2)
            ok, msg, _ = record_supplier_payment(
                supplier_id=int(sup_id),
                amount=amount,
                payment_date=date.today() - timedelta(days=random.randint(1, 15)),
                payment_method=random.choice(["Bank Transfer", "Cheque", "M-Pesa"]),
                reference_number=f"TESTPO{random.randint(1000, 9999)}",
                notes="[TEST] Auto-generated supplier payment",
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
def generate_containers(count=8):
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
            "SELECT id, deposit_amount FROM containers WHERE is_active = TRUE"
        )).fetchall()

        if not (customers and containers):
            return {"issues": 0, "returns": 0}

        stats = {"issues": 0, "returns": 0}

        for i in range(count):
            cust_id = random.choice(customers)[0]
            n_types = random.randint(1, 3)
            picked = random.sample(containers, min(n_types, len(containers)))

            items = [{
                "container_id": int(cid),
                "quantity": random.randint(5, 25),
            } for cid, _dep in picked]

            ok, msg, issue_id = issue_containers(
                customer_id=int(cust_id),
                issue_date=date.today() - timedelta(days=random.randint(5, 30)),
                notes="[TEST] Auto-generated container issue",
                items=items,
            )
            if not ok:
                continue
            stats["issues"] += 1

            if random.random() > 0.7:
                continue

            issue_items = get_issue_items(issue_id)
            if issue_items.empty:
                continue

            return_lines = []
            for _, it in issue_items.iterrows():
                outstanding = float(it['outstanding'] or 0)
                if outstanding <= 0:
                    continue
                frac = random.choice([0.5, 0.7, 1.0])
                return_qty = int(outstanding * frac)
                lost_qty = int(outstanding) - return_qty if random.random() < 0.3 else 0
                if return_qty + lost_qty <= 0:
                    continue
                return_lines.append({
                    "issue_item_id": int(it['id']),
                    "container_id": int(it['container_id']),
                    "quantity_returned": return_qty,
                    "quantity_lost": lost_qty,
                    "loss_reason": "Broken" if lost_qty > 0 else None,
                })
            if return_lines:
                ok, _, _ = return_containers(
                    issue_id=int(issue_id),
                    return_date=date.today() - timedelta(days=random.randint(1, 5)),
                    notes="[TEST] Auto-generated container return",
                    items=return_lines,
                )
                if ok:
                    stats["returns"] += 1

        return stats
    except Exception as e:
        print(f"Container gen error: {e}")
        import traceback
        traceback.print_exc()
        return {"issues": 0, "returns": 0}
    finally:
        conn.close()


# =========================================================
# ORCHESTRATOR
# =========================================================
def generate_all(progress_callback=None, **kwargs):
    import traceback

    results = {
        "users": 0, "customers": 0, "suppliers": 0, "products": 0,
        "vehicles": 0, "drivers": 0,
        "opening_stock": 0, "adjustments": 0, "damages": 0,
        "purchase_orders": {}, "sales_orders": {},
        "customer_payments": 0, "supplier_payments": 0,
        "containers": {},
        "errors": [],
    }

    def progress(msg):
        if progress_callback:
            progress_callback(msg)

    def step(name, fn, *args, **kw):
        try:
            progress(f"▶ {name}...")
            out = fn(*args, **kw)
            progress(f"✅ {name} done")
            return out
        except Exception as e:
            results["errors"].append(f"{name}: {type(e).__name__}: {e}")
            results["errors"].append(traceback.format_exc())
            progress(f"❌ {name} FAILED")
            return None

    # Reference data check
    try:
        wh_count = len(read_sql("SELECT id FROM warehouses WHERE is_active = TRUE"))
        cat_count = len(read_sql("SELECT id FROM product_categories WHERE is_active = TRUE"))
        cont_count = len(read_sql("SELECT id FROM containers WHERE is_active = TRUE"))
        role_count = len(read_sql("SELECT id FROM roles WHERE is_active = TRUE"))
        progress(f"📋 Ref: {wh_count} warehouses, {cat_count} cats, {cont_count} containers, {role_count} roles")
        if wh_count == 0:
            results["errors"].append("⚠️ No warehouses")
    except Exception as e:
        results["errors"].append(f"Ref check failed: {e}")

    # Users
    users = step("Create users", generate_users, kwargs.get("n_users", 5))
    results["users"] = len(users) if users else 0

    # Vehicles + drivers
    vd = step("Vehicles + drivers", generate_vehicles_and_drivers) or {}
    results["vehicles"] = len(vd.get("vehicles", []))
    results["drivers"] = len(vd.get("drivers", []))

    # Customers
    customers = step("Create customers", generate_customers, kwargs.get("n_customers", 10))
    results["customers"] = len(customers) if customers else 0

    # Suppliers
    suppliers = step("Create suppliers", generate_suppliers, kwargs.get("n_suppliers", 5))
    results["suppliers"] = len(suppliers) if suppliers else 0

    # Products
    products = step("Create products", generate_products)
    results["products"] = len(products) if products else 0

    # Opening stock
    if products:
        results["opening_stock"] = step("Opening stock", generate_opening_stock) or 0

    # Adjustments
    if products:
        results["adjustments"] = step("Stock adjustments",
                                       generate_adjustments,
                                       kwargs.get("n_adjustments", 4)) or 0

    # Damages
    if products:
        results["damages"] = step("Damage records",
                                   generate_damage_records,
                                   kwargs.get("n_damages", 4)) or 0

    # POs + GRN
    if suppliers and products:
        results["purchase_orders"] = step("Purchase orders + GRN",
                                          generate_purchase_orders,
                                          kwargs.get("n_pos", 6)) or {}

    # Sales cycle
    if customers and products:
        results["sales_orders"] = step("Sales + dispatch + delivery + invoice",
                                       generate_sales_orders,
                                       kwargs.get("n_sos", 15)) or {}

    # Customer payments
    results["customer_payments"] = step("Customer payments",
                                        generate_customer_payments,
                                        kwargs.get("n_payments", 10)) or 0

    # Supplier payments
    results["supplier_payments"] = step("Supplier payments",
                                        generate_supplier_payments,
                                        3) or 0

    # Containers
    if customers:
        results["containers"] = step("Containers", generate_containers,
                                     kwargs.get("n_container_issues", 8)) or {}

    progress("✅ Test data generation complete")
    return results


# =========================================================
# CLEANUP
# =========================================================
def cleanup_test_data():
    conn = get_db_connection()
    if not conn:
        return {"error": "No DB connection"}
    deleted = {}
    try:
        deletes = [
            ("payment_allocations",
             "payment_id IN (SELECT id FROM payments WHERE payment_number LIKE 'TPAY-%' OR notes LIKE '%[TEST]%')"),
            ("supplier_payment_allocations",
             "payment_id IN (SELECT id FROM payments WHERE payment_number LIKE 'TPAY-%' OR notes LIKE '%[TEST]%')"),
            ("payments",
             "payment_number LIKE 'TPAY-%' OR notes LIKE '%[TEST]%'"),

            ("container_return_items",
             "return_id IN (SELECT id FROM container_returns WHERE return_number LIKE 'TCRT-%' OR notes LIKE '%[TEST]%')"),
            ("container_returns",
             "return_number LIKE 'TCRT-%' OR notes LIKE '%[TEST]%'"),
            ("container_issue_items",
             "issue_id IN (SELECT id FROM container_issues WHERE issue_number LIKE 'TCIS-%' OR notes LIKE '%[TEST]%')"),
            ("container_issues",
             "issue_number LIKE 'TCIS-%' OR notes LIKE '%[TEST]%'"),

            ("delivery_items",
             "delivery_id IN (SELECT id FROM deliveries WHERE delivery_number LIKE 'TDLV-%' OR notes LIKE '%[TEST]%')"),
            ("deliveries",
             "delivery_number LIKE 'TDLV-%' OR notes LIKE '%[TEST]%'"),

            ("dispatch_items",
             "dispatch_id IN (SELECT id FROM dispatches WHERE dispatch_number LIKE 'TDSP-%' OR notes LIKE '%[TEST]%')"),
            ("dispatches",
             "dispatch_number LIKE 'TDSP-%' OR notes LIKE '%[TEST]%'"),

            ("invoice_items",
             "invoice_id IN (SELECT id FROM invoices WHERE notes LIKE '%[TEST]%' OR order_id IN (SELECT id FROM sales_orders WHERE order_number LIKE 'TSO-%' OR notes LIKE '%[TEST]%'))"),
            ("invoices",
             "notes LIKE '%[TEST]%' OR order_id IN (SELECT id FROM sales_orders WHERE order_number LIKE 'TSO-%' OR notes LIKE '%[TEST]%')"),

            ("sales_order_items",
             "order_id IN (SELECT id FROM sales_orders WHERE order_number LIKE 'TSO-%' OR notes LIKE '%[TEST]%')"),
            ("stock_reservations",
             "reference_table = 'sales_orders' AND reference_id IN (SELECT id FROM sales_orders WHERE order_number LIKE 'TSO-%' OR notes LIKE '%[TEST]%')"),
            ("sales_orders",
             "order_number LIKE 'TSO-%' OR notes LIKE '%[TEST]%'"),

            ("goods_received_note_items",
             "grn_id IN (SELECT id FROM goods_received_notes WHERE grn_number LIKE 'TGRN-%' OR notes LIKE '%[TEST]%')"),
            ("goods_received_notes",
             "grn_number LIKE 'TGRN-%' OR notes LIKE '%[TEST]%'"),

            ("purchase_order_items",
             "po_id IN (SELECT id FROM purchase_orders WHERE po_number LIKE 'TPO-%' OR notes LIKE '%[TEST]%')"),
            ("purchase_orders",
             "po_number LIKE 'TPO-%' OR notes LIKE '%[TEST]%'"),

            # stock_movements uses `reason` not `notes`
            ("stock_movements",
             "reason LIKE '%[TEST]%' OR reference_number LIKE 'TEST-%' OR product_id IN (SELECT id FROM products WHERE product_code LIKE 'TPRD-%')"),

            ("product_batches",
             "notes LIKE '%[TEST]%' OR product_id IN (SELECT id FROM products WHERE product_code LIKE 'TPRD-%')"),

            ("products", "product_code LIKE 'TPRD-%'"),
            ("customers", "customer_code LIKE 'TST-CUST-%'"),
            ("suppliers", "supplier_code LIKE 'TST-SUP-%'"),

            ("user_login_history",
             "user_id IN (SELECT id FROM users WHERE username LIKE 'test_%')"),
            ("users", "username LIKE 'test_%'"),

            ("vehicles", "notes LIKE '%[TEST]%'"),
            ("drivers", "notes LIKE '%[TEST]%'"),

            # audit_logs.new_values is JSONB — cast to text
            ("audit_logs",
             "new_values::text LIKE '%[TEST]%' "
             "OR old_values::text LIKE '%[TEST]%' "
             "OR username LIKE 'test_%'"),
        ]

        for table, condition in deletes:
            try:
                result = conn.execute(text(f"DELETE FROM {table} WHERE {condition}"))
                deleted[table] = int(result.rowcount or 0)
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
    queries = {
        "test users":       "SELECT COUNT(*) FROM users WHERE username LIKE 'test_%'",
        "test customers":   "SELECT COUNT(*) FROM customers WHERE customer_code LIKE 'TST-CUST-%'",
        "test suppliers":   "SELECT COUNT(*) FROM suppliers WHERE supplier_code LIKE 'TST-SUP-%'",
        "test products":    "SELECT COUNT(*) FROM products WHERE product_code LIKE 'TPRD-%'",
        "test POs":         "SELECT COUNT(*) FROM purchase_orders WHERE po_number LIKE 'TPO-%' OR notes LIKE '%[TEST]%'",
        "test GRNs":        "SELECT COUNT(*) FROM goods_received_notes WHERE grn_number LIKE 'TGRN-%' OR notes LIKE '%[TEST]%'",
        "test sales orders":"SELECT COUNT(*) FROM sales_orders WHERE order_number LIKE 'TSO-%' OR notes LIKE '%[TEST]%'",
        "test dispatches":  "SELECT COUNT(*) FROM dispatches WHERE dispatch_number LIKE 'TDSP-%' OR notes LIKE '%[TEST]%'",
        "test deliveries":  "SELECT COUNT(*) FROM deliveries WHERE delivery_number LIKE 'TDLV-%' OR notes LIKE '%[TEST]%'",
        "test invoices":    "SELECT COUNT(*) FROM invoices WHERE notes LIKE '%[TEST]%'",
        "test payments":    "SELECT COUNT(*) FROM payments WHERE payment_number LIKE 'TPAY-%' OR notes LIKE '%[TEST]%'",
        "test container issues":
            "SELECT COUNT(*) FROM container_issues WHERE issue_number LIKE 'TCIS-%' OR notes LIKE '%[TEST]%'",
        "test container returns":
            "SELECT COUNT(*) FROM container_returns WHERE return_number LIKE 'TCRT-%' OR notes LIKE '%[TEST]%'",
        "test vehicles":    "SELECT COUNT(*) FROM vehicles WHERE notes LIKE '%[TEST]%'",
        "test drivers":     "SELECT COUNT(*) FROM drivers WHERE notes LIKE '%[TEST]%'",
        "test stock moves":
            "SELECT COUNT(*) FROM stock_movements "
            "WHERE reason LIKE '%[TEST]%' "
            "   OR reference_number LIKE 'TEST-%' "
            "   OR product_id IN (SELECT id FROM products WHERE product_code LIKE 'TPRD-%')",
        "test audit logs":
            "SELECT COUNT(*) FROM audit_logs "
            "WHERE new_values::text LIKE '%[TEST]%' "
            "   OR old_values::text LIKE '%[TEST]%' "
            "   OR username LIKE 'test_%'",
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
