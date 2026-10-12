# pages_settings.py
# Settings Module — Warehouse & Category Register

import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql


def settings_page():
    """Settings page - Warehouse register and categories"""
    
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important;
        }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>⚙️ Settings</h2>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["🏢 Warehouses", "📁 Product Categories", "ℹ️ System Info"])
    
    # ============================================
    # TAB 1: WAREHOUSES
    # ============================================
    with tab1:
        st.markdown("#### 🏢 Warehouses / Stock Locations")
        st.caption("Define where stock is stored — Main Store, Production, Distribution Depot")
        
        df = read_sql("""
            SELECT id, code, name, warehouse_type, location, manager_name, is_active
            FROM warehouses
            ORDER BY id
        """)
        
        if not df.empty:
            display_df = df.copy()
            display_df['is_active'] = display_df['is_active'].apply(lambda x: "✅ Active" if x else "❌ Inactive")
            display_df.columns = ['ID', 'Code', 'Name', 'Type', 'Location', 'Manager', 'Status']
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No warehouses yet.")
        
        st.markdown("---")
        
        with st.expander("➕ Add Warehouse / Stock Location", expanded=False):
            with st.form("add_warehouse_form"):
                col1, col2 = st.columns(2)
                with col1:
                    wh_code = st.text_input("Code *", placeholder="e.g., MAIN, PROD, DIST", key="wh_code")
                    wh_name = st.text_input("Name *", placeholder="e.g., Main Store", key="wh_name")
                with col2:
                    wh_type = st.selectbox("Type *", 
                        ["Main Store", "Production Store", "Distribution Depot", "Transit", "Other"],
                        key="wh_type")
                    wh_location = st.text_input("Location", placeholder="e.g., Head Office", key="wh_loc")
                
                wh_address = st.text_input("Address", placeholder="Full address", key="wh_addr")
                wh_phone = st.text_input("Phone", placeholder="+254...", key="wh_phone")
                wh_manager = st.text_input("Manager Name", placeholder="Name of manager", key="wh_mgr")
                wh_notes = st.text_area("Notes", height=60, key="wh_notes")
                
                submitted = st.form_submit_button("💾 Save Warehouse", type="primary", use_container_width=True)
                
                if submitted:
                    if not wh_code or not wh_name:
                        st.error("❌ Code and Name are required")
                    else:
                        conn = get_db_connection()
                        try:
                            existing = conn.execute(
                                text("SELECT id FROM warehouses WHERE LOWER(code) = LOWER(:c)"),
                                {"c": wh_code.strip()}
                            ).fetchone()
                            
                            if existing:
                                st.error(f"❌ Code '{wh_code}' already exists")
                            else:
                                conn.execute(text("""
                                    INSERT INTO warehouses (
                                        code, name, warehouse_type, location, address,
                                        phone, manager_name, is_active, notes,
                                        created_at, updated_at
                                    ) VALUES (
                                        :code, :name, :type, :loc, :addr,
                                        :phone, :mgr, 1, :notes,
                                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                                    )
                                """), {
                                    "code": wh_code.strip().upper(),
                                    "name": wh_name.strip(),
                                    "type": wh_type,
                                    "loc": wh_location,
                                    "addr": wh_address,
                                    "phone": wh_phone,
                                    "mgr": wh_manager,
                                    "notes": wh_notes,
                                })
                                conn.commit()
                                log_audit("CREATE_WAREHOUSE", "warehouses", None)
                                st.success(f"✅ Warehouse '{wh_name}' created!")
                                st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"❌ Error: {e}")
                        finally:
                            conn.close()
    
    # ============================================
    # TAB 2: PRODUCT CATEGORIES
    # ============================================
    with tab2:
        st.markdown("#### 📁 Product Categories")
        
        df = read_sql("""
            SELECT id, name, description, is_active
            FROM product_categories
            ORDER BY name
        """)
        
        if not df.empty:
            display_df = df.copy()
            display_df['is_active'] = display_df['is_active'].apply(lambda x: "✅" if x else "❌")
            display_df.columns = ['ID', 'Name', 'Description', 'Active']
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No categories yet.")
        
        with st.expander("➕ Add Category", expanded=False):
            with st.form("add_category_form"):
                cat_name = st.text_input("Category Name *", key="cat_name")
                cat_desc = st.text_area("Description", height=60, key="cat_desc")
                
                if st.form_submit_button("💾 Save Category", type="primary", use_container_width=True):
                    if not cat_name:
                        st.error("❌ Name required")
                    else:
                        conn = get_db_connection()
                        try:
                            conn.execute(text("""
                                INSERT INTO product_categories (name, description, is_active, created_at)
                                VALUES (:name, :desc, 1, CURRENT_TIMESTAMP)
                            """), {"name": cat_name.strip(), "desc": cat_desc})
                            conn.commit()
                            st.success(f"✅ Category '{cat_name}' added!")
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"❌ Error: {e}")
                        finally:
                            conn.close()
    
    # ============================================
    # TAB 3: SYSTEM INFO
    # ============================================
    with tab3:
        st.markdown("#### ℹ️ System Information")
        
        from database import get_is_cloud
        db_type = "PostgreSQL (Cloud - Neon)" if get_is_cloud() else "SQLite (Local)"
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Database:** {db_type}")
            st.info(f"**Application:** Amigoz ERP v1.0.0")
        with col2:
            st.info(f"**Current User:** {st.session_state.get('full_name', 'N/A')}")
            st.info(f"**Role:** {st.session_state.get('role', 'N/A')}")
        
        st.markdown("---")
        st.markdown("#### 📊 Table Counts")
        
        conn = get_db_connection()
        if conn:
            tables = ["products", "customers", "suppliers", "warehouses",
                      "product_categories", "product_batches", "stock_movements",
                      "sales_orders", "dispatches", "deliveries", "containers",
                      "payments", "users", "audit_logs"]
            
            counts = []
            for t in tables:
                try:
                    c = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                    counts.append({"Table": t, "Records": c or 0})
                except:
                    counts.append({"Table": t, "Records": "N/A"})
            conn.close()
            
            st.dataframe(pd.DataFrame(counts), use_container_width=True, hide_index=True)
