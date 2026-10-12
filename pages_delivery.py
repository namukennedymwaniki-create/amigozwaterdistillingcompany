# pages_delivery.py
# Delivery Confirmation UI — Stage 05

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import read_sql
from services_delivery import (
    create_delivery_from_dispatch, confirm_delivery,
    get_deliveries, get_delivery, get_delivery_items,
    update_delivery_item, get_delivery_performance,
    generate_delivery_note_html, REJECTION_REASONS
)
from services_dispatch import get_dispatches, get_dispatch


def delivery_page():
    """Delivery Confirmation — 3 tabs"""
    
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important;
        }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>📬 Delivery Confirmation</h2>", unsafe_allow_html=True)
    st.caption("Confirm delivery, capture POD, and record partial deliveries")
    
    tab1, tab2, tab3 = st.tabs([
        "➕ Create Delivery",
        "📋 Confirm Delivery",
        "📊 Performance",
    ])
    
    # ============================================
    # TAB 1: CREATE DELIVERY FROM DISPATCH
    # ============================================
    with tab1:
        st.markdown("#### ➕ Create Delivery from Dispatch")
        st.caption("Pick a Dispatched (in-transit) record to create a pending delivery")
        
        dispatches = get_dispatches(status_filter="Dispatched")
        
        if dispatches.empty:
            st.info("📭 No dispatched records awaiting delivery.")
        else:
            options = {
                f"{row['dispatch_number']} — {row.get('customer_name') or 'N/A'} ({row['dispatch_date']})": row['id']
                for _, row in dispatches.iterrows()
            }
            sel = st.selectbox("Select Dispatched Record", list(options.keys()), key="dlv_from_dsp")
            dsp_id = options[sel]
            
            col1, col2 = st.columns(2)
            with col1:
                ddate = st.date_input("Delivery Date", value=date.today(), key="dlv_date")
            with col2:
                dby = st.text_input("Delivered By (driver)", key="dlv_by")
            
            if st.button("➕ Create Delivery (Pending)", type="primary",
                         use_container_width=True, key="dlv_create"):
                ok, msg, dlv_id = create_delivery_from_dispatch(dsp_id, ddate, dby)
                if ok:
                    st.success(msg)
                    st.info("Go to '📋 Confirm Delivery' tab to complete")
                    st.rerun()
                else:
                    st.error(msg)
    
    # ============================================
    # TAB 2: CONFIRM DELIVERY
    # ============================================
    with tab2:
        st.markdown("#### 📋 Confirm Pending Deliveries")
        
        pending = get_deliveries(status_filter="Pending")
        completed = get_deliveries(status_filter=None)
        
        # ---------- Pending ----------
        if pending.empty:
            st.info("📭 No pending deliveries.")
        else:
            st.success(f"✅ {len(pending)} pending delivery(ies)")
            
            options = {
                f"{row['delivery_number']} — {row.get('customer_name') or 'N/A'} (dispatch {row['dispatch_number']})": row['id']
                for _, row in pending.iterrows()
            }
            sel = st.selectbox("Select Pending Delivery", list(options.keys()), key="dlv_conf_sel")
            dlv_id = options[sel]
            
            d = get_delivery(dlv_id)
            items = get_delivery_items(dlv_id)
            
            if d is not None and not items.empty:
                st.markdown("---")
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric("Delivery #", d['delivery_number'])
                with col2: st.metric("Customer", d.get('customer_name') or '—')
                with col3: st.metric("Warehouse", d.get('warehouse_name') or '—')
                with col4: st.metric("Order", d.get('order_number') or '—')
                
                st.markdown("#### 📦 Line Items")
                st.caption("Adjust 'Received' and 'Rejected' to reflect what actually arrived.")
                
                # Editable grid via individual forms (Streamlit data_editor optional)
                for _, it in items.iterrows():
                    with st.expander(
                        f"{it['product_code']} — {it['product_name']} "
                        f"(Dispatched: {float(it['quantity_dispatched']):,.2f} {it.get('unit') or ''})"
                    ):
                        c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
                        with c1:
                            qrec = st.number_input(
                                "Received",
                                min_value=0.0,
                                max_value=float(it['quantity_dispatched']),
                                value=float(it['quantity_received'] or 0),
                                step=1.0,
                                format="%.2f",
                                key=f"dlv_rec_{it['id']}"
                            )
                        with c2:
                            qrej = st.number_input(
                                "Rejected",
                                min_value=0.0,
                                max_value=float(it['quantity_dispatched']),
                                value=float(it['quantity_rejected'] or 0),
                                step=1.0,
                                format="%.2f",
                                key=f"dlv_rej_{it['id']}"
                            )
                        with c3:
                            reason = st.selectbox(
                                "Reason",
                                [""] + REJECTION_REASONS,
                                index=(REJECTION_REASONS.index(it['rejection_reason']) + 1)
                                      if it.get('rejection_reason') in REJECTION_REASONS else 0,
                                key=f"dlv_reason_{it['id']}"
                            )
                        with c4:
                            notes = st.text_input(
                                "Notes",
                                value=it.get('notes') or "",
                                key=f"dlv_notes_{it['id']}"
                            )
                        
                        if st.button("💾 Save Line", key=f"dlv_save_{it['id']}"):
                            if qrec + qrej > float(it['quantity_dispatched']) + 0.0001:
                                st.error("Received + Rejected cannot exceed Dispatched")
                            elif qrej > 0 and not reason:
                                st.error("Reason required when Rejected > 0")
                            else:
                                ok, msg = update_delivery_item(
                                    it['id'],
                                    quantity_received=qrec,
                                    quantity_rejected=qrej,
                                    rejection_reason=reason or None,
                                    notes=notes or None,
                                )
                                if ok:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                
                st.markdown("---")
                st.markdown("#### ✍️ Proof of Delivery")
                
                with st.form("confirm_delivery_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        rname = st.text_input("Received By Name *", key="pod_name")
                        rphone = st.text_input("Received By Phone", key="pod_phone")
                    with col2:
                        sigref = st.text_input("Signature Reference",
                                               placeholder="e.g., 'Signed on paper', ref#",
                                               key="pod_sig")
                        photourl = st.text_input("Photo URL (optional)",
                                                 placeholder="Paste GCS/drive link",
                                                 key="pod_photo")
                    
                    dnotes = st.text_area("Delivery Notes", height=80, key="pod_notes")
                    
                    if st.form_submit_button("✅ Confirm Delivery", type="primary",
                                             use_container_width=True):
                        if not rname:
                            st.error("Received By Name required")
                        else:
                            ok, msg = confirm_delivery(
                                dlv_id,
                                received_by_name=rname,
                                received_by_phone=rphone,
                                signature_ref=sigref,
                                photo_url=photourl,
                                delivery_notes=dnotes,
                            )
                            if ok:
                                st.success(msg)
                                st.balloons()
                                st.rerun()
                            else:
                                st.error(msg)
        
        # ---------- Completed ----------
        st.markdown("---")
        st.markdown("#### ✅ Completed Deliveries")
        
        completed_only = completed[completed['status'].isin(['Delivered', 'Partially Delivered'])] if not completed.empty else completed
        
        if completed_only.empty:
            st.caption("No completed deliveries yet.")
        else:
            display = completed_only.copy()
            display['delivery_date'] = display['delivery_date'].astype(str)
            display = display[['id', 'delivery_number', 'delivery_date', 'dispatch_number',
                              'customer_name', 'received_by_name', 'is_partial', 'status']]
            display.columns = ['ID', 'Delivery #', 'Date', 'Dispatch #', 'Customer',
                              'Received By', 'Partial?', 'Status']
            st.dataframe(display, use_container_width=True, hide_index=True)
            
            st.markdown("##### 📥 Download Delivery Note")
            dl_options = {
                f"{row['delivery_number']} — {row.get('customer_name') or 'N/A'}": row['id']
                for _, row in completed_only.iterrows()
            }
            dsel = st.selectbox("Select Completed Delivery", list(dl_options.keys()), key="dl_dl_sel")
            html = generate_delivery_note_html(dl_options[dsel])
            
            if html:
                st.download_button(
                    "📥 Download Delivery Note (HTML)",
                    html,
                    f"delivery_{dsel}.html",
                    "text/html",
                    use_container_width=True,
                )
                with st.expander("👁️ Preview"):
                    st.components.v1.html(html, height=700, scrolling=True)
    
    # ============================================
    # TAB 3: PERFORMANCE
    # ============================================
    with tab3:
        st.markdown("#### 📊 Delivery Performance")
        st.caption("Variance and partial-delivery statistics per customer")
        
        col1, col2 = st.columns(2)
        with col1:
            from_date = st.date_input("From", value=date.today() - timedelta(days=90), key="perf_from")
        with col2:
            to_date = st.date_input("To", value=date.today(), key="perf_to")
        
        perf = get_delivery_performance(from_date, to_date)
        
        if perf.empty:
            st.info("No completed deliveries in this period.")
        else:
            st.success(f"✅ {len(perf)} customer(s)")
            
            display = perf.copy()
            for c in ['total_dispatched', 'total_received', 'total_rejected']:
                display[c] = display[c].apply(lambda x: f"{float(x):,.2f}")
            
            display.columns = ['Customer', 'Deliveries', 'Partial', 
                              'Dispatched', 'Received', 'Rejected']
            st.dataframe(display, use_container_width=True, hide_index=True)
            
            csv = perf.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv,
                              f"delivery_performance_{datetime.now().strftime('%Y%m%d')}.csv",
                              "text/csv")
