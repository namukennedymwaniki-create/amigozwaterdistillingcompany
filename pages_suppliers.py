# pages_suppliers.py
# Supplier Register UI

import streamlit as st
import pandas as pd
from datetime import datetime
from services_suppliers import (
    create_supplier, update_supplier, get_suppliers, get_supplier,
    generate_supplier_code, SUPPLIER_TYPES
)


def suppliers_page():
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important; }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>🏭 Supplier Register</h2>", unsafe_allow_html=True)
    st.caption("Manage suppliers of raw materials, packaging, equipment and services")
    
    tab1, tab2, tab3 = st.tabs(["📋 View Suppliers", "➕ Add Supplier", "✏️ Edit Supplier"])
    
    # ---- VIEW ----
    with tab1:
        col1, col2 = st.columns([3, 1])
        with col1:
            search = st.text_input("🔍 Search by name or code", key="sup_search")
        with col2:
            st.write("")
            st.write("")
            if st.button("🔄 Refresh", use_container_width=True, key="sup_ref"):
                st.rerun()
        
        df = get_suppliers(search=search or None)
        
        if df.empty:
            st.info("📭 No suppliers yet. Use '➕ Add Supplier' tab.")
        else:
            st.success(f"✅ {len(df)} supplier(s)")
            display = df[['id', 'supplier_code', 'supplier_name', 'contact_person',
                          'phone', 'town', 'payment_terms', 'is_active']].copy()
            display['is_active'] = display['is_active'].apply(lambda x: "✅" if x else "❌")
            display.columns = ['ID', 'Code', 'Name', 'Contact', 'Phone',
                              'Town', 'Terms', 'Active']
            st.dataframe(display, use_container_width=True, hide_index=True, height=400)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv,
                              f"suppliers_{datetime.now().strftime('%Y%m%d')}.csv",
                              "text/csv")
    
    # ---- ADD ----
    with tab2:
        st.markdown("#### ➕ Add New Supplier")
        st.info(f"💡 Next code: **{generate_supplier_code()}**")
        
        with st.form("add_supplier_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Supplier Name *")
                contact = st.text_input("Contact Person")
                phone = st.text_input("Phone", placeholder="+254...")
                email = st.text_input("Email")
            with col2:
                address = st.text_input("Address")
                town = st.text_input("Town")
                terms_opts = ["Cash", "7 days", "14 days", "30 days", "60 days", "90 days"]
                terms = st.selectbox("Payment Terms", terms_opts, index=3)
                tax_pin = st.text_input("Tax PIN")
            notes = st.text_area("Notes", height=80)
            
            if st.form_submit_button("💾 Save Supplier", type="primary", use_container_width=True):
                if not name:
                    st.error("❌ Supplier name required")
                else:
                    ok, msg, _ = create_supplier(name, contact, phone, email,
                                                 address, town, terms, tax_pin, notes)
                    if ok:
                        st.success(msg)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)
    
    # ---- EDIT ----
    with tab3:
        st.markdown("#### ✏️ Edit Supplier")
        
        df = get_suppliers(active_only=False)
        if df.empty:
            st.info("No suppliers to edit.")
            return
        
        options = {f"{row['supplier_code']} — {row['supplier_name']}": row['id']
                   for _, row in df.iterrows()}
        sel = st.selectbox("Select Supplier", list(options.keys()), key="sup_edit_sel")
        s = get_supplier(options[sel])
        
        if s is not None:
            with st.form("edit_supplier_form"):
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Code", value=s['supplier_code'], disabled=True)
                    name = st.text_input("Supplier Name *", value=s['supplier_name'])
                    contact = st.text_input("Contact Person", value=s['contact_person'] or "")
                    phone = st.text_input("Phone", value=s['phone'] or "")
                    email = st.text_input("Email", value=s['email'] or "")
                with col2:
                    address = st.text_input("Address", value=s['address'] or "")
                    town = st.text_input("Town", value=s['town'] or "")
                    terms_opts = ["Cash", "7 days", "14 days", "30 days", "60 days", "90 days"]
                    terms = st.selectbox("Payment Terms", terms_opts,
                                        index=terms_opts.index(s['payment_terms'])
                                        if s['payment_terms'] in terms_opts else 3)
                    tax_pin = st.text_input("Tax PIN", value=s['tax_pin'] or "")
                notes = st.text_area("Notes", value=s['notes'] or "", height=80)
                is_active = st.checkbox("Active", value=bool(s['is_active']))
                
                col_a, col_b = st.columns(2)
                with col_a:
                    save = st.form_submit_button("💾 Save Changes", type="primary",
                                                 use_container_width=True)
                with col_b:
                    deact = st.form_submit_button("🗑️ Deactivate", use_container_width=True)
                
                if save:
                    ok, msg = update_supplier(
                        s['id'],
                        supplier_name=name, contact_person=contact, phone=phone,
                        email=email, address=address, town=town,
                        payment_terms=terms, tax_pin=tax_pin,
                        is_active=1 if is_active else 0, notes=notes,
                    )
                    if ok:
                        st.success(msg); st.rerun()
                    else:
                        st.error(msg)
                
                if deact:
                    ok, msg = update_supplier(s['id'], is_active=0)
                    if ok:
                        st.success("✅ Supplier deactivated"); st.rerun()
                    else:
                        st.error(msg)
