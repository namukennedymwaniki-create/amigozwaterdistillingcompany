# =========================================================
# services_backup.py
# Backup & export helpers
# =========================================================

import json
import io
import csv
from datetime import datetime
from sqlalchemy import text
from database import get_db_connection, read_sql


EXPORTABLE_TABLES = [
    "products", "product_categories", "warehouses",
    "suppliers", "customers",
    "product_batches", "stock_movements",
    "purchase_orders", "purchase_order_items",
    "goods_received_notes", "goods_received_note_items",
    "sales_orders", "sales_order_items",
    "dispatches", "dispatch_items",
    "deliveries", "delivery_items",
    "containers", "container_issues", "container_issue_items",
    "container_returns", "container_return_items",
    "invoices", "invoice_items",
    "payments", "audit_logs", "stock_reservations",
    "vehicles", "drivers", "users", "roles",
]


def export_table_csv(table_name):
    """Return (bytes, filename) or (None, error)"""
    try:
        df = read_sql(f"SELECT * FROM {table_name}")
        if df.empty:
            return None, "Empty table"
        csv_bytes = df.to_csv(index=False).encode('utf-8')
        filename = f"{table_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return csv_bytes, filename
    except Exception as e:
        return None, str(e)


def export_table_json(table_name):
    """Return (json_bytes, filename) or (None, error)"""
    try:
        df = read_sql(f"SELECT * FROM {table_name}")
        if df.empty:
            return None, "Empty table"
        
        # Convert to records (handle non-serializable)
        records = df.astype(object).where(df.notna(), None).to_dict(orient='records')
        
        def default(o):
            if hasattr(o, 'isoformat'):
                return o.isoformat()
            return str(o)
        
        payload = {
            "table": table_name,
            "exported_at": datetime.now().isoformat(),
            "record_count": len(records),
            "records": records,
        }
        json_bytes = json.dumps(payload, default=default, indent=2).encode('utf-8')
        filename = f"{table_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        return json_bytes, filename
    except Exception as e:
        return None, str(e)


def full_db_snapshot(tables=None):
    """
    Build a single JSON snapshot of many tables.
    Returns (json_bytes, filename) or (None, error)
    """
    if tables is None:
        tables = EXPORTABLE_TABLES
    
    snapshot = {
        "exported_at": datetime.now().isoformat(),
        "database": "amigoz_erp",
        "tables": {},
    }
    
    def default(o):
        if hasattr(o, 'isoformat'):
            return o.isoformat()
        return str(o)
    
    for t in tables:
        try:
            df = read_sql(f"SELECT * FROM {t}")
            records = df.astype(object).where(df.notna(), None).to_dict(orient='records')
            snapshot["tables"][t] = {
                "count": len(records),
                "records": records,
            }
        except Exception as e:
            snapshot["tables"][t] = {"error": str(e)}
    
    json_bytes = json.dumps(snapshot, default=default, indent=2).encode('utf-8')
    filename = f"amigoz_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return json_bytes, filename
