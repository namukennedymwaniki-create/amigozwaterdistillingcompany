# pages_sales.py
# Sales Orders UI — with full invoice generation flow

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import get_db_connection, read_sql
from services_customers import get_customers
from services_sales import (
    create_sales_order, get_sales_orders, get_order, get_order_items,
    confirm_order, cancel_order, generate_order_number, ORDER_STATUSES
)
from services_quality import get_available_stock
from services_invoices import (
    create_invoice_from_order, get_invoices, get_invoice,
    get_invoice_items, generate_invoice_html,
)


def sales_page():
    """Sales Orders — 4 tabs"""

    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important;
        }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h2 style='color: #0c4a6e;'>💰 Sales Management</h2>", unsafe_allow_html=True)
    st.caption("Create orders, validate stock, reserve items, and generate invoices")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Orders List",
        "➕ Create Order",
        "🔍 Order Details",
        "🧾 Invoices",
    ])

    # ============================================
    # TAB 1: ORDERS LIST
    # ============================================
    with tab1:
        st.markdown("#### 📋 Sales Orders")

        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            search = st.text_input("🔍 Search by order # or customer",
                                   key="so_search")
        with col2:
            status_filter = st.selectbox("Status", ["All"] + ORDER_STATUSES,
                                        key="so_status")
        with col3:
            st.write("")
            st.write("")
            if st.button("🔄 Refresh", use_container_width=True,
                        key="so_refresh"):
                st.rerun()

        df = get_sales_orders(status_filter=status_filter,
                              search=search or None)

        if df.empty:
            st.info("📭 No orders yet. Use '➕ Create Order' tab.")
        else:
            st.success(f"✅ {len(df)} order(s)")

            display = df.copy()
            display['total_amount'] = display['total_amount'].apply(
                lambda x: f"KES {float(x):,.2f}" if x else "KES 0.00"
            )
            display['order_date'] = display['order_date'].astype(str)
            display = display[['id', 'order_number', 'order_date',
                              'customer_name', 'items_count',
                              'total_amount', 'status']]
            display.columns = ['ID', 'Order #', 'Date', 'Customer',
                              'Items', 'Total', 'Status']

            st.dataframe(display, use_container_width=True,
                        hide_index=True, height=400)

    # ============================================
    # TAB 2: CREATE ORDER
    # ============================================
    with tab2:
        st.markdown("#### ➕ Create Sales Order")
        st.info(f"💡 Next order number: **{generate_order_number()}**")

        customers_df = get_customers(active_only=True)
        products_df = read_sql("""
            SELECT id, product_code, product_name, unit, selling_price
            FROM products WHERE is_active = TRUE ORDER BY product_name
        """)

        if customers_df.empty:
            st.warning("⚠️ No customers yet. Add customers first.")
        elif products_df.empty:
            st.warning("⚠️ No products yet.")
        else:
            cust_options = {
                f"{row['customer_code']} — {row['customer_name']}": row['id']
                for _, row in customers_df.iterrows()
            }

            col1, col2 = st.columns(2)
            with col1:
                customer_sel = st.selectbox("Customer *",
                                           list(cust_options.keys()),
                                           key="new_so_cust")
                order_date = st.date_input("Order Date",
                                          value=date.today(),
                                          key="new_so_date")
            with col2:
                delivery_date = st.date_input(
                    "Expected Delivery",
                    value=date.today() + timedelta(days=3),
                    key="new_so_del"
                )
                vat_enabled = st.checkbox("Enable VAT (16%)",
                                         value=False, key="new_so_vat")

            notes = st.text_area("Order Notes", height=60,
                                key="new_so_notes")

            st.markdown("---")
            st.markdown("#### 📦 Line Items")
            st.caption("Add products to this order")

            if 'new_so_items' not in st.session_state:
                st.session_state.new_so_items = []

            with st.expander("➕ Add Line Item", expanded=True):
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                with col1:
                    prod_options = {
                        f"{row['product_code']} — {row['product_name']}": row['id']
                        for _, row in products_df.iterrows()
                    }
                    prod_sel = st.selectbox("Product",
                                           list(prod_options.keys()),
                                           key="item_prod_sel")
                with col2:
                    item_qty = st.number_input("Qty", min_value=0.01,
                                              value=1.0, step=1.0,
                                              key="item_qty")
                with col3:
                    prod_row = products_df[
                        products_df['id'] == prod_options[prod_sel]
                    ].iloc[0]
                    default_price = float(prod_row['selling_price'] or 0)
                    item_price = st.number_input("Unit Price",
                                                min_value=0.0,
                                                value=default_price,
                                                step=0.50, format="%.2f",
                                                key="item_price")
                with col4:
                    st.write("")
                    st.write("")
                    if st.button("➕ Add", use_container_width=True,
                                key="item_add_btn"):
                        avail = get_available_stock(prod_options[prod_sel])
                        st.session_state.new_so_items.append({
                            'product_id': prod_options[prod_sel],
                            'product_name': prod_row['product_name'],
                            'product_code': prod_row['product_code'],
                            'unit': prod_row['unit'],
                            'quantity': item_qty,
                            'unit_price': item_price,
                            'line_total': item_qty * item_price,
                            'available': avail,
                        })
                        st.rerun()

            if st.session_state.new_so_items:
                st.markdown("#### 🛒 Current Items")
                items_df = pd.DataFrame(st.session_state.new_so_items)
                st.dataframe(
                    items_df[['product_code', 'product_name', 'quantity',
                             'unit_price', 'line_total', 'available']],
                    use_container_width=True, hide_index=True
                )

                subtotal = sum(it['line_total']
                              for it in st.session_state.new_so_items)
                tax = subtotal * 0.16 if vat_enabled else 0
                total = subtotal + tax

                col1, col2, col3 = st.columns(3)
                with col1: st.metric("Subtotal", f"KES {subtotal:,.2f}")
                with col2: st.metric("VAT (16%)", f"KES {tax:,.2f}")
                with col3: st.metric("Total", f"KES {total:,.2f}")

                if st.button("🗑️ Clear All Items", key="clear_items"):
                    st.session_state.new_so_items = []
                    st.rerun()

                st.markdown("---")

                if st.button("💾 Create Order (Draft)", type="primary",
                            use_container_width=True, key="create_so_btn"):
                    ok, msg, order_id = create_sales_order(
                        customer_id=cust_options[customer_sel],
                        order_date=order_date,
                        delivery_date=delivery_date,
                        vat_enabled=vat_enabled,
                        tax_rate=16,
                        notes=notes,
                        items=st.session_state.new_so_items,
                    )
                    if ok:
                        st.success(msg)
                        st.session_state.new_so_items = []
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)

    # ============================================
    # TAB 3: ORDER DETAILS
    # ============================================
    with tab3:
        st.markdown("#### 🔍 Order Details")

        orders_df = get_sales_orders()

        if orders_df.empty:
            st.info("No orders yet.")
        else:
            options = {
                f"{row['order_number']} — {row['customer_name']} ({row['status']})": row['id']
                for _, row in orders_df.iterrows()
            }

            selected = st.selectbox("Select Order", list(options.keys()),
                                   key="order_detail_sel")
            order_id = options[selected]

            order = get_order(order_id)
            items = get_order_items(order_id)

            if order is not None:
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric("Order #", order['order_number'])
                with col2: st.metric("Customer", order['customer_name'])
                with col3: st.metric("Status", order['status'])
                with col4: st.metric("Total",
                                    f"KES {float(order['total_amount']):,.2f}")

                st.markdown("#### 📦 Items")
                if not items.empty:
                    display = items.copy()
                    display['unit_price'] = display['unit_price'].apply(
                        lambda x: f"KES {float(x):,.2f}"
                    )
                    display['line_total'] = display['line_total'].apply(
                        lambda x: f"KES {float(x):,.2f}"
                    )
                    display = display[['product_code', 'product_name',
                                      'quantity_ordered', 'unit_price',
                                      'line_total']]
                    display.columns = ['Code', 'Product', 'Qty Ordered',
                                      'Unit Price', 'Line Total']
                    st.dataframe(display, use_container_width=True,
                                hide_index=True)

                # ============================================
                # ACTIONS
                # ============================================
                st.markdown("---")
                st.markdown("#### ⚙️ Actions")

                col_a, col_b, col_c = st.columns(3)

                # ---- Confirm ----
                with col_a:
                    if order['status'] == 'Draft':
                        if st.button("✅ Confirm Order", type="primary",
                                     use_container_width=True,
                                     key="confirm_btn"):
                            ok, msg = confirm_order(order_id)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    else:
                        st.button("✅ Confirm Order", disabled=True,
                                 use_container_width=True,
                                 key="confirm_disabled")

                # ---- Cancel ----
                with col_b:
                    if order['status'] in ['Draft', 'Confirmed']:
                        if st.button("❌ Cancel Order",
                                     use_container_width=True,
                                     key="cancel_btn"):
                            st.session_state.cancelling_order = order_id
                            st.rerun()
                    else:
                        st.button("❌ Cancel Order", disabled=True,
                                 use_container_width=True,
                                 key="cancel_disabled")

                # ---- Generate Invoice ----
                with col_c:
                    if order['status'] in ['Confirmed', 'Dispatched']:
                        if st.button("🧾 Generate Invoice", type="primary",
                                     use_container_width=True,
                                     key="invoice_btn"):
                            ok, msg, inv_id = create_invoice_from_order(order_id)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    elif order['status'] == 'Invoiced':
                        st.success("✅ Already invoiced")
                    else:
                        st.button("🧾 Generate Invoice", disabled=True,
                                 use_container_width=True,
                                 key="invoice_disabled")

                # ---- Cancel confirmation ----
                if st.session_state.get('cancelling_order') == order_id:
                    st.warning("⚠️ Provide a cancellation reason:")
                    reason = st.text_area("Cancellation Reason",
                                         key="cancel_reason")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("✅ Confirm Cancel", type="primary",
                                     use_container_width=True,
                                     key="cancel_yes"):
                            if reason:
                                ok, msg = cancel_order(order_id, reason)
                                if ok:
                                    st.success(msg)
                                    del st.session_state.cancelling_order
                                    st.rerun()
                                else:
                                    st.error(msg)
                            else:
                                st.error("Reason required")
                    with col_no:
                        if st.button("❌ Back", use_container_width=True,
                                     key="cancel_no"):
                            del st.session_state.cancelling_order
                            st.rerun()

    # ============================================
    # TAB 4: INVOICES
    # ============================================
    with tab4:
        st.markdown("#### 🧾 Invoices")

        col1, col2 = st.columns([3, 1])
        with col1:
            search = st.text_input("🔍 Search by invoice # or customer",
                                   key="inv_search")
        with col2:
            status_filter = st.selectbox("Status",
                                        ["All", "Unpaid", "Partial", "Paid"],
                                        key="inv_status")

        df = get_invoices(search=search or None,
                          status_filter=status_filter)

        if df.empty:
            st.info(
                "📭 No invoices yet. "
                "Go to **🔍 Order Details** tab → pick a **Confirmed** order "
                "→ click **🧾 Generate Invoice**."
            )
        else:
            st.success(f"✅ {len(df)} invoice(s)")

            display = df.copy()
            display['total_amount'] = display['total_amount'].apply(
                lambda x: f"KES {float(x):,.2f}" if x else "KES 0.00"
            )
            display['balance_due'] = display['balance_due'].apply(
                lambda x: f"KES {float(x):,.2f}" if x else "KES 0.00"
            )
            display['invoice_date'] = display['invoice_date'].astype(str)
            display['due_date'] = display['due_date'].astype(str)

            display = display[['id', 'invoice_number', 'invoice_date',
                              'due_date', 'customer_name', 'order_number',
                              'total_amount', 'balance_due', 'status']]
            display.columns = ['ID', 'Invoice #', 'Date', 'Due', 'Customer',
                              'Order', 'Total', 'Balance', 'Status']
            st.dataframe(display, use_container_width=True,
                        hide_index=True, height=400)

            st.markdown("---")
            st.markdown("#### 📥 Download Invoice")

            inv_options = {
                f"{row['invoice_number']} — {row['customer_name']}": row['id']
                for _, row in df.iterrows()
            }

            selected_inv = st.selectbox("Select Invoice",
                                        list(inv_options.keys()),
                                        key="inv_download_sel")
            inv_id = inv_options[selected_inv]

            html = generate_invoice_html(inv_id)

            if html:
                st.download_button(
                    "📥 Download Invoice (HTML)",
                    html,
                    f"invoice_{inv_id}_{datetime.now().strftime('%Y%m%d')}.html",
                    "text/html",
                    use_container_width=True,
                )
                with st.expander("👁️ Preview Invoice"):
                    st.components.v1.html(html, height=700, scrolling=True)
