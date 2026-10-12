# pages_procurement.py
# Purchase Orders + GRN UI

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import read_sql
from services_suppliers import get_suppliers
from services_procurement import (
    create_purchase_order, approve_purchase_order, cancel_purchase_order,
    get_purchase_orders, get_purchase_order, get_po_items,
    create_grn, confirm_grn, cancel_grn,
    get_grns, get_grn, get_grn_items,
    generate_po_number, generate_grn_number,
    PO_STATUSES, GRN_STATUSES,
)


def procurement_page():
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important; }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>🛒 Procurement</h2>", unsafe_allow_html=True)
    st.caption("Raise purchase orders, receive goods, and drive stock-in via GRN")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Purchase Orders",
        "➕ Create PO",
        "📥 Receive Goods",
        "📦 GRN Register",
    ])
    
    # ---- 1. PO LIST ----
    with tab1:
        st.markdown("#### 📋 Purchase Orders")
        col1, col2 = st.columns([3, 1])
        with col1:
            search = st.text_input("🔍 Search PO # or supplier", key="po_search")
        with col2:
            status_filter = st.selectbox("Status", ["All"] + PO_STATUSES, key="po_status")
        
        df = get_purchase_orders(status_filter=status_filter, search=search or None)
        if df.empty:
            st.info("📭 No POs yet.")
        else:
            st.success(f"✅ {len(df)} PO(s)")
            display = df.copy()
            display['total_amount'] = display['total_amount'].apply(lambda x: f"KES {float(x):,.2f}")
            display['order_date'] = display['order_date'].astype(str)
            display = display[['id', 'po_number', 'order_date', 'supplier_name',
                              'items_count', 'total_amount', 'status']]
            display.columns = ['ID', 'PO #', 'Date', 'Supplier', 'Items', 'Total', 'Status']
            st.dataframe(display, use_container_width=True, hide_index=True, height=350)
            
            st.markdown("---")
            st.markdown("#### 🔍 PO Details")
            sel = st.selectbox("Select PO",
                              [f"{r['po_number']} — {r['supplier_name']} ({r['status']})" for _, r in df.iterrows()],
                              key="po_detail_sel")
            sel_id = df.iloc[[f"{r['po_number']} — {r['supplier_name']} ({r['status']})" 
                             for _, r in df.iterrows()].index(sel)]['id']
            po = get_purchase_order(sel_id)
            items = get_po_items(sel_id)
            
            if po is not None:
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric("PO #", po['po_number'])
                with c2: st.metric("Supplier", po['supplier_name'])
                with c3: st.metric("Status", po['status'])
                with c4: st.metric("Total", f"KES {float(po['total_amount']):,.2f}")
                
                if not items.empty:
                    di = items.copy()
                    di['unit_cost'] = di['unit_cost'].apply(lambda x: f"KES {float(x):,.2f}")
                    di['line_total'] = di['line_total'].apply(lambda x: f"KES {float(x):,.2f}")
                    st.dataframe(di[['product_code', 'product_name', 'quantity_ordered',
                                    'quantity_received', 'qty_outstanding',
                                    'unit_cost', 'line_total', 'unit']],
                                use_container_width=True, hide_index=True)
                
                st.markdown("---")
                c_a, c_b = st.columns(2)
                with c_a:
                    if po['status'] == 'Draft':
                        if st.button("✅ Approve PO", type="primary",
                                     use_container_width=True, key="po_appr"):
                            ok, msg = approve_purchase_order(sel_id)
                            if ok: st.success(msg); st.rerun()
                            else: st.error(msg)
                with c_b:
                    if po['status'] in ('Draft', 'Approved', 'Partially Received'):
                        if st.button("❌ Cancel PO", use_container_width=True, key="po_cancel"):
                            reason = st.text_input("Cancellation reason", key="po_cancel_reason")
                            if reason:
                                ok, msg = cancel_purchase_order(sel_id, reason)
                                if ok: st.success(msg); st.rerun()
                                else: st.error(msg)
                            else:
                                st.warning("Enter a reason")
    
    # ---- 2. CREATE PO ----
    with tab2:
        st.markdown("#### ➕ Create Purchase Order")
        st.info(f"💡 Next PO: **{generate_po_number()}**")
        
        suppliers = get_suppliers(active_only=True)
        products = read_sql("""
            SELECT id, product_code, product_name, unit, cost_price
            FROM products WHERE is_active = 1 ORDER BY product_name
        """)
        
        if suppliers.empty or products.empty:
            st.warning("Need at least one supplier and one product.")
        else:
            sup_opts = {f"{r['supplier_code']} — {r['supplier_name']}": r['id']
                        for _, r in suppliers.iterrows()}
            prod_opts = {f"{r['product_code']} — {r['product_name']}": r['id']
                         for _, r in products.iterrows()}
            
            col1, col2, col3 = st.columns(3)
            with col1:
                sup_sel = st.selectbox("Supplier *", list(sup_opts.keys()), key="po_sup")
                order_date = st.date_input("Order Date", value=date.today(), key="po_odate")
            with col2:
                expected_date = st.date_input("Expected Date",
                                              value=date.today() + timedelta(days=7),
                                              key="po_edate")
                terms_opts = ["Cash", "7 days", "14 days", "30 days", "60 days", "90 days"]
                terms = st.selectbox("Payment Terms", terms_opts, index=3, key="po_terms")
            with col3:
                notes = st.text_area("Notes", height=60, key="po_notes")
            
            if 'po_items' not in st.session_state:
                st.session_state.po_items = []
            
            st.markdown("---")
            st.markdown("#### 📦 Line Items")
            
            with st.expander("➕ Add Item", expanded=True):
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                with c1:
                    prod_sel = st.selectbox("Product", list(prod_opts.keys()), key="po_it_prod")
                with c2:
                    qty = st.number_input("Qty", min_value=0.01, value=1.0, step=1.0, key="po_it_qty")
                with c3:
                    default_cost = float(products[products['id'] == prod_opts[prod_sel]].iloc[0]['cost_price'] or 0)
                    cost = st.number_input("Unit Cost", min_value=0.0, value=default_cost,
                                          step=0.50, format="%.2f", key="po_it_cost")
                with c4:
                    st.write("")
                    st.write("")
                    if st.button("➕ Add", use_container_width=True, key="po_add_btn"):
                        st.session_state.po_items.append({
                            'product_id': prod_opts[prod_sel],
                            'product_name': products[products['id'] == prod_opts[prod_sel]].iloc[0]['product_name'],
                            'product_code': products[products['id'] == prod_opts[prod_sel]].iloc[0]['product_code'],
                            'quantity_ordered': qty,
                            'unit_cost': cost,
                            'line_total': qty * cost,
                        })
                        st.rerun()
            
            if st.session_state.po_items:
                st.markdown("#### 🛒 Current Items")
                st.dataframe(pd.DataFrame(st.session_state.po_items)[
                    ['product_code', 'product_name', 'quantity_ordered', 'unit_cost', 'line_total']
                ], use_container_width=True, hide_index=True)
                
                total = sum(it['line_total'] for it in st.session_state.po_items)
                st.metric("PO Total", f"KES {total:,.2f}")
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🗑️ Clear Items", use_container_width=True, key="po_clear"):
                        st.session_state.po_items = []
                        st.rerun()
                with c2:
                    if st.button("💾 Create PO (Draft)", type="primary",
                                 use_container_width=True, key="po_create"):
                        ok, msg, po_id = create_purchase_order(
                            supplier_id=sup_opts[sup_sel],
                            order_date=order_date,
                            expected_date=expected_date,
                            payment_terms=terms,
                            notes=notes,
                            items=st.session_state.po_items,
                        )
                        if ok:
                            st.success(msg)
                            st.session_state.po_items = []
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(msg)
    
    # ---- 3. RECEIVE GOODS (create + confirm GRN) ----
    with tab3:
        st.markdown("#### 📥 Receive Goods (Create GRN)")
        st.caption("Stock is only increased when a GRN is **confirmed**.")
        st.info(f"💡 Next GRN: **{generate_grn_number()}**")
        
        po_df = get_purchase_orders(status_filter=None)
        po_df = po_df[po_df['status'].isin(['Approved', 'Partially Received'])] if not po_df.empty else po_df
        
        if po_df.empty:
            st.info("No POs available for receiving.")
        else:
            po_opts = {f"{r['po_number']} — {r['supplier_name']} ({r['status']})": r['id']
                       for _, r in po_df.iterrows()}
            po_sel = st.selectbox("Select PO", list(po_opts.keys()), key="grn_po")
            po_id = po_opts[po_sel]
            
            po_items = get_po_items(po_id)
            po_items = po_items[po_items['qty_outstanding'] > 0] if not po_items.empty else po_items
            
            wh_df = read_sql("SELECT id, code, name FROM warehouses WHERE is_active = 1 ORDER BY code")
            wh_opts = {f"{r['code']} — {r['name']}": r['id'] for _, r in wh_df.iterrows()}
            
            # Default MAIN if present
            default_idx = 0
            for i, (k, v) in enumerate(wh_opts.items()):
                if k.startswith("MAIN"):
                    default_idx = i
                    break
            
            col1, col2 = st.columns(2)
            with col1:
                recv_date = st.date_input("Received Date", value=date.today(), key="grn_rdate")
            with col2:
                wh_sel = st.selectbox("Warehouse", list(wh_opts.keys()),
                                     index=default_idx, key="grn_wh")
            
            grn_notes = st.text_area("Notes", height=60, key="grn_notes")
            
            st.markdown("---")
            st.markdown("#### 📦 Line Items (enter received qty)")
            
            if po_items.empty:
                st.info("Nothing outstanding on this PO.")
            else:
                grn_items = []
                for _, it in po_items.iterrows():
                    with st.expander(f"{it['product_code']} — {it['product_name']} "
                                     f"(Outstanding: {float(it['qty_outstanding']):,.2f})"):
                        c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
                        with c1:
                            qrec = st.number_input(
                                "Received",
                                min_value=0.0, max_value=float(it['qty_outstanding']),
                                value=float(it['qty_outstanding']),
                                step=1.0, format="%.2f",
                                key=f"grn_rec_{it['id']}",
                            )
                        with c2:
                            qrej = st.number_input(
                                "Rejected",
                                min_value=0.0, max_value=float(it['qty_outstanding']),
                                value=0.0, step=1.0, format="%.2f",
                                key=f"grn_rej_{it['id']}",
                            )
                        with c3:
                            cost = st.number_input(
                                "Unit Cost",
                                min_value=0.0, value=float(it['unit_cost'] or 0),
                                step=0.50, format="%.2f",
                                key=f"grn_cost_{it['id']}",
                            )
                        with c4:
                            reason = st.text_input("Rejection reason",
                                                  key=f"grn_reason_{it['id']}")
                        
                        if qrec + qrej > 0:
                            grn_items.append({
                                'po_item_id': it['id'],
                                'product_id': it['product_id'],
                                'quantity_received': qrec,
                                'quantity_rejected': qrej,
                                'unit_cost': cost,
                                'rejection_reason': reason or None,
                            })
                
                st.markdown("---")
                if st.button("💾 Create GRN (Draft)", type="primary",
                             use_container_width=True, key="grn_create"):
                    if not grn_items:
                        st.error("Enter at least one received qty")
                    else:
                        ok, msg, grn_id = create_grn(
                            po_id=po_id,
                            warehouse_id=wh_opts[wh_sel],
                            received_date=recv_date,
                            notes=grn_notes,
                            items=grn_items,
                        )
                        if ok:
                            st.success(msg)
                            st.info("Now confirm it below (or in the GRN Register tab).")
                            st.session_state.last_grn_id = grn_id
                            st.rerun()
                        else:
                            st.error(msg)
        
        # Confirm-any-draft section
        st.markdown("---")
        st.markdown("#### ✅ Confirm a Draft GRN")
        drafts = get_grns(status_filter="Draft")
        if drafts.empty:
            st.caption("No draft GRNs to confirm.")
        else:
            sel = st.selectbox(
                "Select Draft GRN",
                [f"{r['grn_number']} — {r['supplier_name']} (PO {r['po_number']})"
                 for _, r in drafts.iterrows()],
                key="grn_confirm_sel",
            )
            grn_id = drafts.iloc[[f"{r['grn_number']} — {r['supplier_name']} (PO {r['po_number']})"
                                 for _, r in drafts.iterrows()].index(sel)]['id']
            
            if st.button("🚚 Confirm GRN (post stock)", type="primary",
                         use_container_width=True, key="grn_confirm_btn"):
                ok, msg = confirm_grn(grn_id)
                if ok: st.success(msg); st.balloons(); st.rerun()
                else: st.error(msg)
    
    # ---- 4. GRN REGISTER ----
    with tab4:
        st.markdown("#### 📦 GRN Register")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            search = st.text_input("🔍 Search GRN # or supplier", key="grn_search")
        with col2:
            status_filter = st.selectbox("Status", ["All"] + GRN_STATUSES, key="grn_status")
        
        df = get_grns(status_filter=status_filter, search=search or None)
        if df.empty:
            st.info("📭 No GRNs yet.")
        else:
            st.success(f"✅ {len(df)} GRN(s)")
            display = df.copy()
            display['received_date'] = display['received_date'].astype(str)
            display = display[['id', 'grn_number', 'received_date', 'po_number',
                              'supplier_name', 'warehouse_code', 'items_count', 'status']]
            display.columns = ['ID', 'GRN #', 'Date', 'PO #', 'Supplier',
                              'Warehouse', 'Items', 'Status']
            st.dataframe(display, use_container_width=True, hide_index=True, height=350)
            
            st.markdown("---")
            st.markdown("#### 🔍 GRN Details")
            sel = st.selectbox(
                "Select GRN",
                [f"{r['grn_number']} — {r['supplier_name']}" for _, r in df.iterrows()],
                key="grn_det_sel",
            )
            grn_id = df.iloc[[f"{r['grn_number']} — {r['supplier_name']}" 
                             for _, r in df.iterrows()].index(sel)]['id']
            g = get_grn(grn_id)
            gi = get_grn_items(grn_id)
            
            if g is not None:
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric("GRN #", g['grn_number'])
                with c2: st.metric("PO #", g.get('po_number') or '—')
                with c3: st.metric("Warehouse", g.get('warehouse_name') or '—')
                with c4: st.metric("Status", g['status'])
                
                if not gi.empty:
                    st.dataframe(gi[['product_code', 'product_name', 'batch_number',
                                    'quantity_received', 'quantity_rejected',
                                    'unit_cost', 'rejection_reason', 'unit']],
                                use_container_width=True, hide_index=True)
                
                if g['status'] == 'Draft':
                    if st.button("❌ Cancel GRN", use_container_width=True, key="grn_cancel"):
                        reason = st.text_input("Reason", key="grn_cancel_reason")
                        if reason:
                            ok, msg = cancel_grn(grn_id, reason)
                            if ok: st.success(msg); st.rerun()
                            else: st.error(msg)
                        else:
                            st.warning("Enter a reason")
