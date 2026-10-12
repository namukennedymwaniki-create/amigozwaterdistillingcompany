# pages_quality.py
# Quality Control & Batch Management UI — Stage 01, Step 4

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from sqlalchemy import text
from database import get_db_connection, read_sql
from services_quality import (
    create_batch, change_batch_status, get_batches, get_batch,
    get_available_stock, get_expiring_batches, get_batch_summary,
    is_batch_sellable, generate_batch_number,
    BATCH_STATUSES, EXPIRY_WARNING_DAYS
)
from services_inventory import get_stock_balance


def quality_page():
    """Quality Control — 4 tabs"""
    
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important;
        }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
        .status-released { background: #d1fae5; color: #065f46; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 12px; }
        .status-quarantined { background: #fef3c7; color: #92400e; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 12px; }
        .status-rejected { background: #fee2e2; color: #991b1b; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 12px; }
        .status-expired { background: #f3f4f6; color: #374151; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 12px; }
        .status-recalled { background: #fce7f3; color: #9f1239; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 12px; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>🧪 Quality Control & Batch Management</h2>", unsafe_allow_html=True)
    st.caption("Track batches from production → QC → release. Only Released batches are sellable.")
    
    # ============================================
    # DASHBOARD CARDS
    # ============================================
    conn = get_db_connection()
    if conn:
        try:
            stats = {
                "total": conn.execute(text("SELECT COUNT(*) FROM product_batches")).scalar() or 0,
                "released": conn.execute(text("SELECT COUNT(*) FROM product_batches WHERE quality_status = 'Released'")).scalar() or 0,
                "quarantined": conn.execute(text("SELECT COUNT(*) FROM product_batches WHERE quality_status = 'Quarantined'")).scalar() or 0,
                "rejected": conn.execute(text("SELECT COUNT(*) FROM product_batches WHERE quality_status = 'Rejected'")).scalar() or 0,
                "expired": conn.execute(text(f"SELECT COUNT(*) FROM product_batches WHERE expiry_date < CURRENT_DATE AND quality_status NOT IN ('Rejected','Recalled')")).scalar() or 0,
            }
            conn.close()
        except:
            stats = {"total": 0, "released": 0, "quarantined": 0, "rejected": 0, "expired": 0}
    else:
        stats = {"total": 0, "released": 0, "quarantined": 0, "rejected": 0, "expired": 0}
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: st.metric("📦 Total Batches", stats["total"])
    with col2: st.metric("✅ Released", stats["released"])
    with col3: st.metric("🟡 Quarantined", stats["quarantined"])
    with col4: st.metric("❌ Rejected", stats["rejected"])
    with col5: st.metric("⏰ Expired", stats["expired"])
    
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Batch Register",
        "➕ Create Batch",
        "🧪 QC Actions",
        "⏰ Expiry Monitor",
    ])
    
    # ============================================
    # TAB 1: BATCH REGISTER
    # ============================================
    with tab1:
        st.markdown("#### 📋 Batch Register")
        
        products_df = read_sql("""
            SELECT id, product_code, product_name FROM products 
            WHERE is_active = 1 AND is_batch_tracked = 1
            ORDER BY product_name
        """)
        
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            prod_filter = {"All Products": None}
            prod_filter.update({f"{row['product_code']} — {row['product_name']}": row['id']
                                for _, row in products_df.iterrows()})
            selected_prod = st.selectbox("Product", list(prod_filter.keys()), key="qr_prod")
        with col2:
            status_filter = st.selectbox("Status", ["All"] + BATCH_STATUSES + ["Expired (auto)"], key="qr_status")
        with col3:
            st.write("")
            st.write("")
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        
        batches_df = get_batches(
            product_id=prod_filter[selected_prod],
            status_filter=status_filter,
        )
        
        if batches_df.empty:
            st.info("No batches match the filter. Create one in the '➕ Create Batch' tab.")
        else:
            st.success(f"✅ {len(batches_df)} batch(es) found")
            
            display = batches_df.copy()
            display['production_date'] = display['production_date'].astype(str)
            display['expiry_date'] = display['expiry_date'].astype(str)
            
            # Add visual status
            def format_status(row):
                if row['is_expired']:
                    return "⏰ Expired"
                return f"● {row['quality_status']}"
            
            display['Status'] = display.apply(format_status, axis=1)
            
            if 'is_expiring_soon' in display.columns:
                display['Expiring'] = display['is_expiring_soon'].apply(lambda x: "⚠️ Soon" if x else "")
            
            display = display[['id', 'batch_number', 'product_code', 'product_name', 
                              'unit', 'production_date', 'expiry_date', 'Status', 
                              'quantity_produced', 'notes']]
            display.columns = ['ID', 'Batch #', 'Code', 'Product', 'Unit',
                              'Production', 'Expiry', 'Status', 'Qty Produced', 'Notes']
            
            st.dataframe(display, use_container_width=True, hide_index=True, height=400)
            
            csv = batches_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Batches CSV", csv,
                              f"batches_{datetime.now().strftime('%Y%m%d')}.csv",
                              "text/csv")
    
    # ============================================
    # TAB 2: CREATE BATCH
    # ============================================
    with tab2:
        st.markdown("#### ➕ Create New Batch")
        st.info("New batches start as **Quarantined** — QC must release them before sale.")
        
        products_df = read_sql("""
            SELECT id, product_code, product_name, cost_price
            FROM products 
            WHERE is_active = 1 AND is_batch_tracked = 1
            ORDER BY product_name
        """)
        
        warehouses_df = read_sql("""
            SELECT id, code, name FROM warehouses WHERE is_active = 1 ORDER BY code
        """)
        
        if products_df.empty:
            st.warning("⚠️ No batch-tracked products. Enable batch tracking in Products page.")
        else:
            prod_options = {f"{row['product_code']} — {row['product_name']}": row['id']
                            for _, row in products_df.iterrows()}
            wh_options = {f"{row['code']} — {row['name']}": row['id']
                          for _, row in warehouses_df.iterrows()}
            
            with st.form("create_batch_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    product_sel = st.selectbox("Product *", list(prod_options.keys()), key="cb_prod")
                    product_id = prod_options[product_sel]
                    
                    auto_batch = st.checkbox("Auto-generate batch number", value=True)
                    if auto_batch:
                        # Preview
                        product_code = products_df[products_df['id'] == product_id].iloc[0]['product_code']
                        preview_batch = generate_batch_number(product_code)
                        st.text_input("Batch Number (auto)", value=preview_batch or "", disabled=True)
                        batch_number = None
                    else:
                        batch_number = st.text_input("Batch Number *", placeholder="e.g., BW-500ML-20261013-001")
                    
                    production_date = st.date_input("Production Date", value=date.today())
                    expiry_date = st.date_input("Expiry Date", value=date.today() + timedelta(days=365))
                
                with col2:
                    quantity = st.number_input("Initial Quantity *", min_value=0.0, value=0.0, step=1.0, format="%.2f")
                    wh_sel = st.selectbox("Initial Warehouse *", list(wh_options.keys()), key="cb_wh")
                    warehouse_id = wh_options[wh_sel]
                    
                    default_cost = float(products_df[products_df['id'] == product_id].iloc[0]['cost_price'] or 0)
                    unit_cost = st.number_input("Unit Cost (KES)", min_value=0.0, value=default_cost, step=0.50, format="%.2f")
                    
                    initial_status = st.selectbox("Initial Status", BATCH_STATUSES,
                                                  index=BATCH_STATUSES.index("Quarantined"),
                                                  key="cb_status")
                
                notes = st.text_area("Notes", height=80, placeholder="e.g., Production run 2026-10-13, shift A")
                
                submitted = st.form_submit_button("💾 Create Batch", type="primary", use_container_width=True)
                
                if submitted:
                    if quantity <= 0:
                        st.error("❌ Quantity must be > 0")
                    else:
                        ok, msg, batch_id = create_batch(
                            product_id=product_id,
                            batch_number=batch_number,
                            production_date=production_date,
                            expiry_date=expiry_date,
                            quantity=quantity,
                            warehouse_id=warehouse_id,
                            status=initial_status,
                            notes=notes,
                            unit_cost=unit_cost,
                        )
                        if ok:
                            st.success(msg)
                            st.balloons()
                        else:
                            st.error(msg)
    
    # ============================================
    # TAB 3: QC ACTIONS
    # ============================================
    with tab3:
        st.markdown("#### 🧪 Change Batch Status")
        st.warning("⚠️ Status changes are audited. A reason is required.")
        
        batches_df = get_batches()
        
        if batches_df.empty:
            st.info("No batches to manage.")
        else:
            options = {f"{row['batch_number']} — {row['product_name']} ({row['quality_status']})": row['id']
                       for _, row in batches_df.iterrows()}
            
            selected = st.selectbox("Select Batch", list(options.keys()), key="qca_batch")
            batch_id = options[selected]
            
            batch = get_batch(batch_id)
            
            if batch is not None:
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric("Batch #", batch['batch_number'])
                with col2: st.metric("Product", batch['product_name'])
                with col3: st.metric("Current Status", batch['quality_status'])
                with col4: 
                    exp = batch['expiry_date']
                    st.metric("Expiry Date", str(exp) if exp else "N/A")
                
                st.markdown("---")
                
                with st.form("qc_action_form"):
                    new_status = st.selectbox("New Status *", BATCH_STATUSES,
                                               index=BATCH_STATUSES.index(batch['quality_status'])
                                               if batch['quality_status'] in BATCH_STATUSES else 0)
                    reason = st.text_area("Reason *", height=80,
                                          placeholder="e.g., Passed all quality tests, Physical inspection OK, etc.")
                    
                    submitted = st.form_submit_button("🧪 Apply Status Change", type="primary", use_container_width=True)
                    
                    if submitted:
                        ok, msg = change_batch_status(batch_id, new_status, reason)
                        if ok:
                            st.success(msg)
                            st.balloons()
                        else:
                            st.error(msg)
                
                # Audit trail
                st.markdown("#### 📋 Batch Audit Trail")
                audit_df = read_sql("""
                    SELECT timestamp, username, action, old_values, new_values
                    FROM audit_logs
                    WHERE table_name = 'product_batches' AND record_id = :bid
                    ORDER BY timestamp DESC
                    LIMIT 20
                """, {"bid": batch_id})
                
                if audit_df.empty:
                    st.caption("No status changes recorded yet.")
                else:
                    st.dataframe(audit_df, use_container_width=True, hide_index=True)
    
    # ============================================
    # TAB 4: EXPIRY MONITOR
    # ============================================
    with tab4:
        st.markdown("#### ⏰ Expiry Monitor")
        st.caption(f"Batches expiring within {EXPIRY_WARNING_DAYS} days")
        
        days_ahead = st.slider("Look ahead (days)", 30, 180, EXPIRY_WARNING_DAYS, 30)
        
        expiring_df = get_expiring_batches(days_ahead=days_ahead)
        
        if expiring_df.empty:
            st.success(f"✅ No batches expiring within {days_ahead} days")
        else:
            st.warning(f"⚠️ {len(expiring_df)} batch(es) expiring soon")
            
            def severity_label(row):
                days = row['days_until_expiry']
                if days < 0: return "🔴 Expired"
                if days < 30: return "🔴 Critical"
                if days < 60: return "🟠 Warning"
                return "🟡 Notice"
            
            display = expiring_df.copy()
            display['Severity'] = display.apply(severity_label, axis=1)
            display['expiry_date'] = display['expiry_date'].astype(str)
            
            display = display[['id', 'batch_number', 'product_code', 'product_name',
                              'expiry_date', 'days_until_expiry', 'Severity', 'quality_status']]
            display.columns = ['ID', 'Batch #', 'Code', 'Product',
                              'Expiry Date', 'Days Until Expiry', 'Severity', 'Status']
            
            st.dataframe(display, use_container_width=True, hide_index=True)
            
            csv = expiring_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Expiring Batches CSV", csv,
                              f"expiring_batches_{datetime.now().strftime('%Y%m%d')}.csv",
                              "text/csv")
        
        st.markdown("---")
        st.markdown("#### 📊 Batch Summary by Product")
        
        products_df = read_sql("""
            SELECT id, product_code, product_name FROM products
            WHERE is_active = 1 AND is_batch_tracked = 1
            ORDER BY product_name
        """)
        
        if not products_df.empty:
            for _, prod in products_df.iterrows():
                with st.expander(f"**{prod['product_code']} — {prod['product_name']}**"):
                    summary_df = get_batch_summary(prod['id'])
                    if summary_df.empty:
                        st.caption("No batches")
                    else:
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.dataframe(summary_df, use_container_width=True, hide_index=True)
                        with col2:
                            avail = get_available_stock(prod['id'])
                            st.metric("Sellable Stock", f"{avail:,.2f}")
