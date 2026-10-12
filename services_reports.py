# =========================================================
# services_reports.py
# Reports & Controls — backend service
# =========================================================

import streamlit as st
from datetime import datetime, date, timedelta
from sqlalchemy import text
from database import get_db_connection, read_sql, get_is_cloud


# =========================================================
# SALES REPORTS
# =========================================================
def sales_summary(from_date, to_date):
    return read_sql("""
        SELECT 
            DATE(so.order_date) as day,
            COUNT(*) as order_count,
            SUM(so.subtotal) as subtotal,
            SUM(so.tax_amount) as tax,
            SUM(so.total_amount) as total
        FROM sales_orders so
        WHERE so.order_date BETWEEN :fd AND :td
          AND so.status NOT IN ('Cancelled', 'Draft')
        GROUP BY DATE(so.order_date)
        ORDER BY day DESC
    """, {"fd": from_date, "td": to_date})


def sales_by_customer(from_date, to_date):
    return read_sql("""
        SELECT 
            c.customer_code,
            c.customer_name,
            c.customer_type,
            COUNT(so.id) as orders,
            SUM(so.total_amount) as total_sales
        FROM sales_orders so
        JOIN customers c ON so.customer_id = c.id
        WHERE so.order_date BETWEEN :fd AND :td
          AND so.status NOT IN ('Cancelled', 'Draft')
        GROUP BY c.customer_code, c.customer_name, c.customer_type
        ORDER BY total_sales DESC
    """, {"fd": from_date, "td": to_date})


def sales_by_product(from_date, to_date):
    return read_sql("""
        SELECT 
            p.product_code,
            p.product_name,
            p.unit,
            SUM(soi.quantity_ordered) as qty_sold,
            SUM(soi.line_total) as revenue
        FROM sales_order_items soi
        JOIN sales_orders so ON soi.order_id = so.id
        JOIN products p ON soi.product_id = p.id
        WHERE so.order_date BETWEEN :fd AND :td
          AND so.status NOT IN ('Cancelled', 'Draft')
        GROUP BY p.product_code, p.product_name, p.unit
        ORDER BY revenue DESC
    """, {"fd": from_date, "td": to_date})


# =========================================================
# INVENTORY REPORTS
# =========================================================
def stock_valuation():
    return read_sql("""
        SELECT 
            p.product_code,
            p.product_name,
            p.unit,
            p.cost_price,
            p.selling_price,
            COALESCE((
                SELECT SUM(sm.quantity_change)
                FROM stock_movements sm
                WHERE sm.product_id = p.id AND sm.is_posted = 1
            ), 0) as current_stock,
            COALESCE((
                SELECT SUM(sm.quantity_change)
                FROM stock_movements sm
                WHERE sm.product_id = p.id AND sm.is_posted = 1
            ), 0) * COALESCE(p.cost_price, 0) as cost_value,
            COALESCE((
                SELECT SUM(sm.quantity_change)
                FROM stock_movements sm
                WHERE sm.product_id = p.id AND sm.is_posted = 1
            ), 0) * COALESCE(p.selling_price, 0) as retail_value
        FROM products p
        WHERE p.is_active = 1
        ORDER BY cost_value DESC
    """)


def stock_movement_summary(from_date, to_date):
    return read_sql("""
        SELECT 
            sm.movement_type,
            COUNT(*) as movements,
            SUM(CASE WHEN sm.quantity_change > 0 THEN sm.quantity_change ELSE 0 END) as total_in,
            SUM(CASE WHEN sm.quantity_change < 0 THEN ABS(sm.quantity_change) ELSE 0 END) as total_out
        FROM stock_movements sm
        WHERE sm.movement_date BETWEEN :fd AND :td
        GROUP BY sm.movement_type
        ORDER BY sm.movement_type
    """, {"fd": from_date, "td": to_date})


# =========================================================
# PROCUREMENT REPORTS
# =========================================================
def supplier_summary(from_date, to_date):
    return read_sql("""
        SELECT 
            s.supplier_code,
            s.supplier_name,
            COUNT(po.id) as po_count,
            SUM(po.total_amount) as total_spend
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        WHERE po.order_date BETWEEN :fd AND :td
          AND po.status != 'Cancelled'
        GROUP BY s.supplier_code, s.supplier_name
        ORDER BY total_spend DESC
    """, {"fd": from_date, "td": to_date})


def po_status_summary():
    return read_sql("""
        SELECT 
            status,
            COUNT(*) as po_count,
            SUM(total_amount) as total_value
        FROM purchase_orders
        GROUP BY status
        ORDER BY status
    """)


# =========================================================
# CONTAINER REPORTS
# =========================================================
def container_report(from_date, to_date):
    return read_sql("""
        SELECT 
            c.container_code,
            c.container_name,
            COALESCE(SUM(cii.quantity_issued), 0) as issued,
            COALESCE(SUM(cii.quantity_returned), 0) as returned,
            COALESCE(SUM(cii.quantity_lost), 0) as lost,
            COALESCE(SUM(cii.quantity_issued - cii.quantity_returned - cii.quantity_lost), 0) as outstanding
        FROM containers c
        LEFT JOIN container_issue_items cii ON c.id = cii.container_id
        LEFT JOIN container_issues ci ON cii.issue_id = ci.id
            AND ci.issue_date BETWEEN :fd AND :td
        GROUP BY c.container_code, c.container_name
        ORDER BY c.container_code
    """, {"fd": from_date, "td": to_date})


# =========================================================
# DELIVERY REPORTS
# =========================================================
def delivery_summary(from_date, to_date):
    return read_sql("""
        SELECT 
            d.status,
            COUNT(*) as deliveries,
            SUM(CASE WHEN d.is_partial = TRUE THEN 1 ELSE 0 END) as partial_count
        FROM deliveries d
        WHERE d.delivery_date BETWEEN :fd AND :td
        GROUP BY d.status
        ORDER BY d.status
    """, {"fd": from_date, "td": to_date})


# =========================================================
# QUALITY REPORTS
# =========================================================
def qc_summary():
    return read_sql("""
        SELECT 
            quality_status,
            COUNT(*) as batch_count,
            COALESCE(SUM(quantity_produced), 0) as total_qty
        FROM product_batches
        GROUP BY quality_status
        ORDER BY quality_status
    """)


def expired_batches():
    return read_sql("""
        SELECT 
            pb.batch_number,
            p.product_code,
            p.product_name,
            pb.production_date,
            pb.expiry_date,
            pb.quality_status,
            pb.quantity_produced,
            (:today - pb.expiry_date) as days_expired
        FROM product_batches pb
        JOIN products p ON pb.product_id = p.id
        WHERE pb.expiry_date IS NOT NULL
          AND pb.expiry_date < :today
          AND pb.quality_status NOT IN ('Rejected', 'Recalled')
        ORDER BY pb.expiry_date ASC
    """, {"today": date.today()})


# =========================================================
# AUDIT TRAIL
# =========================================================
def get_audit_logs(from_date=None, to_date=None, username=None,
                   table_name=None, action=None, limit=500):
    query = """
        SELECT 
            al.id,
            al.timestamp,
            al.username,
            al.action,
            al.table_name,
            al.record_id,
            al.old_values,
            al.new_values,
            al.ip_address
        FROM audit_logs al
        WHERE 1=1
    """
    params = {"limit": limit}
    
    if from_date:
        query += " AND al.timestamp >= :fd"; params["fd"] = from_date
    if to_date:
        query += " AND al.timestamp <= :td"; params["td"] = to_date
    if username:
        query += " AND LOWER(al.username) LIKE :un"; params["un"] = f"%{username.lower()}%"
    if table_name and table_name != "All":
        query += " AND al.table_name = :tn"; params["tn"] = table_name
    if action and action != "All":
        query += " AND al.action LIKE :act"; params["act"] = f"%{action}%"
    
    query += " ORDER BY al.timestamp DESC LIMIT :limit"
    return read_sql(query, params)


def get_audit_stats():
    return read_sql("""
        SELECT 
            COUNT(*) as total_logs,
            COUNT(DISTINCT username) as unique_users,
            COUNT(DISTINCT table_name) as tables_touched,
            MAX(timestamp) as last_activity
        FROM audit_logs
    """)


# =========================================================
# SYSTEM HEALTH
# =========================================================
def get_table_counts():
    tables = [
        "users", "roles", "warehouses", "products", "product_categories",
        "suppliers", "customers", "product_batches", "stock_movements",
        "purchase_orders", "purchase_order_items",
        "goods_received_notes", "goods_received_note_items",
        "sales_orders", "sales_order_items",
        "dispatches", "dispatch_items",
        "deliveries", "delivery_items",
        "containers", "container_issues", "container_issue_items",
        "container_returns", "container_return_items",
        "invoices", "invoice_items",
        "payments", "audit_logs", "stock_reservations",
        "vehicles", "drivers",
    ]
    
    conn = get_db_connection()
    if not conn:
        return []
    
    results = []
    try:
        for t in tables:
            try:
                c = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                results.append({"Table": t, "Records": c or 0})
            except:
                results.append({"Table": t, "Records": "missing"})
    finally:
        conn.close()
    return results


def get_recent_activity(limit=20):
    return read_sql("""
        SELECT timestamp, username, action, table_name, record_id
        FROM audit_logs
        ORDER BY timestamp DESC LIMIT :lim
    """, {"lim": limit})


def get_db_info():
    return {
        "db_type": "PostgreSQL (Neon)" if get_is_cloud() else "SQLite (local)",
        "is_cloud": get_is_cloud(),
    }
