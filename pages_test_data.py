# pages_test_data.py
# Test Data Generator UI — Full Coverage

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
    st.caption("Populate every table with realistic sample data — safely tagged for one-click cleanup")

    role = st.session_state.get('role') or 'Viewer'
    if role not in ('Administrator', 'Managing Director'):
        st.error("⚠️ Only Administrator and Managing Director can manage test data.")
        return

    st.warning("""
    ⚠️ **This tool inserts real records into your database.**
    Every record is tagged so you can safely remove them later.
    Do **not** run on production data you care about.
    """)

    tab1, tab2, tab3 = st.tabs(["🎬 Generate", "📊 Current Test Data", "🧹 Cleanup"])

    # ============================================
    # TAB 1: GENERATE
    # ============================================
    with tab1:
        st.markdown("#### 🎬 Generate Test Data")

        c1, c2, c3 = st.columns(3)
        with c1:
            n_users = st.slider("Users", 1, 15, 5)
            n_customers = st.slider("Customers", 5, 40, 10)
            n_suppliers = st.slider("Suppliers", 2, 15, 5)
            n_products = st.slider("Products (max 9)", 1, 9, 9)
        with c2:
            n_pos = st.slider("Purchase Orders", 1, 15, 6)
            n_sos = st.slider("Sales Orders", 5, 30, 15)
            n_payments = st.slider("Customer Payments", 0, 20, 10)
            n_container_issues = st.slider("Container Issues", 1, 15, 8)
        with c3:
            n_adjustments = st.slider("Stock Adjustments", 0, 10, 4)
            n_damages = st.slider("Damage Records", 0, 10, 4)
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
            n_payments=n_payments,
            n_adjustments=n_adjustments,
            n_damages=n_damages,
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
                    n_payments=n_payments,
                    n_adjustments=n_adjustments,
                    n_damages=n_damages,
                )

            errors = results.get("errors", [])
            if errors:
                st.error(f"⚠️ {len(errors)} issue(s) during generation")
                with st.expander("❌ Error Details", expanded=True):
                    for e in errors:
                        st.code(e)
            else:
                st.success("✅ Test data generation complete — no errors reported")

            st.markdown("#### 📊 Summary")
            po = results.get("purchase_orders", {}) or {}
            so = results.get("sales_orders", {}) or {}
            ct = results.get("containers", {}) or {}

            summary = [
                {"Entity": "Users", "Created": results.get("users", 0)},
                {"Entity": "Vehicles", "Created": results.get("vehicles", 0)},
                {"Entity": "Drivers", "Created": results.get("drivers", 0)},
                {"Entity": "Customers", "Created": results.get("customers", 0)},
                {"Entity": "Suppliers", "Created": results.get("suppliers", 0)},
                {"Entity": "Products", "Created": results.get("products", 0)},
                {"Entity": "Opening stock movements", "Created": results.get("opening_stock", 0)},
                {"Entity": "Stock adjustments", "Created": results.get("adjustments", 0)},
                {"Entity": "Damage records", "Created": results.get("damages", 0)},
                {"Entity": "Purchase Orders", "Created": po.get("pos", 0)},
                {"Entity": "GRNs confirmed", "Created": po.get("grns_confirmed", 0)},
                {"Entity": "Sales Orders", "Created": so.get("orders", 0)},
                {"Entity": "Orders confirmed", "Created": so.get("confirmed", 0)},
                {"Entity": "Dispatches confirmed", "Created": so.get("dispatched", 0)},
                {"Entity": "Deliveries confirmed", "Created": so.get("delivered", 0)},
                {"Entity": "Partial deliveries", "Created": so.get("partial", 0)},
                {"Entity": "Invoices created", "Created": so.get("invoiced", 0)},
                {"Entity": "Customer payments", "Created": results.get("customer_payments", 0)},
                {"Entity": "Supplier payments", "Created": results.get("supplier_payments", 0)},
                {"Entity": "Container issues", "Created": ct.get("issues", 0)},
                {"Entity": "Container returns", "Created": ct.get("returns", 0)},
            ]
            st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)

            with st.expander("📜 Generation Log"):
                for line in st.session_state.get('test_gen_log', []):
                    st.write(line)

            st.balloons()

    # ============================================
    # TAB 2: CURRENT TEST DATA
    # ============================================
    with tab2:
        st.markdown("#### 📊 Current Test Data")

        counts = count_test_data()

        if not counts:
            st.info("No test data.")
        else:
            df = pd.DataFrame([
                {"Entity": k, "Count": v}
                for k, v in counts.items()
            ])
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
        - Vehicles/drivers tagged `[TEST]`
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
                if isinstance(v, int):
                    rows.append({"Table": k, "Deleted": int(v), "Status": "OK"})
                else:
                    rows.append({"Table": k, "Deleted": 0, "Status": f"⚠️ {str(v)[:120]}"})

            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("Nothing deleted — no test data found.")

            st.rerun()
