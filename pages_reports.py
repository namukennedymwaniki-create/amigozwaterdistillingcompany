# pages_reports.py
# Reports — Reorder alerts + Damaged goods log (extended later in Stage 07)

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import read_sql
from services_procurement import get_reorder_alerts, get_damaged_goods_log, post_damaged_goods
from services_suppliers import get_suppliers


def reports_page():
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important; }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>📈 Reports</h2>", unsafe_allow_html=True)
    st.caption("Reorder alerts, damaged goods, and stock health")
    
    tab1, tab2 = st.tabs(["⚠️ Reorder Alerts", "🗑️ Damaged Goods"])
    
    # ---- 1. REORDER ----
    with tab1:
        st.markdown("#### ⚠️ Products Below Reorder Level")
        
        wh_df = read_sql("SELECT id, code, name FROM warehouses WHERE is_active = 1 ORDER BY code")
        wh_opts = {"All Warehouses (total)": None}
        wh_opts.update({f"{r['code']} — {r['name']}": r['id'] for _, r in wh_df.iterrows()})
        sel = st.selectbox("Warehouse", list(wh_opts.keys()), key="reord_wh")
        
        df = get_reorder_alerts(warehouse_id=wh_opts[sel])
        
        if df.empty:
            st.success("✅ No products are below reorder level.")
        else:
            st.warning(f"⚠️ {len(df)} product(s) below reorder level")
            
            display = df.copy()
            display['gap'] = display['reorder_level'] - display['current_stock']
            display['suggested_order'] = display.apply(
                lambda r: r['reorder_quantity'] if r['reorder_quantity'] and r['reorder_quantity'] > 0
                          else (r['reorder_level'] - r['current_stock']) * 2,
                axis=1,
            )
            display = display[['id', 'product_code', 'product_name', 'unit',
                              'current_stock', 'reorder_level', 'gap',
                              'suggested_order', 'cost_price']]
            display.columns = ['ID', 'Code', 'Product', 'Unit',
                              'Current Stock', 'Reorder Level', 'Gap',
                              'Suggested Order', 'Unit Cost']
            st.dataframe(display, use_container_width=True, hide_index=True)
            
            csv = display.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv,
                              f"reorder_alerts_{datetime.now().strftime('%Y%m%d')}.csv",
                              "text/csv")
    
    # ---- 2. DAMAGED GOODS ----
    with tab2:
        st.markdown("#### 🗑️ Damaged Goods Log")
        
        c1, c2 = st.columns(2)
        with c1:
            from_date = st.date_input("From", value=date.today() - timedelta(days=90),
                                     key="dmg_from")
        with c2:
            to_date = st.date_input("To", value=date.today(), key="dmg_to")
        
        df = get_damaged_goods_log(from_date, to_date)
        if df.empty:
            st.info("No damaged goods recorded in this period.")
        else:
            st.success(f"✅ {len(df)} record(s)")
            display = df.copy()
            display['movement_date'] = display['movement_date'].astype(str)
            display = display[['id', 'movement_date', 'reference_number',
                              'product_code', 'product_name', 'warehouse_code',
                              'quantity_change', 'reason', 'created_by']]
            display.columns = ['ID', 'Date', 'Reference', 'Code', 'Product',
                              'Warehouse', 'Qty', 'Reason', 'By']
            st.dataframe(display, use_container_width=True, hide_index=True)
            
            csv = display.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv,
                              f"damaged_goods_{datetime.now().strftime('%Y%m%d')}.csv",
                              "text/csv")
        
        st.markdown("---")
        st.markdown("#### ➕ Record Damaged Goods")
        st.caption("Posts a DAMAGE (negative) movement to the stock ledger")
        
        products = read_sql("""SELECT id, product_code, product_name, unit FROM products
                              WHERE is_active = 1 ORDER BY product_name""")
        warehouses = read_sql("SELECT id, code, name FROM warehouses WHERE is_active = 1 ORDER BY code")
        
        if products.empty or warehouses.empty:
            st.info("Need at least one product and warehouse.")
        else:
            with st.form("dmg_form"):
                c1, c2 = st.columns(2)
                with c1:
                    prod_opts = {f"{r['product_code']} — {r['product_name']}": r['id']
                                 for _, r in products.iterrows()}
                    psel = st.selectbox("Product *", list(prod_opts.keys()), key="dmg_prod")
                    qty = st.number_input("Quantity *", min_value=0.01, value=1.0, step=1.0,
                                         key="dmg_qty")
                with c2:
                    wh_opts = {f"{r['code']} — {r['name']}": r['id']
                               for _, r in warehouses.iterrows()}
                    wsel = st.selectbox("Warehouse *", list(wh_opts.keys()), key="dmg_wh")
                    ref = st.text_input("Reference", value=f"DMG-{date.today().strftime('%Y%m%d')}",
                                       key="dmg_ref")
                
                reason = st.text_area("Reason *", height=80,
                                     placeholder="e.g., Broken during handling, expired stock, etc.",
                                     key="dmg_reason")
                
                if st.form_submit_button("🗑️ Post Damaged Goods", type="primary",
                                        use_container_width=True):
                    if not reason:
                        st.error("Reason required")
                    else:
                        ok, msg = post_damaged_goods(
                            product_id=prod_opts[psel],
                            warehouse_id=wh_opts[wsel],
                            quantity=qty,
                            reason=reason,
                            reference_number=ref,
                        )
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
