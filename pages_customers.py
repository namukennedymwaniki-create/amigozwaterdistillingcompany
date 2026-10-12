# pages_customers.py
# Customer Register UI

import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import text
from database import get_db_connection, read_sql
from services_customers import (
    create_customer, update_customer, get_customers, get_customer,
    generate_customer_code, CUSTOMER_TYPES
)


def customers_page():
    """Customer Register — 3 tabs"""
    
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important;
        }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>👥 Customer Register</h2>", unsafe_allow_html=True)
    st.caption("Manage all customers — retail, wholesale, distributors, and institutions")
    
    tab1, tab2, tab3 = st.tabs(["📋 View Customers", "➕ Add Customer", "✏️ Edit Customer"])
    
    # ============================================
    # TAB 1: VIEW
    # ============================================
    with tab1:
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            search = st.text_input("🔍 Search by name or code", key="cust_search")
        with col2:
            type_filter = st.selectbox("Type", ["All"] + CUSTOMER_TYPES, key="cust_type_filter")
        with col3:
            st.write("")
            st.write("")
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        
        df = get_customers(search=search or None, customer_type=type_filter)
        
        if df.empty:
            st.info("📭 No customers yet. Use '➕ Add Customer' tab.")
        else:
            st.success(f"✅ {len(df)} customer(s)")
            
            display = df[['id', 'customer_code', 'customer_name', 'customer_type',
                          'contact_person', 'phone', 'town', 'credit_limit', 'is_active']].copy()
            display['credit_limit'] = display['credit_limit'].apply(
                lambda x: f"KES {float(x):,.2f}" if x else "KES 0.00"
            )
            display['is_active'] = display['is_active'].apply(lambda x: "✅" if x else "❌")
            display.columns = ['ID', 'Code', 'Name', 'Type', 'Contact', 'Phone',
                              'Town', 'Credit Limit', 'Active']
            
            st.dataframe(display, use_container_width=True, hide_index=True, height=400)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv,
                              f"customers_{datetime.now().strftime('%Y%m%d')}.csv",
                              "text/csv")
    
    # ============================================
    # TAB 2: ADD
    # ============================================
    with tab2:
        st.markdown("#### ➕ Add New Customer")
        st.info(f"💡 Next customer code: **{generate_customer_code()}**")
        
        with st.form("add_customer_form"):
            col1, col2 = st.columns(2)
            with col1:
                customer_name = st.text_input("Customer Name *", placeholder="e.g., Acme Distributors Ltd")
                customer_type = st.selectbox("Customer Type", CUSTOMER_TYPES, index=0)
                contact_person = st.text_input("Contact Person", placeholder="Full name")
                phone = st.text_input("Phone", placeholder="+254...")
                email = st.text_input("Email", placeholder="email@example.com")
            with col2:
                address = st.text_input("Address", placeholder="Physical address")
                town = st.text_input("Town", placeholder="e.g., Embu")
                credit_limit = st.number_input("Credit Limit (KES)", min_value=0.0,
                                               value=0.0, step=1000.0, format="%.2f")
                payment_terms = st.selectbox("Payment Terms",
                    ["Cash", "7 days", "14 days", "30 days", "60 days", "90 days"],
                    index=3)
                tax_pin = st.text_input("Tax PIN", placeholder="e.g., P051234567X")
            
            notes = st.text_area("Notes", height=80)
            
            submitted = st.form_submit_button("💾 Save Customer", type="primary", use_container_width=True)
            
            if submitted:
                if not customer_name:
                    st.error("❌ Customer name required")
                else:
                    ok, msg, _ = create_customer(
                        customer_name=customer_name,
                        customer_type=customer_type,
                        contact_person=contact_person,
                        phone=phone,
                        email=email,
                        address=address,
                        town=town,
                        credit_limit=credit_limit,
                        payment_terms=payment_terms,
                        tax_pin=tax_pin,
                        notes=notes,
                    )
                    if ok:
                        st.success(msg)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)
    
    # ============================================
    # TAB 3: EDIT
    # ============================================
    with tab3:
        st.markdown("#### ✏️ Edit Customer")
        
        df = get_customers(active_only=False)
        
        if df.empty:
            st.info("No customers to edit.")
        else:
            options = {f"{row['customer_code']} — {row['customer_name']}": row['id']
                       for _, row in df.iterrows()}
            
            selected = st.selectbox("Select Customer", list(options.keys()), key="edit_cust_sel")
            cid = options[selected]
            customer = get_customer(cid)
            
            if customer is not None:
                with st.form("edit_customer_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text_input("Customer Code", value=customer['customer_code'], disabled=True)
                        name = st.text_input("Customer Name *", value=customer['customer_name'])
                        ctype = st.selectbox("Customer Type", CUSTOMER_TYPES,
                                            index=CUSTOMER_TYPES.index(customer['customer_type'])
                                            if customer['customer_type'] in CUSTOMER_TYPES else 0)
                        contact = st.text_input("Contact Person", value=customer['contact_person'] or "")
                        phone = st.text_input("Phone", value=customer['phone'] or "")
                        email = st.text_input("Email", value=customer['email'] or "")
                    with col2:
                        address = st.text_input("Address", value=customer['address'] or "")
                        town = st.text_input("Town", value=customer['town'] or "")
                        credit = st.number_input("Credit Limit (KES)", min_value=0.0,
                                                value=float(customer['credit_limit'] or 0),
                                                step=1000.0, format="%.2f")
                        terms_opts = ["Cash", "7 days", "14 days", "30 days", "60 days", "90 days"]
                        terms = st.selectbox("Payment Terms", terms_opts,
                                            index=terms_opts.index(customer['payment_terms'])
                                            if customer['payment_terms'] in terms_opts else 3)
                        tax_pin = st.text_input("Tax PIN", value=customer['tax_pin'] or "")
                    
                    notes = st.text_area("Notes", value=customer['notes'] or "", height=80)
                    is_active = st.checkbox("Active", value=bool(customer['is_active']))
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        save = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
                    with col_b:
                        deactivate = st.form_submit_button("🗑️ Deactivate", use_container_width=True)
                    
                    if save:
                        ok, msg = update_customer(
                            cid,
                            customer_name=name,
                            customer_type=ctype,
                            contact_person=contact,
                            phone=phone,
                            email=email,
                            address=address,
                            town=town,
                            credit_limit=credit,
                            payment_terms=terms,
                            tax_pin=tax_pin,
                            is_active=1 if is_active else 0,
                            notes=notes,
                        )
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    
                    if deactivate:
                        ok, msg = update_customer(cid, is_active=0)
                        if ok:
                            st.success("✅ Customer deactivated")
                            st.rerun()
                        else:
                            st.error(msg)
