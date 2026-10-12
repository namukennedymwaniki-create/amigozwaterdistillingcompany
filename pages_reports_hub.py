# pages_reports_hub.py
# Reports & Controls — Stage 07

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import read_sql
from services_reports import (
    sales_summary, sales_by_customer, sales_by_product,
    stock_valuation, stock_movement_summary,
    supplier_summary, po_status_summary,
    container_report, delivery_summary,
    qc_summary, expired_batches,
    get_audit_logs, get_audit_stats,
    get_table_counts, get_recent_activity, get_db_info,
)
from services_backup import (
    export_table_csv, export_table_json,
    full_db_snapshot, EXPORTABLE_TABLES,
)
from services_permissions import PERMISSIONS_MATRIX
from services_procurement import get_reorder_alerts, get_damaged_goods_log


def reports_hub_page():
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important; }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>📈 Reports & Controls</h2>", unsafe_allow_html=True)
    st.caption("Role-based reporting, audit trail, exports, backups, and system health")
    
    role = st.session_state.get('role') or 'Viewer'
    is_admin = role in ('Administrator', 'Managing Director')
    is_finance = role in ('Administrator', 'Managing Director', 'Accountant')
    
    tabs = ["📊 Operational Reports", "🔒 Audit Trail", "📤 Export Center",
            "💾 Backup", "🩺 System Health", "🛡️ Permissions"]
    
    t1, t2, t3, t4, t5, t6 = st.tabs(tabs)
    
    # ============================================
    # TAB 1: OPERATIONAL REPORTS
    # ============================================
    with t1:
        st.markdown("#### 📊 Operational Reports")
        
        c1, c2 = st.columns(2)
        with c1:
            from_date = st.date_input("From", value=date.today() - timedelta(days=30),
                                     key="rpt_from")
        with c2:
            to_date = st.date_input("To", value=date.today(), key="rpt_to")
        
        report_type = st.selectbox("Report", [
            "Sales Summary (daily)",
            "Sales by Customer",
            "Sales by Product",
            "Stock Valuation",
            "Stock Movement Summary",
            "Supplier Purchases",
            "PO Status Summary",
            "Container Position",
            "Delivery Summary",
            "Quality Control Summary",
            "Expired Batches",
            "Reorder Alerts",
            "Damaged Goods Log",
        ], key="rpt_type")
        
        st.markdown("---")
        
        df = pd.DataFrame()
        title = report_type
        
        try:
            if report_type == "Sales Summary (daily)":
                df = sales_summary(from_date, to_date)
            elif report_type == "Sales by Customer":
                df = sales_by_customer(from_date, to_date)
            elif report_type == "Sales by Product":
                df = sales_by_product(from_date, to_date)
            elif report_type == "Stock Valuation":
                df = stock_valuation()
            elif report_type == "Stock Movement Summary":
                df = stock_movement_summary(from_date, to_date)
            elif report_type == "Supplier Purchases":
                df = supplier_summary(from_date, to_date)
            elif report_type == "PO Status Summary":
                df = po_status_summary()
            elif report_type == "Container Position":
                df = container_report(from_date, to_date)
            elif report_type == "Delivery Summary":
                df = delivery_summary(from_date, to_date)
            elif report_type == "Quality Control Summary":
                df = qc_summary()
            elif report_type == "Expired Batches":
                df = expired_batches()
            elif report_type == "Reorder Alerts":
                df = get_reorder_alerts()
            elif report_type == "Damaged Goods Log":
                df = get_damaged_goods_log(from_date, to_date)
        except Exception as e:
            st.error(f"Report error: {e}")
        
        if df.empty:
            st.info("No data for this report in the selected period.")
        else:
            st.success(f"✅ {len(df)} row(s)")
            st.dataframe(df, use_container_width=True, hide_index=True, height=500)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download CSV",
                csv,
                f"{report_type.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv",
            )
    
    # ============================================
    # TAB 2: AUDIT TRAIL
    # ============================================
    with t2:
        st.markdown("#### 🔒 Audit Trail Explorer")
        
        if not is_finance and not is_admin:
            st.warning("⚠️ Audit trail is restricted to Administrator, Managing Director, and Accountant roles.")
        else:
            stats = get_audit_stats()
            if not stats.empty:
                s = stats.iloc[0]
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric("Total Logs", f"{int(s['total_logs'] or 0):,}")
                with c2: st.metric("Unique Users", int(s['unique_users'] or 0))
                with c3: st.metric("Tables Touched", int(s['tables_touched'] or 0))
                with c4: st.metric("Last Activity", str(s['last_activity'])[:16] if s['last_activity'] else "—")
            
            st.markdown("---")
            st.markdown("#### 🔍 Filter")
            
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                fd = st.date_input("From", value=date.today() - timedelta(days=30), key="aud_fd")
            with f2:
                td = st.date_input("To", value=date.today(), key="aud_td")
            with f3:
                user_filter = st.text_input("Username contains", key="aud_user")
            with f4:
                action_filter = st.text_input("Action contains", key="aud_action")
            
            table_filter = st.selectbox("Table", ["All"] + EXPORTABLE_TABLES, key="aud_table")
            
            logs = get_audit_logs(
                from_date=fd, to_date=td,
                username=user_filter or None,
                table_name=table_filter,
                action=action_filter or None,
                limit=500,
            )
            
            if logs.empty:
                st.info("No audit logs match the filters.")
            else:
                st.success(f"✅ {len(logs)} log(s)")
                
                display = logs.copy()
                display['timestamp'] = display['timestamp'].astype(str)
                display = display[['id', 'timestamp', 'username', 'action',
                                  'table_name', 'record_id']]
                display.columns = ['ID', 'Timestamp', 'User', 'Action',
                                  'Table', 'Record ID']
                st.dataframe(display, use_container_width=True, hide_index=True, height=350)
                
                st.markdown("##### 🔎 Inspect a Log Entry")
                ids = logs['id'].tolist()
                sel = st.selectbox("Log ID", ids, key="aud_detail_sel")
                row = logs[logs['id'] == sel].iloc[0]
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Before**")
                    st.code(str(row.get('old_values') or '—'), language='json')
                with c2:
                    st.markdown("**After**")
                    st.code(str(row.get('new_values') or '—'), language='json')
                
                csv = logs.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Audit Logs CSV", csv,
                                  f"audit_logs_{datetime.now().strftime('%Y%m%d')}.csv",
                                  "text/csv")
    
    # ============================================
    # TAB 3: EXPORT CENTER
    # ============================================
    with t3:
        st.markdown("#### 📤 Export Center")
        st.caption("Download any table as CSV or JSON")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            table_sel = st.selectbox("Table", EXPORTABLE_TABLES, key="exp_table")
        with col2:
            export_format = st.radio("Format", ["CSV", "JSON"], horizontal=True, key="exp_fmt")
        with col3:
            st.write(""); st.write("")
            if st.button("🔄 Preview", use_container_width=True, key="exp_preview"):
                st.rerun()
        
        try:
            preview = read_sql(f"SELECT * FROM {table_sel} LIMIT 100")
            if preview.empty:
                st.info("No data in this table.")
            else:
                st.dataframe(preview, use_container_width=True, hide_index=True, height=350)
        except Exception as e:
            st.error(f"Preview error: {e}")
        
        st.markdown("---")
        
        if export_format == "CSV":
            data, meta = export_table_csv(table_sel)
            fname = meta if isinstance(meta, str) and data else f"{table_sel}.csv"
            if data:
                st.download_button(f"📥 Download {table_sel}.csv", data, fname, "text/csv",
                                  use_container_width=True)
            else:
                st.error(f"Export error: {meta}")
        else:
            data, meta = export_table_json(table_sel)
            fname = meta if isinstance(meta, str) and data else f"{table_sel}.json"
            if data:
                st.download_button(f"📥 Download {table_sel}.json", data, fname,
                                  "application/json", use_container_width=True)
            else:
                st.error(f"Export error: {meta}")
    
    # ============================================
    # TAB 4: BACKUP
    # ============================================
    with t4:
        st.markdown("#### 💾 Backup")
        st.caption("Full JSON snapshot of the ERP data. Restore is manual (SQL).")
        
        if not is_admin:
            st.warning("⚠️ Backup is restricted to Administrator and Managing Director.")
        else:
            st.info("""
            **What this does**
            - Creates a single JSON file with all tables and rows.
            - No passwords/hashes are stripped; treat the file as sensitive.
            
            **Restore guidance**
            1. Stop the app.
            2. Use a DB client (e.g. `psql` for PostgreSQL, `sqlite3` for SQLite).
            3. Import the JSON manually per table.
            4. Or write a Python script using `pandas.read_json()` + `df.to_sql()`.
            """)
            
            if st.button("🧾 Generate Full Snapshot", type="primary", use_container_width=True):
                with st.spinner("Building snapshot..."):
                    data, fname = full_db_snapshot()
                if data:
                    st.success(f"✅ Snapshot ready — {len(data) / 1024:.1f} KB")
                    st.download_button(
                        "📥 Download Snapshot (JSON)",
                        data,
                        fname,
                        "application/json",
                        use_container_width=True,
                    )
                else:
                    st.error(f"Snapshot error: {fname}")
    
    # ============================================
    # TAB 5: SYSTEM HEALTH
    # ============================================
    with t5:
        st.markdown("#### 🩺 System Health")
        
        info = get_db_info()
        c1, c2 = st.columns(2)
        with c1:
            st.info(f"**DB Type:** {info['db_type']}")
            st.info(f"**Cloud Mode:** {'Yes' if info['is_cloud'] else 'No'}")
        with c2:
            st.info(f"**User:** {st.session_state.get('full_name', 'N/A')}")
            st.info(f"**Role:** {st.session_state.get('role', 'N/A')}")
        
        st.markdown("---")
        st.markdown("#### 📊 Table Row Counts")
        
        counts = get_table_counts()
        if counts:
            df = pd.DataFrame(counts)
            st.dataframe(df, use_container_width=True, hide_index=True, height=400)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Table Counts CSV", csv,
                              f"table_counts_{datetime.now().strftime('%Y%m%d')}.csv",
                              "text/csv")
        
        st.markdown("---")
        st.markdown("#### ⏱️ Recent Activity")
        recent = get_recent_activity(20)
        if recent.empty:
            st.caption("No activity.")
        else:
            st.dataframe(recent, use_container_width=True, hide_index=True)
    
    # ============================================
    # TAB 6: PERMISSIONS MATRIX
    # ============================================
    with t6:
        st.markdown("#### 🛡️ Permissions Matrix")
        st.caption("Reference of role capabilities across the ERP")
        
        headers = ["Capability", "Admin", "MD", "Prod Mgr", "QC Off",
                  "Storekeeper", "Proc Off", "Sales Off", "Accountant", "Driver"]
        rows = PERMISSIONS_MATRIX
        
        df = pd.DataFrame(rows, columns=headers)
        st.dataframe(df, use_container_width=True, hide_index=True, height=600)
