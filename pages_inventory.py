# pages_inventory.py
# Inventory Management UI — Stage 01, Step 3

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from sqlalchemy import text
from database import get_db_connection, read_sql
from services_inventory import (
    get_warehouse_balances, post_opening_stock, transfer_stock,
    post_adjustment, get_ledger, get_stock_balance,
    MOVEMENT_TYPES
)


def inventory_page():
    """Inventory Management — 5 tabs"""
    
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important;
        }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>📊 Inventory Management</h2>", unsafe_allow_html=True)
    st.caption("Stock ledger — the single source of truth for all inventory")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Stock Balance",
        "📥 Opening Stock",
        "🔄 Transfer Stock",
        "⚖️ Adjustments",
        "📋 Ledger",
    ])
    
    # ============================================
    # TAB 1: STOCK BALANCE
    # ============================================
    with tab1:
        st.markdown("#### 📊 Current Stock Balance")
        st.caption("Calculated live from the stock ledger")
        
        wh_df = read_sql("SELECT id, code, name FROM warehouses WHERE is_active = 1 ORDER BY code")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            wh_options = {"All Warehouses": None}
            wh_options.update({f"{row['code']} — {row['name']}": row['id'] for _, row in wh_df.iterrows()})
            selected_wh = st.selectbox("Warehouse", list(wh_options.keys()), key="bal_wh")
            wh_id = wh_options[selected_wh]
        with col2:
            st.write("")
            st.write("")
            if st.button("🔄 Refresh Balances", use_container_width=True):
                st.rerun()
        
        balances_df = get_warehouse_balances(warehouse_id=wh_id)
        
        if balances_df.empty:
            st.info("No products yet. Add products in Products page.")
        else:
            balances_df = balances_df[balances_df['balance'] != 0]
            
            if balances_df.empty:
                st.info("No stock recorded yet. Use '📥 Opening Stock' tab to record initial stock.")
            else:
                show_mode = st.radio(
                    "View Mode",
                    ["By Product (Total)", "By Product & Warehouse"],
                    horizontal=True, key="bal_view_mode"
                )
                
                if show_mode == "By Product (Total)":
                    summary = balances_df.groupby(
                        ['product_id', 'product_code', 'product_name', 'unit']
                    )['balance'].sum().reset_index()
                    summary.columns = ['ID', 'Code', 'Product', 'Unit', 'Total Balance']
                    summary = summary.sort_values('Product')
                    st.dataframe(summary, use_container_width=True, hide_index=True)
                    
                    csv = summary.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download CSV", csv,
                                      f"stock_balance_{datetime.now().strftime('%Y%m%d')}.csv",
                                      "text/csv")
                else:
                    display = balances_df.copy()
                    display = display[['product_code', 'product_name', 'unit',
                                       'warehouse_code', 'warehouse_name', 'balance']]
                    display.columns = ['Code', 'Product', 'Unit', 'WH Code', 'Warehouse', 'Balance']
                    st.dataframe(display, use_container_width=True, hide_index=True)
                    
                    csv = display.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download CSV", csv,
                                      f"stock_balance_detail_{datetime.now().strftime('%Y%m%d')}.csv",
                                      "text/csv")
    
    # ============================================
    # TAB 2: OPENING STOCK
    # ============================================
    with tab2:
        st.markdown("#### 📥 Record Opening Stock")
        st.info("Opening stock is recorded at the **MAIN** warehouse.")
        
        products_df = read_sql("""
            SELECT id, product_code, product_name, unit, is_batch_tracked, cost_price
            FROM products WHERE is_active = 1 ORDER BY product_name
        """)
        
        if products_df.empty:
            st.warning("No products yet. Add products first.")
        else:
            options = {f"{row['product_code']} — {row['product_name']}": row['id']
                       for _, row in products_df.iterrows()}
            
            selected = st.selectbox("Select Product", list(options.keys()), key="open_prod")
            product_id = options[selected]
            
            prod_row = products_df[products_df['id'] == product_id].iloc[0]
            is_batch = bool(prod_row['is_batch_tracked'])
            
            with st.form("opening_stock_form"):
                col1, col2 = st.columns(2)
                with col1:
                    quantity = st.number_input("Opening Quantity *", min_value=0.0,
                                               value=0.0, step=1.0, format="%.2f")
                    unit_cost = st.number_input("Unit Cost (KES)",
                                                min_value=0.0,
                                                value=float(prod_row['cost_price'] or 0),
                                                step=0.50, format="%.2f")
                with col2:
                    if is_batch:
                        batch_number = st.text_input("Batch Number *",
                                                    placeholder="e.g., OPENING-2026")
                        production_date = st.date_input("Production Date", value=date.today())
                        expiry_date = st.date_input("Expiry Date",
                                                    value=date.today() + timedelta(days=365))
                    else:
                        batch_number = None
                        production_date = None
                        expiry_date = None
                        st.info("ℹ️ This product is not batch-tracked")
                
                reason = st.text_area("Reason / Notes", height=80,
                                      placeholder="e.g., Opening balance as at 01/01/2026")
                
                submitted = st.form_submit_button("💾 Post Opening Stock",
                                                  type="primary", use_container_width=True)
                
                if submitted:
                    if quantity <= 0:
                        st.error("❌ Quantity must be greater than zero")
                    elif is_batch and not batch_number:
                        st.error("❌ Batch number required for batch-tracked products")
                    else:
                        ok, msg = post_opening_stock(
                            product_id=product_id,
                            quantity=quantity,
                            unit_cost=unit_cost,
                            batch_number=batch_number,
                            production_date=production_date,
                            expiry_date=expiry_date,
                            reason=reason,
                        )
                        if ok:
                            st.success(msg)
                            st.balloons()
                        else:
                            st.error(msg)
    
    # ============================================
    # TAB 3: TRANSFER STOCK
    # ============================================
    with tab3:
        st.markdown("#### 🔄 Transfer Stock Between Warehouses")
        st.caption("Move stock: MAIN → PROD → DIST")
        
        products_df = read_sql("""
            SELECT id, product_code, product_name, unit
            FROM products WHERE is_active = 1 ORDER BY product_name
        """)
        warehouses_df = read_sql("""
            SELECT id, code, name FROM warehouses WHERE is_active = 1 ORDER BY code
        """)
        
        if products_df.empty or warehouses_df.empty:
            st.warning("Need at least one product and one warehouse.")
        else:
            prod_options = {f"{row['product_code']} — {row['product_name']}": row['id']
                            for _, row in products_df.iterrows()}
            wh_options = {f"{row['code']} — {row['name']}": row['id']
                          for _, row in warehouses_df.iterrows()}
            
            with st.form("transfer_form"):
                col1, col2 = st.columns(2)
                with col1:
                    product_sel = st.selectbox("Product *", list(prod_options.keys()))
                    from_wh = st.selectbox("From Warehouse *", list(wh_options.keys()))
                with col2:
                    to_wh = st.selectbox("To Warehouse *", list(wh_options.keys()),
                                         index=min(1, len(wh_options) - 1))
                    quantity = st.number_input("Quantity *", min_value=0.0,
                                              value=0.0, step=1.0, format="%.2f")
                
                reason = st.text_input("Reason", placeholder="e.g., Distribution to depot")
                
                submitted = st.form_submit_button("🔄 Post Transfer",
                                                  type="primary", use_container_width=True)
                
                if submitted:
                    if quantity <= 0:
                        st.error("❌ Quantity must be > 0")
                    elif wh_options[from_wh] == wh_options[to_wh]:
                        st.error("❌ Source and destination must differ")
                    else:
                        ok, msg = transfer_stock(
                            product_id=prod_options[product_sel],
                            from_wh_id=wh_options[from_wh],
                            to_wh_id=wh_options[to_wh],
                            quantity=quantity,
                            reason=reason,
                        )
                        if ok:
                            st.success(msg)
                            st.balloons()
                        else:
                            st.error(msg)
    
    # ============================================
    # TAB 4: ADJUSTMENTS
    # ============================================
    with tab4:
        st.markdown("#### ⚖️ Stock Adjustments")
        st.warning("⚠️ Adjustments require a reason and are audited.")
        
        products_df = read_sql("""
            SELECT id, product_code, product_name, unit
            FROM products WHERE is_active = 1 ORDER BY product_name
        """)
        warehouses_df = read_sql("""
            SELECT id, code, name FROM warehouses WHERE is_active = 1 ORDER BY code
        """)
        
        if products_df.empty or warehouses_df.empty:
            st.warning("Need at least one product and one warehouse.")
        else:
            prod_options = {f"{row['product_code']} — {row['product_name']}": row['id']
                            for _, row in products_df.iterrows()}
            wh_options = {f"{row['code']} — {row['name']}": row['id']
                          for _, row in warehouses_df.iterrows()}
            
            with st.form("adjustment_form"):
                col1, col2 = st.columns(2)
                with col1:
                    product_sel = st.selectbox("Product *", list(prod_options.keys()), key="adj_prod")
                    wh_sel = st.selectbox("Warehouse *", list(wh_options.keys()), key="adj_wh")
                with col2:
                    pid = prod_options[product_sel]
                    wid = wh_options[wh_sel]
                    current = get_stock_balance(pid, wid)
                    st.metric("Current Balance", f"{current} units")
                    new_quantity = st.number_input("New Quantity *", min_value=0.0,
                                                  value=float(current), step=1.0, format="%.2f")
                
                reason = st.text_area("Reason for Adjustment *", height=80,
                                      placeholder="e.g., Physical count variance, damaged goods, etc.")
                
                submitted = st.form_submit_button("⚖️ Post Adjustment",
                                                  type="primary", use_container_width=True)
                
                if submitted:
                    if not reason:
                        st.error("❌ Reason is required")
                    else:
                        ok, msg = post_adjustment(
                            product_id=pid, warehouse_id=wid,
                            new_quantity=new_quantity, reason=reason,
                        )
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
    
    # ============================================
    # TAB 5: LEDGER
    # ============================================
    with tab5:
        st.markdown("#### 📋 Stock Movement Ledger")
        st.caption("Every stock change is recorded here. This is your audit trail.")
        
        products_df = read_sql("SELECT id, product_code, product_name FROM products ORDER BY product_name")
        warehouses_df = read_sql("SELECT id, code, name FROM warehouses ORDER BY code")
        
        col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
        with col1:
            prod_filter = {"All Products": None}
            prod_filter.update({f"{row['product_code']} — {row['product_name']}": row['id']
                                for _, row in products_df.iterrows()})
            selected_prod = st.selectbox("Product", list(prod_filter.keys()), key="ledger_prod")
        with col2:
            wh_filter = {"All Warehouses": None}
            wh_filter.update({f"{row['code']} — {row['name']}": row['id']
                              for _, row in warehouses_df.iterrows()})
            selected_wh = st.selectbox("Warehouse", list(wh_filter.keys()), key="ledger_wh")
        with col3:
            from_date = st.date_input("From", value=date.today() - timedelta(days=90), key="ledger_from")
        with col4:
            to_date = st.date_input("To", value=date.today(), key="ledger_to")
        
        ledger_df = get_ledger(
            product_id=prod_filter[selected_prod],
            warehouse_id=wh_filter[selected_wh],
            from_date=from_date,
            to_date=to_date,
        )
        
        if ledger_df.empty:
            st.info("No movements in this period.")
        else:
            st.success(f"✅ {len(ledger_df)} movement(s)")
            
            display = ledger_df.copy()
            display['quantity_change'] = display['quantity_change'].apply(
                lambda x: f"+{float(x):,.2f}" if x > 0 else f"{float(x):,.2f}"
            )
            display['balance_after'] = display['balance_after'].apply(
                lambda x: f"{float(x):,.2f}" if x is not None else ""
            )
            
            display = display[['movement_date', 'movement_type', 'reference_number',
                              'product_code', 'product_name', 'warehouse',
                              'quantity_change', 'balance_after', 'reason', 'created_at']]
            display.columns = ['Date', 'Type', 'Reference', 'Code', 'Product',
                              'Warehouse', 'Qty Change', 'Balance', 'Reason', 'Posted At']
            
            st.dataframe(display, use_container_width=True, hide_index=True, height=500)
            
            csv = ledger_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Ledger CSV", csv,
                              f"ledger_{datetime.now().strftime('%Y%m%d')}.csv",
                              "text/csv")
