# pages_payments.py
# Payments UI

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import read_sql
from services_payments import (
    record_customer_payment, record_supplier_payment, reverse_payment,
    get_payments, get_payment, get_payment_allocations,
    get_supplier_payment_allocations, get_customer_statement,
    get_ar_aging, generate_receipt_html,
    generate_payment_number, PAYMENT_METHODS, PAYMENT_TYPES,
)
from services_customers import get_customers
from services_suppliers import get_suppliers


def payments_page():
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important; }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>💳 Payments</h2>", unsafe_allow_html=True)
    st.caption("Customer receipts, supplier payments, statements, and aging")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "💵 Record Payment",
        "📋 Payment Register",
        "👥 Customer Statements",
        "⏰ AR Aging",
        "📤 Supplier Payments",
    ])
    
    # ============================================
    # TAB 1: RECORD PAYMENT
    # ============================================
    with tab1:
        st.markdown("#### 💵 Record Customer Receipt")
        st.info(f"💡 Next payment number: **{generate_payment_number()}**")
        
        customers = get_customers(active_only=True)
        if customers.empty:
            st.warning("No customers yet.")
        else:
            cust_opts = {f"{r['customer_code']} — {r['customer_name']}": r['id']
                         for _, r in customers.iterrows()}
            
            col1, col2, col3 = st.columns(3)
            with col1:
                cust_sel = st.selectbox("Customer *", list(cust_opts.keys()), key="pay_cust")
            with col2:
                pdate = st.date_input("Payment Date", value=date.today(), key="pay_date")
            with col3:
                method = st.selectbox("Method", PAYMENT_METHODS, key="pay_method")
            
            cust_id = cust_opts[cust_sel]
            
            # Show outstanding invoices
            open_inv = read_sql("""
                SELECT id, invoice_number, invoice_date, total_amount,
                       amount_paid, balance_due, status
                FROM invoices
                WHERE customer_id = :cid
                  AND status IN ('Unpaid', 'Partial')
                  AND balance_due > 0
                ORDER BY invoice_date ASC
            """, {"cid": cust_id})
            
            total_outstanding = 0
            if not open_inv.empty:
                total_outstanding = float(open_inv['balance_due'].sum())
                st.markdown(f"**Outstanding: KES {total_outstanding:,.2f}** across {len(open_inv)} invoice(s)")
                st.dataframe(open_inv[['invoice_number', 'invoice_date', 'balance_due', 'status']],
                            use_container_width=True, hide_index=True)
            
            col1, col2 = st.columns(2)
            with col1:
                amount = st.number_input("Amount (KES) *", min_value=0.0,
                                        value=float(total_outstanding) if total_outstanding > 0 else 0.0,
                                        step=100.0, format="%.2f", key="pay_amt")
            with col2:
                ref = st.text_input("Reference (e.g. M-Pesa code)", key="pay_ref")
            
            notes = st.text_area("Notes", height=60, key="pay_notes")
            
            alloc_mode = st.radio("Allocation",
                                 ["Auto-FIFO to oldest invoices", "Manual (none — credit)"],
                                 horizontal=True, key="pay_alloc_mode")
            
            if st.button("💾 Record Payment", type="primary", use_container_width=True, key="pay_save"):
                if amount <= 0:
                    st.error("Amount must be positive")
                else:
                    auto = (alloc_mode.startswith("Auto"))
                    ok, msg, _ = record_customer_payment(
                        customer_id=cust_id,
                        amount=amount,
                        payment_date=pdate,
                        payment_method=method,
                        reference_number=ref,
                        notes=notes,
                        auto_allocate=auto,
                    )
                    if ok:
                        st.success(msg)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)
        
        st.markdown("---")
        st.markdown("#### 🔄 Reverse a Payment")
        st.caption("Reversals create a new offsetting payment — nothing is deleted.")
        
        recent = get_payments(payment_type="Customer Receipt")
        if not recent.empty:
            rev_opts = {f"{r['payment_number']} — {r.get('customer_name') or '—'} (KES {float(r['amount']):,.2f})": r['id']
                        for _, r in recent[~recent['is_reversal'].astype(bool)].head(50).iterrows()}
            if rev_opts:
                rev_sel = st.selectbox("Payment to reverse", list(rev_opts.keys()), key="rev_sel")
                rev_reason = st.text_input("Reversal reason *", key="rev_reason")
                if st.button("🔄 Reverse Payment", use_container_width=True, key="rev_btn"):
                    if not rev_reason:
                        st.error("Reason required")
                    else:
                        ok, msg, _ = reverse_payment(rev_opts[rev_sel], rev_reason)
                        if ok:
                            st.success(msg); st.rerun()
                        else:
                            st.error(msg)
    
    # ============================================
    # TAB 2: PAYMENT REGISTER
    # ============================================
    with tab2:
        st.markdown("#### 📋 Payment Register")
        
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        with col1:
            search = st.text_input("🔍 Search", key="pay_search")
        with col2:
            ptype = st.selectbox("Type", ["All"] + PAYMENT_TYPES, key="pay_type_filter")
        with col3:
            fd = st.date_input("From", value=date.today() - timedelta(days=90), key="pay_fd")
        with col4:
            td = st.date_input("To", value=date.today(), key="pay_td")
        
        df = get_payments(payment_type=ptype, search=search or None,
                         from_date=fd, to_date=td)
        
        if df.empty:
            st.info("No payments match the filters.")
        else:
            st.success(f"✅ {len(df)} payment(s)")
            
            display = df.copy()
            display['payment_date'] = display['payment_date'].astype(str)
            display['amount'] = display['amount'].apply(lambda x: f"KES {float(x):,.2f}")
            display['unallocated_amount'] = display['unallocated_amount'].apply(lambda x: f"KES {float(x or 0):,.2f}")
            display['party'] = display.apply(
                lambda r: r['customer_name'] if r.get('customer_name') else (r.get('supplier_name') or '—'),
                axis=1,
            )
            display['rev'] = display['is_reversal'].apply(lambda x: "🔄" if x else "")
            display = display[['id', 'payment_number', 'payment_date', 'payment_type',
                              'party', 'payment_method', 'amount',
                              'unallocated_amount', 'rev']]
            display.columns = ['ID', 'Payment #', 'Date', 'Type', 'Party',
                              'Method', 'Amount', 'Unallocated', '']
            st.dataframe(display, use_container_width=True, hide_index=True, height=400)
            
            st.markdown("---")
            st.markdown("#### 🔍 Payment Details")
            sel = st.selectbox("Select Payment",
                              [f"{r['payment_number']} — {r.get('customer_name') or r.get('supplier_name') or '—'}"
                               for _, r in df.iterrows()],
                              key="pay_detail_sel")
            pid = df.iloc[[f"{r['payment_number']} — {r.get('customer_name') or r.get('supplier_name') or '—'}"
                          for _, r in df.iterrows()].index(sel)]['id']
            
            p = get_payment(pid)
            if p is not None:
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric("Payment #", p['payment_number'])
                with c2: st.metric("Amount", f"KES {float(p['amount']):,.2f}")
                with c3: st.metric("Allocated", f"KES {float(p['amount']) - float(p.get('unallocated_amount') or 0):,.2f}")
                with c4: st.metric("Unallocated", f"KES {float(p.get('unallocated_amount') or 0):,.2f}")
                
                allocs = get_payment_allocations(pid)
                if not allocs.empty:
                    st.markdown("##### Invoice Allocations")
                    st.dataframe(allocs[['invoice_number', 'invoice_date', 'amount', 'status']],
                                use_container_width=True, hide_index=True)
                
                sp_allocs = get_supplier_payment_allocations(pid)
                if not sp_allocs.empty:
                    st.markdown("##### PO Allocations")
                    st.dataframe(sp_allocs[['po_number', 'order_date', 'amount', 'status']],
                                use_container_width=True, hide_index=True)
                
                html = generate_receipt_html(pid)
                if html:
                    st.download_button(
                        "📥 Download Receipt (HTML)",
                        html,
                        f"receipt_{p['payment_number']}.html",
                        "text/html",
                        use_container_width=True,
                    )
                    with st.expander("👁️ Preview Receipt"):
                        st.components.v1.html(html, height=600, scrolling=True)
    
    # ============================================
    # TAB 3: CUSTOMER STATEMENTS
    # ============================================
    with tab3:
        st.markdown("#### 👥 Customer Statement (AR Ledger)")
        
        customers = get_customers(active_only=False)
        if customers.empty:
            st.info("No customers.")
        else:
            cust_opts = {f"{r['customer_code']} — {r['customer_name']}": r['id']
                         for _, r in customers.iterrows()}
            sel = st.selectbox("Customer", list(cust_opts.keys()), key="stmt_cust")
            cid = cust_opts[sel]
            
            col1, col2 = st.columns(2)
            with col1:
                fd = st.date_input("From", value=date.today() - timedelta(days=180), key="stmt_fd")
            with col2:
                td = st.date_input("To", value=date.today(), key="stmt_td")
            
            stmt = get_customer_statement(cid, fd, td)
            
            if stmt.empty:
                st.info("No transactions in this period.")
            else:
                st.success(f"✅ {len(stmt)} transaction(s)")
                
                display = stmt.copy()
                display['entry_date'] = display['entry_date'].astype(str)
                for c in ['debit', 'credit', 'running_balance']:
                    display[c] = display[c].apply(lambda x: f"KES {float(x):,.2f}")
                display = display[['entry_date', 'entry_type', 'reference',
                                  'debit', 'credit', 'running_balance', 'status']]
                display.columns = ['Date', 'Type', 'Reference', 'Debit',
                                  'Credit', 'Balance', 'Status']
                st.dataframe(display, use_container_width=True, hide_index=True)
                
                csv = stmt.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Statement CSV", csv,
                                  f"statement_{cid}_{datetime.now().strftime('%Y%m%d')}.csv",
                                  "text/csv")
    
    # ============================================
    # TAB 4: AR AGING
    # ============================================
    with tab4:
        st.markdown("#### ⏰ Accounts Receivable Aging")
        
        asof = st.date_input("As of", value=date.today(), key="aging_date")
        
        aging = get_ar_aging(as_of_date=asof)
        
        if aging.empty:
            st.success("✅ No outstanding receivables.")
        else:
            st.warning(f"⚠️ {len(aging)} customer(s) with outstanding balances")
            
            display = aging.copy()
            for c in ['bucket_0_30', 'bucket_31_60', 'bucket_61_90',
                     'bucket_90_plus', 'total_outstanding']:
                display[c] = display[c].apply(lambda x: f"KES {float(x or 0):,.2f}")
            display = display[['customer_code', 'customer_name', 'open_invoices',
                              'bucket_0_30', 'bucket_31_60', 'bucket_61_90',
                              'bucket_90_plus', 'total_outstanding']]
            display.columns = ['Code', 'Customer', 'Invoices',
                              '0-30', '31-60', '61-90', '90+', 'Total']
            st.dataframe(display, use_container_width=True, hide_index=True)
            
            total = aging['total_outstanding'].sum()
            st.metric("Total Outstanding", f"KES {float(total):,.2f}")
            
            csv = aging.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Aging CSV", csv,
                              f"ar_aging_{asof.strftime('%Y%m%d')}.csv",
                              "text/csv")
    
    # ============================================
    # TAB 5: SUPPLIER PAYMENTS
    # ============================================
    with tab5:
        st.markdown("#### 📤 Record Supplier Payment")
        
        suppliers = get_suppliers(active_only=True)
        if suppliers.empty:
            st.warning("No suppliers yet.")
        else:
            sup_opts = {f"{r['supplier_code']} — {r['supplier_name']}": r['id']
                        for _, r in suppliers.iterrows()}
            
            col1, col2, col3 = st.columns(3)
            with col1:
                sup_sel = st.selectbox("Supplier *", list(sup_opts.keys()), key="spay_sup")
            with col2:
                pdate = st.date_input("Payment Date", value=date.today(), key="spay_date")
            with col3:
                method = st.selectbox("Method", PAYMENT_METHODS, index=2, key="spay_method")
            
            sup_id = sup_opts[sup_sel]
            
            open_pos = read_sql("""
                SELECT id, po_number, order_date, total_amount, status
                FROM purchase_orders
                WHERE supplier_id = :sid
                  AND status IN ('Approved', 'Partially Received', 'Fully Received')
                ORDER BY order_date ASC
            """, {"sid": sup_id})
            
            total_open = 0
            if not open_pos.empty:
                total_open = float(open_pos['total_amount'].sum())
                st.markdown(f"**Open POs: KES {total_open:,.2f}** across {len(open_pos)} PO(s)")
                st.dataframe(open_pos[['po_number', 'order_date', 'total_amount', 'status']],
                            use_container_width=True, hide_index=True)
            
            col1, col2 = st.columns(2)
            with col1:
                amount = st.number_input("Amount (KES) *", min_value=0.0,
                                        value=float(total_open) if total_open > 0 else 0.0,
                                        step=100.0, format="%.2f", key="spay_amt")
            with col2:
                ref = st.text_input("Reference", key="spay_ref")
            
            notes = st.text_area("Notes", height=60, key="spay_notes")
            
            alloc_mode = st.radio("Allocation",
                                 ["Auto-FIFO to oldest POs", "None (unallocated)"],
                                 horizontal=True, key="spay_alloc_mode")
            
            if st.button("💾 Record Supplier Payment", type="primary",
                         use_container_width=True, key="spay_save"):
                if amount <= 0:
                    st.error("Amount must be positive")
                else:
                    auto = alloc_mode.startswith("Auto")
                    ok, msg, _ = record_supplier_payment(
                        supplier_id=sup_id,
                        amount=amount,
                        payment_date=pdate,
                        payment_method=method,
                        reference_number=ref,
                        notes=notes,
                        auto_allocate=auto,
                    )
                    if ok:
                        st.success(msg)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)
