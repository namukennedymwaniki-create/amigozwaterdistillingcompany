# pages_containers.py
# Returnable Containers UI — Stage 06

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import read_sql
from services_containers import (
    issue_containers, return_containers, mark_refund_paid,
    auto_issue_for_order,
    get_containers, get_issues, get_issue, get_issue_items,
    get_returns, get_return, get_return_items,
    get_customer_container_balance, get_overdue_issues, get_company_balance,
    generate_issue_number, generate_return_number,
)
from services_customers import get_customers
from services_sales import get_sales_orders


def containers_page():
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important; }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>🍶 Returnable Containers</h2>", unsafe_allow_html=True)
    st.caption("Issue containers, collect returns, track deposits, and monitor losses")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Issue Containers",
        "📥 Return / Collect",
        "👥 Customer Balances",
        "📊 Company Report",
    ])
    
    # ---- 1. ISSUE ----
    with tab1:
        st.markdown("#### 📤 Issue Containers to a Customer")
        st.info(f"💡 Next issue: **{generate_issue_number()}**")
        
        customers = get_customers(active_only=True)
        containers = get_containers(active_only=True)
        
        if customers.empty or containers.empty:
            st.warning("Need at least one customer and one container.")
        else:
            cust_opts = {f"{r['customer_code']} — {r['customer_name']}": r['id']
                         for _, r in customers.iterrows()}
            cont_opts = {f"{r['container_code']} — {r['container_name']} "
                         f"(deposit KES {float(r['deposit_amount']):,.2f})": r['id']
                         for _, r in containers.iterrows()}
            
            col1, col2, col3 = st.columns(3)
            with col1:
                cust_sel = st.selectbox("Customer *", list(cust_opts.keys()), key="ci_cust")
                issue_date = st.date_input("Issue Date", value=date.today(), key="ci_date")
            with col2:
                due_date = st.date_input("Due Date (return by)",
                                        value=date.today() + timedelta(days=30),
                                        key="ci_due")
                order_df = get_sales_orders()
                order_opts = {"— None —": None}
                order_opts.update({f"{r['order_number']}": r['id']
                                   for _, r in order_df.iterrows()})
                order_sel = st.selectbox("Link to Order (optional)",
                                        list(order_opts.keys()), key="ci_order")
            with col3:
                notes = st.text_area("Notes", height=60, key="ci_notes")
            
            if 'ci_items' not in st.session_state:
                st.session_state.ci_items = []
            
            with st.expander("➕ Add Container Line", expanded=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    cont_sel = st.selectbox("Container", list(cont_opts.keys()),
                                            key="ci_line_cont")
                with c2:
                    qty = st.number_input("Qty", min_value=0.01, value=1.0, step=1.0,
                                         key="ci_line_qty")
                with c3:
                    st.write(""); st.write("")
                    if st.button("➕ Add", use_container_width=True, key="ci_add_btn"):
                        st.session_state.ci_items.append({
                            'container_id': cont_opts[cont_sel],
                            'container_label': cont_sel,
                            'quantity': qty,
                        })
                        st.rerun()
            
            if st.session_state.ci_items:
                st.markdown("#### 🛒 Current Lines")
                st.dataframe(pd.DataFrame(st.session_state.ci_items)[
                    ['container_label', 'quantity']
                ], use_container_width=True, hide_index=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🗑️ Clear", use_container_width=True, key="ci_clear"):
                        st.session_state.ci_items = []
                        st.rerun()
                with c2:
                    if st.button("💾 Issue Containers", type="primary",
                                 use_container_width=True, key="ci_issue"):
                        ok, msg, _ = issue_containers(
                            customer_id=cust_opts[cust_sel],
                            issue_date=issue_date,
                            due_date=due_date,
                            order_id=order_opts[order_sel],
                            notes=notes,
                            items=st.session_state.ci_items,
                        )
                        if ok:
                            st.success(msg)
                            st.session_state.ci_items = []
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(msg)
        
        st.markdown("---")
        st.markdown("#### 📋 Issues Register")
        issues = get_issues()
        if issues.empty:
            st.caption("No issues yet.")
        else:
            display = issues.copy()
            display['issue_date'] = display['issue_date'].astype(str)
            display['due_date'] = display['due_date'].astype(str)
            for c in ['total_deposit', 'refunded_amount', 'forfeited_amount']:
                display[c] = display[c].apply(lambda x: f"KES {float(x):,.2f}")
            display = display[['id', 'issue_number', 'issue_date', 'due_date',
                              'customer_name', 'order_number', 'items_count',
                              'total_deposit', 'status']]
            display.columns = ['ID', 'Issue #', 'Issued', 'Due', 'Customer',
                              'Order', 'Lines', 'Deposit', 'Status']
            st.dataframe(display, use_container_width=True, hide_index=True)
    
    # ---- 2. RETURN ----
    with tab2:
        st.markdown("#### 📥 Collect Containers")
        st.info(f"💡 Next return: **{generate_return_number()}**")
        
        open_issues = get_issues()
        open_issues = open_issues[open_issues['status'].isin(
            ['Issued', 'Partially Returned'])].reset_index(drop=True) if not open_issues.empty else open_issues
        
        if open_issues.empty:
            st.info("No open issues to return against.")
        else:
            sel = st.selectbox(
                "Select Issue",
                [f"{r['issue_number']} — {r['customer_name']} ({r['status']})"
                 for _, r in open_issues.iterrows()],
                key="cr_issue_sel",
            )
            issue_id = open_issues.iloc[[f"{r['issue_number']} — {r['customer_name']} ({r['status']})"
                                        for _, r in open_issues.iterrows()].index(sel)]['id']
            
            issue = get_issue(issue_id)
            items = get_issue_items(issue_id)
            
            if issue is not None and not items.empty:
                c1, c2, c3 = st.columns(3)
                with c1: st.metric("Issue #", issue['issue_number'])
                with c2: st.metric("Customer", issue['customer_name'])
                with c3: st.metric("Deposit Held", f"KES {float(issue['total_deposit']):,.2f}")
                
                st.markdown("#### 📦 Lines to Return")
                
                return_lines = []
                for _, it in items.iterrows():
                    outstanding = float(it['outstanding'] or 0)
                    if outstanding <= 0:
                        continue
                    
                    with st.expander(
                        f"{it['container_code']} — {it['container_name']} "
                        f"(Outstanding: {outstanding:,.2f}, "
                        f"Deposit/unit: KES {float(it['deposit_per_unit']):,.2f})"
                    ):
                        c1, c2, c3 = st.columns([1, 1, 2])
                        with c1:
                            qret = st.number_input(
                                "Returned",
                                min_value=0.0, max_value=outstanding,
                                value=outstanding, step=1.0,
                                key=f"cr_ret_{it['id']}",
                            )
                        with c2:
                            qlost = st.number_input(
                                "Lost/Broken",
                                min_value=0.0, max_value=outstanding,
                                value=0.0, step=1.0,
                                key=f"cr_lost_{it['id']}",
                            )
                        with c3:
                            reason = st.text_input("Loss reason",
                                                  key=f"cr_reason_{it['id']}")
                        
                        if qret + qlost > 0:
                            return_lines.append({
                                'issue_item_id': it['id'],
                                'container_id': it['container_id'],
                                'quantity_returned': qret,
                                'quantity_lost': qlost,
                                'loss_reason': reason or None,
                            })
                
                c1, c2 = st.columns(2)
                with c1:
                    rdate = st.date_input("Return Date", value=date.today(), key="cr_date")
                with c2:
                    notes = st.text_input("Notes", key="cr_notes")
                
                if st.button("💾 Post Return", type="primary",
                             use_container_width=True, key="cr_post"):
                    if not return_lines:
                        st.error("Enter at least one return qty")
                    else:
                        ok, msg, _ = return_containers(
                            issue_id, rdate, notes, return_lines
                        )
                        if ok:
                            st.success(msg)
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(msg)
        
        st.markdown("---")
        st.markdown("#### 📋 Returns Register")
        returns = get_returns()
        if returns.empty:
            st.caption("No returns yet.")
        else:
            display = returns.copy()
            display['return_date'] = display['return_date'].astype(str)
            display['refund_amount'] = display['refund_amount'].apply(lambda x: f"KES {float(x):,.2f}")
            display = display[['id', 'return_number', 'return_date', 'issue_number',
                              'customer_name', 'items_count', 'refund_amount', 'refund_status']]
            display.columns = ['ID', 'Return #', 'Date', 'Issue #', 'Customer',
                              'Lines', 'Refund', 'Refund Status']
            st.dataframe(display, use_container_width=True, hide_index=True)
            
            st.markdown("##### 💰 Mark Refund Paid")
            pending = returns[returns['refund_status'] == 'Pending'].reset_index(drop=True)
            if pending.empty:
                st.caption("No pending refunds.")
            else:
                sel = st.selectbox(
                    "Pending Refund",
                    [f"{r['return_number']} — {r['customer_name']} (KES {float(r['refund_amount']):,.2f})"
                     for _, r in pending.iterrows()],
                    key="cr_refund_sel",
                )
                rid = pending.iloc[[f"{r['return_number']} — {r['customer_name']} (KES {float(r['refund_amount']):,.2f})"
                                   for _, r in pending.iterrows()].index(sel)]['id']
                
                n = st.text_input("Refund notes", key="cr_refund_notes")
                if st.button("✅ Mark Refund Paid", type="primary", key="cr_refund_btn"):
                    ok, msg = mark_refund_paid(rid, n)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
    
    # ---- 3. CUSTOMER BALANCES ----
    with tab3:
        st.markdown("#### 👥 Outstanding Containers by Customer")
        
        cust_df = get_customers(active_only=False)
        cust_opts = {"All Customers": None}
        cust_opts.update({f"{r['customer_code']} — {r['customer_name']}": r['id']
                          for _, r in cust_df.iterrows()})
        sel = st.selectbox("Customer", list(cust_opts.keys()), key="bal_cust")
        
        bal = get_customer_container_balance(customer_id=cust_opts[sel])
        
        if bal.empty:
            st.success("✅ No outstanding containers.")
        else:
            display = bal.copy()
            display['outstanding_deposit'] = display['outstanding_deposit'].apply(
                lambda x: f"KES {float(x):,.2f}"
            )
            display = display[['customer_code', 'customer_name',
                              'container_code', 'container_name',
                              'outstanding_qty', 'outstanding_deposit']]
            display.columns = ['Code', 'Customer', 'Container Code', 'Container',
                              'Outstanding Qty', 'Deposit Held']
            st.dataframe(display, use_container_width=True, hide_index=True)
            
            total_qty = bal['outstanding_qty'].sum()
            total_dep = bal['outstanding_deposit'].sum()
            c1, c2 = st.columns(2)
            with c1: st.metric("Total Outstanding", f"{total_qty:,.2f}")
            with c2: st.metric("Total Deposits Held", f"KES {float(total_dep):,.2f}")
        
        st.markdown("---")
        st.markdown("#### ⏰ Overdue Containers")
        over = get_overdue_issues()
        if over.empty:
            st.success("✅ No overdue containers.")
        else:
            st.warning(f"⚠️ {len(over)} issue(s) overdue")
            display = over.copy()
            display['issue_date'] = display['issue_date'].astype(str)
            display['due_date'] = display['due_date'].astype(str)
            display = display[['id', 'issue_number', 'issue_date', 'due_date',
                              'days_overdue', 'customer_name', 'status']]
            display.columns = ['ID', 'Issue #', 'Issued', 'Due',
                              'Days Overdue', 'Customer', 'Status']
            st.dataframe(display, use_container_width=True, hide_index=True)
    
    # ---- 4. COMPANY REPORT ----
    with tab4:
        st.markdown("#### 📊 Company-wide Container Position")
        
        comp = get_company_balance()
        if comp.empty:
            st.info("No container activity yet.")
        else:
            display = comp.copy()
            display['deposits_held'] = display['deposits_held'].apply(
                lambda x: f"KES {float(x):,.2f}"
            )
            st.dataframe(display, use_container_width=True, hide_index=True)
            
            csv = comp.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv,
                              f"container_position_{datetime.now().strftime('%Y%m%d')}.csv",
                              "text/csv")
