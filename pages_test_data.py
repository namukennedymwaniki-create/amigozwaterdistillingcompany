# pages_test_data.py
# Test Data Generator UI

import streamlit as st
import pandas as pd
from datetime import datetime
from database import read_sql
from services_test_data import (
    preview_plan, generate_all, cleanup_test_data, count_test_data,
)


def test_data_page():
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important; }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>🧪 Test Data Generator</h2>", unsafe_allow_html=True)
    st.caption("Populate the system with realistic sample data — safely tagged for one-click cleanup")
    
    role = st.session_state.get('role') or 'Viewer'
    if role not in ('Administrator', 'Managing Director'):
        st.error("⚠️ Only Administrator and Managing Director can manage test data.")
        return
    
    st.warning("""
    ⚠️ **This tool inserts real records into your database.**
    Every record is tagged so you can safely remove them later.
    Do **not** run on production data you care about.
    """)
    
    tab1, tab2, tab3 = st.tabs([
        "🎬 Generate",
        "📊 Current Test Data",
        "🧹 Cleanup",
    ])
    
    # ============================================
    # TAB 1: GENERATE
    # ============================================
    with tab1:
        st.markdown("#### 🎬 Generate Test Data")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            n_users = st.slider("Users", 1, 10, 5)
            n_customers = st.slider("Customers", 5, 30, 10)
            n_suppliers = st.slider("Suppliers", 2, 10, 5)
        with col2:
            n_products = st.slider("Products (max 7)", 1, 7, 7)
            n_pos = st.slider("Purchase Orders", 1, 10, 4)
            n_sos = st.slider("Sales Orders", 3, 20, 10)
        with col3:
            n_container_issues = st.slider("Container Issues", 1, 10, 5)
            st.markdown("&nbsp;")
            dry_run = st.checkbox("🔍 Dry Run (preview only)", value=True)
        
        st.markdown("---")
        st.markdown("#### 📋 Plan Preview")
        
        plan = preview_plan(
            n_users=n_users,
            n_customers=n_customers,
            n_suppliers=n_suppliers,
            n_products=n_products,
            n_pos=n_pos,
            n_sos=n_sos,
            n_container_issues=n_container_issues,
        )
        
        plan_df = pd.DataFrame([
            {"Entity": k.replace("_", " ").title(), "Will Create": v}
            for k, v in plan.items()
        ])
        st.dataframe(plan_df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        if dry_run:
            st.info("ℹ️ Dry Run is ON — nothing will be inserted. Uncheck above and click Run to execute.")
        
        if st.button("🚀 Run Test Data Generation", type="primary",
                    use_container_width=True, disabled=dry_run):
            st.session_state.test_gen_log = []
            
            def log(msg):
                st.session_state.test_gen_log.append(msg)
            
            with st.spinner("Generating test data..."):
                results = generate_all(
                    progress_callback=log,
                    n_users=n_users,
                    n_customers=n_customers,
                    n_suppliers=n_suppliers,
                    n_products=n_products,
                    n_pos=n_pos,
                    n_sos=n_sos,
                    n_container_issues=n_container_issues,
                )
            
            st.success("✅ Test data generation complete")
            
            # Summary
            st.markdown("#### 📊 Summary")
            summary = [
                {"Entity": "Users", "Created": results.get("users", 0)},
                {"Entity": "Customers", "Created": results.get("customers", 0)},
                {"Entity": "Suppliers", "Created": results.get("suppliers", 0)},
                {"Entity": "Products", "Created": results.get("products", 0)},
                {"Entity": "Opening stock records", "Created": results.get("opening_stock", 0)},
                {"Entity": "Purchase Orders", "Created": results.get("purchase_orders", {}).get("pos", 0)},
                {"Entity": "GRNs confirmed", "Created": results.get("purchase_orders", {}).get("grns_confirmed", 0)},
                {"Entity": "Sales Orders", "Created": results.get("sales_orders", {}).get("orders", 0)},
                {"Entity": "Dispatches confirmed", "Created": results.get("sales_orders", {}).get("dispatched", 0)},
                {"Entity": "Invoices created", "Created": results.get("sales_orders", {}).get("invoiced", 0)},
                {"Entity": "Payments", "Created": results.get("payments", 0)},
                {"Entity": "Container issues", "Created": results.get("containers", {}).get("issues", 0)},
                {"Entity": "Container returns", "Created": results.get("containers", {}).get("returns", 0)},
            ]
            st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
            
            # Log
            with st.expander("📜 Generation Log"):
                for line in st.session_state.get('test_gen_log', []):
                    st.write(line)
            
            st.balloons()
    
    # ============================================
    # TAB 2: CURRENT TEST DATA
    # ============================================
    with tab2:
        st.markdown("#### 📊 Current Test Data")
        st.caption("What's currently in the database that would be removed by Cleanup")
        
        counts = count_test_data()
        
        if not counts:
            st.info("No test data.")
        else:
            df = pd.DataFrame([
                {"Entity": k, "Count": v}
                for k, v in counts.items()
            ])
            # Total
            total = sum(v for v in counts.values() if isinstance(v, int))
            c1, c2 = st.columns(2)
            with c1: st.metric("Test Data Categories", len(counts))
            with c2: st.metric("Total Test Records", f"{total:,}")
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            if st.button("🔄 Refresh", key="refresh_test_counts"):
                st.rerun()
    
    # ============================================
    # TAB 3: CLEANUP
    # ============================================
    with tab3:
        st.markdown("#### 🧹 Cleanup Test Data")
        st.error("""
        ⚠️ **This permanently deletes all tagged test data.**
        It will remove:
        - Users starting with `test_`
        - Customers with code `TST-CUST-*`
        - Suppliers with code `TST-SUP-*`
        - Products with code `TPRD-*`
        - All POs, GRNs, SOs, dispatches, deliveries, invoices, payments,
          containers, and stock movements tagged `[TEST]` or with TEST prefixes
        """)
        
        st.markdown("#### 🔍 Preview")
        counts = count_test_data()
        if counts:
            df = pd.DataFrame([
                {"Entity": k, "Will Delete": v}
                for k, v in counts.items()
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        confirm = st.checkbox(
            "I understand this will permanently delete test data.",
            key="cleanup_confirm",
        )
        phrase = st.text_input(
            "Type **DELETE TEST DATA** to confirm",
            key="cleanup_phrase",
        )
        
        if st.button("🧹 Run Cleanup", type="primary",
                    use_container_width=True,
                    disabled=(not confirm or phrase != "DELETE TEST DATA")):
            with st.spinner("Deleting test data..."):
                result = cleanup_test_data()
            
            st.success("✅ Cleanup complete")
            st.markdown("#### 📊 Deletion Summary")
            
            rows = []
            for k, v in result.items():
                if isinstance(v, int) and v > 0:
                    rows.append({"Table": k, "Deleted": v})
                elif isinstance(v, int):
                    rows.append({"Table": k, "Deleted": 0})
                else:
                    rows.append({"Table": k, "Deleted": f"⚠️ {v}"})
            
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("Nothing deleted — no test data found.")
            
            st.rerun()
