# pages_warehouse.py
# Warehouse & Dispatch UI — Stage 03

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from sqlalchemy import text
from database import get_db_connection, read_sql
from services_inventory import get_stock_balance
from services_quality import get_available_stock
from services_vehicles import (
    create_vehicle, get_vehicles, update_vehicle,
    create_driver, get_drivers, update_driver
)
from services_reservations import (
    get_active_reservations, release_reservation, expire_old_reservations
)
from services_sales import get_sales_orders, get_order, get_order_items
from services_dispatch import (
    create_dispatch, mark_picked, confirm_dispatch, mark_delivered,
    get_dispatches, get_dispatch, get_dispatch_items, get_fifo_batches,
    get_in_transit, generate_dispatch_note_html, DISPATCH_STATUSES
)


def warehouse_page():
    """Warehouse & Dispatch — 5 tabs"""
    
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important;
        }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>🏭 Warehouse & Dispatch</h2>", unsafe_allow_html=True)
    st.caption("Reserve stock, prepare picking lists, dispatch goods, and track delivery")
    
    # Auto-expire old reservations
    expire_old_reservations()
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔒 Reservations",
        "📝 Picking List",
        "🚚 Dispatch",
        "🛣️ In-Transit",
        "🚐 Vehicles & Drivers",
    ])
    
    # ============================================
    # TAB 1: RESERVATIONS
    # ============================================
    with tab1:
        st.markdown("#### 🔒 Active Stock Reservations")
        st.caption("Reservations are soft holds. Stock is only reduced when dispatched.")
        
        res_df = get_active_reservations()
        
        if res_df.empty:
            st.info("📭 No active reservations. Confirm a sales order to create one.")
        else:
            st.success(f"✅ {len(res_df)} active reservation(s)")
            
            display = res_df.copy()
            display['expires_at'] = display['expires_at'].astype(str)
            display = display[['id', 'reservation_number', 'product_code', 'product_name',
                              'warehouse_code', 'batch_number', 'quantity',
                              'reference_number', 'reserved_for', 'expires_at']]
            display.columns = ['ID', 'Reservation #', 'Code', 'Product', 'Warehouse',
                              'Batch', 'Qty', 'Reference', 'Reserved For', 'Expires']
            
            st.dataframe(display, use_container_width=True, hide_index=True, height=400)
            
            st.markdown("---")
            st.markdown("#### ❌ Release a Reservation")
            
            rel_options = {f"{row['reservation_number']} — {row['product_name']} ({row['quantity']})": row['id']
                           for _, row in res_df.iterrows()}
            rel_sel = st.selectbox("Select Reservation", list(rel_options.keys()), key="rel_rsv")
            rel_reason = st.text_input("Reason for Release", key="rel_reason")
            
            if st.button("Release Reservation", type="primary", key="rel_btn"):
                if not rel_reason:
                    st.error("Reason required")
                else:
                    ok, msg = release_reservation(rel_options[rel_sel], rel_reason)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
    
    # ============================================
    # TAB 2: PICKING LIST
    # ============================================
    with tab2:
        st.markdown("#### 📝 Picking List")
        st.caption("For each order, select the warehouse to pick from. FIFO batches are suggested.")
        
        orders_df = get_sales_orders(status_filter="Confirmed")
        
        if orders_df.empty:
            st.info("No confirmed orders awaiting picking.")
        else:
            options = {f"{row['order_number']} — {row['customer_name']}": row['id']
                       for _, row in orders_df.iterrows()}
            selected = st.selectbox("Select Confirmed Order", list(options.keys()), key="pick_order")
            order_id = options[selected]
            
            order = get_order(order_id)
            items = get_order_items(order_id)
            
            wh_df = read_sql("SELECT id, code, name FROM warehouses WHERE is_active = 1 ORDER BY code")
            wh_options = {f"{row['code']} — {row['name']}": row['id'] for _, row in wh_df.iterrows()}
            pick_wh = st.selectbox("Pick from Warehouse", list(wh_options.keys()), key="pick_wh")
            warehouse_id = wh_options[pick_wh]
            
            st.markdown("---")
            st.markdown("#### Suggested Picks (FIFO)")
            
            pick_plan = []
            
            for _, it in items.iterrows():
                st.markdown(f"**{it['product_code']} — {it['product_name']}** (Ordered: {it['quantity_ordered']})")
                
                # Check if batch-tracked
                is_batch = read_sql(
                    "SELECT is_batch_tracked FROM products WHERE id = :id",
                    {"id": it['product_id']}
                )
                is_bt = bool(is_batch.iloc[0]['is_batch_tracked']) if not is_batch.empty else False
                
                if is_bt:
                    fifo = get_fifo_batches(it['product_id'], warehouse_id, float(it['quantity_ordered']))
                    
                    if not fifo:
                        st.warning(f"   ⚠️ No Released batches available at this warehouse")
                    else:
                        for b in fifo:
                            st.caption(f"   • Batch {b['batch_number']} (expiry {b['expiry_date']}) — take {b['suggested_qty']}")
                            pick_plan.append({
                                "product_id": it['product_id'],
                                "batch_id": b['batch_id'],
                                "quantity": b['suggested_qty'],
                            })
                else:
                    avail = get_stock_balance(it['product_id'], warehouse_id)
                    if avail >= it['quantity_ordered']:
                        st.caption(f"   • Available: {avail} — pick {it['quantity_ordered']}")
                        pick_plan.append({
                            "product_id": it['product_id'],
                            "batch_id": None,
                            "quantity": float(it['quantity_ordered']),
                        })
                    else:
                        st.error(f"   ❌ Insufficient at this warehouse (have {avail}, need {it['quantity_ordered']})")
            
            st.markdown("---")
            
            if st.button("🚚 Create Dispatch from This Plan", type="primary", key="pick_create_dsp"):
                if not pick_plan:
                    st.error("Nothing to dispatch")
                else:
                    # Get vehicle/driver
                    veh_df = get_vehicles()
                    drv_df = get_drivers()
                    
                    ok, msg, dispatch_id = create_dispatch(
                        order_id=order_id,
                        warehouse_id=warehouse_id,
                        dispatch_date=date.today(),
                        notes=f"Picking from {pick_wh}",
                        items=pick_plan,
                    )
                    if ok:
                        st.success(msg)
                        st.info("Go to the '🚚 Dispatch' tab to review and confirm.")
                        st.rerun()
                    else:
                        st.error(msg)
    
    # ============================================
    # TAB 3: DISPATCH
    # ============================================
    with tab3:
        st.markdown("#### 🚚 Dispatches")
        
        col1, col2 = st.columns([2, 2])
        with col1:
            search = st.text_input("🔍 Search", key="dsp_search")
        with col2:
            status_filter = st.selectbox("Status", ["All"] + DISPATCH_STATUSES, key="dsp_status")
        
        df = get_dispatches(status_filter=status_filter, search=search or None)
        
        if df.empty:
            st.info("📭 No dispatches yet.")
        else:
            st.success(f"✅ {len(df)} dispatch(es)")
            
            display = df.copy()
            display['dispatch_date'] = display['dispatch_date'].astype(str)
            display = display[['id', 'dispatch_number', 'dispatch_date', 'customer_name',
                              'order_number', 'warehouse_code', 'plate_number',
                              'driver_name', 'items_count', 'status']]
            display.columns = ['ID', 'Dispatch #', 'Date', 'Customer', 'Order',
                              'Warehouse', 'Vehicle', 'Driver', 'Items', 'Status']
            
            st.dataframe(display, use_container_width=True, hide_index=True, height=350)
            
            st.markdown("---")
            st.markdown("#### ⚙️ Manage a Dispatch")
            
            dsp_options = {f"{row['dispatch_number']} — {row.get('customer_name') or 'N/A'} ({row['status']})": row['id']
                           for _, row in df.iterrows()}
            sel = st.selectbox("Select Dispatch", list(dsp_options.keys()), key="dsp_sel")
            dsp_id = dsp_options[sel]
            
            d = get_dispatch(dsp_id)
            d_items = get_dispatch_items(dsp_id)
            
            if d is not None:
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric("Dispatch #", d['dispatch_number'])
                with col2: st.metric("Warehouse", d.get('warehouse_name') or 'N/A')
                with col3: st.metric("Status", d['status'])
                with col4: st.metric("Items", len(d_items))
                
                if not d_items.empty:
                    st.dataframe(d_items[['product_code', 'product_name', 'batch_number',
                                          'quantity_dispatched', 'unit']],
                                 use_container_width=True, hide_index=True)
                
                col_a, col_b, col_c, col_d = st.columns(4)
                
                with col_a:
                    if d['status'] == 'Draft':
                        if st.button("📝 Mark Picked", use_container_width=True, key="mark_pick"):
                            ok, msg = mark_picked(dsp_id)
                            if ok: st.success(msg); st.rerun()
                            else: st.error(msg)
                
                with col_b:
                    if d['status'] in ['Draft', 'Picked']:
                        if st.button("🚚 Confirm Dispatch", type="primary",
                                     use_container_width=True, key="conf_dsp"):
                            ok, msg = confirm_dispatch(dsp_id)
                            if ok: st.success(msg); st.rerun()
                            else: st.error(msg)
                
                with col_c:
                    if d['status'] == 'Dispatched':
                        if st.button("✅ Mark Delivered", use_container_width=True, key="mark_del"):
                            ok, msg = mark_delivered(dsp_id)
                            if ok: st.success(msg); st.rerun()
                            else: st.error(msg)
                
                with col_d:
                    html = generate_dispatch_note_html(dsp_id)
                    if html:
                        st.download_button(
                            "📥 Dispatch Note",
                            html,
                            f"dispatch_{d['dispatch_number']}.html",
                            "text/html",
                            use_container_width=True,
                            key="dsp_dl"
                        )
    
    # ============================================
    # TAB 4: IN-TRANSIT
    # ============================================
    with tab4:
        st.markdown("#### 🛣️ Goods In-Transit")
        st.caption("Dispatched but not yet delivered")
        
        transit = get_in_transit()
        
        if transit.empty:
            st.success("✅ No goods in transit")
        else:
            st.warning(f"⚠️ {len(transit)} dispatch(es) in transit")
            
            display = transit.copy()
            display['dispatch_date'] = display['dispatch_date'].astype(str)
            display = display[['id', 'dispatch_number', 'dispatch_date', 'customer_name',
                              'warehouse_code', 'plate_number', 'driver_name',
                              'items_count', 'status']]
            display.columns = ['ID', 'Dispatch #', 'Date', 'Customer', 'Warehouse',
                              'Vehicle', 'Driver', 'Items', 'Status']
            
            st.dataframe(display, use_container_width=True, hide_index=True)
    
    # ============================================
    # TAB 5: VEHICLES & DRIVERS
    # ============================================
    with tab5:
        st.markdown("#### 🚐 Vehicles & Drivers")
        
        sub1, sub2 = st.tabs(["🚐 Vehicles", "👤 Drivers"])
        
        # VEHICLES
        with sub1:
            vehicles = get_vehicles(active_only=False)
            
            if not vehicles.empty:
                display = vehicles[['id', 'plate_number', 'description', 'capacity_kg', 'is_active']].copy()
                display['is_active'] = display['is_active'].apply(lambda x: "✅" if x else "❌")
                display.columns = ['ID', 'Plate #', 'Description', 'Capacity (kg)', 'Active']
                st.dataframe(display, use_container_width=True, hide_index=True)
            else:
                st.info("No vehicles registered.")
            
            with st.expander("➕ Add Vehicle"):
                with st.form("add_vehicle_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        plate = st.text_input("Plate Number *", placeholder="e.g., KDA 123X")
                        desc = st.text_input("Description", placeholder="e.g., 3-ton truck")
                    with col2:
                        cap = st.number_input("Capacity (kg)", min_value=0.0, value=0.0, step=100.0)
                        notes = st.text_area("Notes", height=60)
                    
                    if st.form_submit_button("💾 Save Vehicle", type="primary", use_container_width=True):
                        if not plate:
                            st.error("Plate number required")
                        else:
                            ok, msg, _ = create_vehicle(plate, desc, cap, notes)
                            if ok: st.success(msg); st.rerun()
                            else: st.error(msg)
        
        # DRIVERS
        with sub2:
            drivers = get_drivers(active_only=False)
            
            if not drivers.empty:
                display = drivers[['id', 'name', 'phone', 'license_number', 'is_active']].copy()
                display['is_active'] = display['is_active'].apply(lambda x: "✅" if x else "❌")
                display.columns = ['ID', 'Name', 'Phone', 'License #', 'Active']
                st.dataframe(display, use_container_width=True, hide_index=True)
            else:
                st.info("No drivers registered.")
            
            with st.expander("➕ Add Driver"):
                with st.form("add_driver_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        name = st.text_input("Driver Name *")
                        phone = st.text_input("Phone", placeholder="+254...")
                    with col2:
                        lic = st.text_input("License Number")
                        notes = st.text_area("Notes", height=60)
                    
                    if st.form_submit_button("💾 Save Driver", type="primary", use_container_width=True):
                        if not name:
                            st.error("Name required")
                        else:
                            ok, msg, _ = create_driver(name, phone, lic, notes)
                            if ok: st.success(msg); st.rerun()
                            else: st.error(msg)
