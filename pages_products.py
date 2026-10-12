# pages_products.py
# Product Register Module - Stage 01, Step 2

import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import text
from database import get_db_connection, log_audit, get_next_code


def products_page():
    """Product Register UI - CRUD"""
    
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important;
        }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
        div[data-testid="stDataFrame"] {
            background: white !important;
            border-radius: 12px !important;
            border: 1px solid #bae6fd !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>📦 Product Register</h2>", unsafe_allow_html=True)
    st.caption("Manage all products — bottled water, sachets, containers, and accessories")
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📋 View Products", "➕ Add Product", "✏️ Edit Product"])
    
    # ============================================
    # TAB 1: VIEW PRODUCTS
    # ============================================
    with tab1:
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            search_term = st.text_input("🔍 Search by code or name", placeholder="Type to search...", key="prod_search")
        with col2:
            filter_active = st.selectbox("Status", ["All", "Active", "Inactive"], key="prod_status_filter")
        with col3:
            st.write("")
            st.write("")
            refresh = st.button("🔄 Refresh", use_container_width=True)
        
        conn = get_db_connection()
        if not conn:
            st.error("Cannot connect to database")
            return
        
        try:
            query = """
                SELECT p.id, p.product_code, p.product_name, 
                       c.name as category, p.size, p.unit,
                       p.cost_price, p.selling_price,
                       p.reorder_level, p.is_batch_tracked, p.is_active
                FROM products p
                LEFT JOIN product_categories c ON p.category_id = c.id
                WHERE 1=1
            """
            params = {}
            
            if search_term:
                query += " AND (LOWER(p.product_code) LIKE :search OR LOWER(p.product_name) LIKE :search)"
                params["search"] = f"%{search_term.lower()}%"
            
            if filter_active == "Active":
                query += " AND p.is_active = 1"
            elif filter_active == "Inactive":
                query += " AND p.is_active = 0"
            
            query += " ORDER BY p.id DESC"
            
            df = pd.read_sql(text(query), conn, params=params)
            
            if df.empty:
                st.info("📭 No products yet. Use the '➕ Add Product' tab to create your first product.")
            else:
                st.success(f"✅ {len(df)} product(s) found")
                
                # Format display
                display_df = df.copy()
                display_df['cost_price'] = display_df['cost_price'].apply(lambda x: f"KES {float(x):,.2f}" if x else "KES 0.00")
                display_df['selling_price'] = display_df['selling_price'].apply(lambda x: f"KES {float(x):,.2f}" if x else "KES 0.00")
                display_df['is_active'] = display_df['is_active'].apply(lambda x: "✅ Active" if x else "❌ Inactive")
                display_df['is_batch_tracked'] = display_df['is_batch_tracked'].apply(lambda x: "Yes" if x else "No")
                
                display_df = display_df.rename(columns={
                    'product_code': 'Code',
                    'product_name': 'Product Name',
                    'category': 'Category',
                    'size': 'Size',
                    'unit': 'Unit',
                    'cost_price': 'Cost Price',
                    'selling_price': 'Selling Price',
                    'reorder_level': 'Reorder Level',
                    'is_batch_tracked': 'Batch Tracked',
                    'is_active': 'Status',
                })
                
                st.dataframe(
                    display_df[['id', 'Code', 'Product Name', 'Category', 'Size', 'Unit',
                                'Cost Price', 'Selling Price', 'Reorder Level', 'Batch Tracked', 'Status']],
                    use_container_width=True,
                    hide_index=True,
                    height=400,
                )
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Download CSV",
                    csv,
                    f"products_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv",
                )
        finally:
            conn.close()
    
    # ============================================
    # TAB 2: ADD PRODUCT
    # ============================================
    with tab2:
        st.markdown("#### ➕ Add New Product")
        
        conn = get_db_connection()
        if not conn:
            return
        
        try:
            # Get categories
            cats_df = pd.read_sql(text("SELECT id, name FROM product_categories WHERE is_active = 1 ORDER BY name"), conn)
            cat_options = {row['name']: row['id'] for _, row in cats_df.iterrows()}
            cat_options["— No Category —"] = None
            
            with st.form("add_product_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    product_code = st.text_input("Product Code *", placeholder="e.g., BW-500ML", key="add_prod_code")
                    product_name = st.text_input("Product Name *", placeholder="e.g., 500ml Bottled Water", key="add_prod_name")
                    category = st.selectbox("Category", list(cat_options.keys()), key="add_prod_cat")
                    size = st.text_input("Size", placeholder="e.g., 500ml, 20L", key="add_prod_size")
                    unit = st.selectbox("Unit", ["pcs", "carton", "pack", "litre", "kg"], key="add_prod_unit")
                    
                with col2:
                    pack_size = st.number_input("Pack Size", min_value=1, value=1, key="add_prod_pack")
                    cost_price = st.number_input("Cost Price (KES)", min_value=0.0, value=0.0, step=0.50, format="%.2f", key="add_prod_cost")
                    selling_price = st.number_input("Selling Price (KES)", min_value=0.0, value=0.0, step=0.50, format="%.2f", key="add_prod_price")
                    reorder_level = st.number_input("Reorder Level", min_value=0, value=10, key="add_prod_reorder")
                    reorder_quantity = st.number_input("Reorder Quantity", min_value=0, value=50, key="add_prod_reorder_qty")
                
                description = st.text_area("Description", placeholder="Optional details...", height=80, key="add_prod_desc")
                is_batch_tracked = st.checkbox("Batch Tracked (for quality control)", value=False, key="add_prod_batch")
                
                submitted = st.form_submit_button("💾 Save Product", type="primary", use_container_width=True)
                
                if submitted:
                    # Validate
                    if not product_code or not product_name:
                        st.error("❌ Product Code and Name are required")
                    else:
                        # Duplicate check
                        existing = conn.execute(
                            text("SELECT id FROM products WHERE LOWER(product_code) = LOWER(:code)"),
                            {"code": product_code.strip()}
                        ).fetchone()
                        
                        if existing:
                            st.error(f"❌ Product code '{product_code}' already exists")
                        else:
                            try:
                                conn.execute(text("""
                                    INSERT INTO products (
                                        product_code, product_name, category_id, size, unit,
                                        pack_size, cost_price, selling_price,
                                        reorder_level, reorder_quantity,
                                        is_batch_tracked, is_active, description,
                                        created_at, updated_at
                                    ) VALUES (
                                        :code, :name, :cat, :size, :unit,
                                        :pack, :cost, :price,
                                        :reorder, :reorder_qty,
                                        :batch, 1, :desc,
                                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                                    )
                                """), {
                                    "code": product_code.strip(),
                                    "name": product_name.strip(),
                                    "cat": cat_options[category],
                                    "size": size,
                                    "unit": unit,
                                    "pack": pack_size,
                                    "cost": cost_cost if (cost_cost := cost_price) else 0,
                                    "price": selling_price,
                                    "reorder": reorder_level,
                                    "reorder_qty": reorder_quantity,
                                    "batch": is_batch_tracked,
                                    "desc": description,
                                })
                                conn.commit()
                                
                                log_audit("CREATE_PRODUCT", "products", None,
                                         new_values={"product_code": product_code, "product_name": product_name})
                                
                                st.success(f"✅ Product '{product_name}' created successfully!")
                                st.balloons()
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"❌ Error: {e}")
        finally:
            conn.close()
    
    # ============================================
    # TAB 3: EDIT PRODUCT
    # ============================================
    with tab3:
        st.markdown("#### ✏️ Edit Product")
        
        conn = get_db_connection()
        if not conn:
            return
        
        try:
            products_df = pd.read_sql(
                text("SELECT id, product_code, product_name FROM products WHERE is_active = 1 ORDER BY product_name"),
                conn
            )
            
            if products_df.empty:
                st.info("No active products to edit.")
            else:
                options = {f"{row['product_code']} — {row['product_name']}": row['id']
                           for _, row in products_df.iterrows()}
                
                selected = st.selectbox("Select Product", list(options.keys()), key="edit_prod_select")
                selected_id = options[selected]
                
                product_df = pd.read_sql(
                    text("SELECT * FROM products WHERE id = :id"),
                    conn, params={"id": selected_id}
                )
                
                if not product_df.empty:
                    p = product_df.iloc[0]
                    
                    cats_df = pd.read_sql(text("SELECT id, name FROM product_categories WHERE is_active = 1 ORDER BY name"), conn)
                    cat_options = {row['name']: row['id'] for _, row in cats_df.iterrows()}
                    cat_options["— No Category —"] = None
                    
                    current_cat_name = "— No Category —"
                    for name, cid in cat_options.items():
                        if cid == p['category_id']:
                            current_cat_name = name
                            break
                    
                    with st.form("edit_product_form"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.text_input("Product Code", value=p['product_code'], disabled=True)
                            product_name = st.text_input("Product Name *", value=p['product_name'])
                            category = st.selectbox("Category", list(cat_options.keys()),
                                                    index=list(cat_options.keys()).index(current_cat_name))
                            size = st.text_input("Size", value=p['size'] or "")
                            unit = st.text_input("Unit", value=p['unit'] or "pcs")
                        
                        with col2:
                            pack_size = st.number_input("Pack Size", min_value=1, value=int(p['pack_size'] or 1))
                            cost_price = st.number_input("Cost Price (KES)", min_value=0.0,
                                                         value=float(p['cost_price'] or 0), step=0.50, format="%.2f")
                            selling_price = st.number_input("Selling Price (KES)", min_value=0.0,
                                                            value=float(p['selling_price'] or 0), step=0.50, format="%.2f")
                            reorder_level = st.number_input("Reorder Level", min_value=0, value=int(p['reorder_level'] or 0))
                            reorder_quantity = st.number_input("Reorder Quantity", min_value=0, value=int(p['reorder_quantity'] or 0))
                        
                        description = st.text_area("Description", value=p['description'] or "", height=80)
                        is_batch_tracked = st.checkbox("Batch Tracked", value=bool(p['is_batch_tracked']))
                        is_active = st.checkbox("Active", value=bool(p['is_active']))
                        
                        col_a, col_b = st.columns(2)
                        with col_a:
                            save = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
                        with col_b:
                            delete = st.form_submit_button("🗑️ Deactivate", use_container_width=True)
                        
                        if save:
                            try:
                                conn.execute(text("""
                                    UPDATE products SET
                                        product_name = :name,
                                        category_id = :cat,
                                        size = :size,
                                        unit = :unit,
                                        pack_size = :pack,
                                        cost_price = :cost,
                                        selling_price = :price,
                                        reorder_level = :reorder,
                                        reorder_quantity = :reorder_qty,
                                        is_batch_tracked = :batch,
                                        is_active = :active,
                                        description = :desc,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = :id
                                """), {
                                    "name": product_name,
                                    "cat": cat_options[category],
                                    "size": size,
                                    "unit": unit,
                                    "pack": pack_size,
                                    "cost": cost_price,
                                    "price": selling_price,
                                    "reorder": reorder_level,
                                    "reorder_qty": reorder_quantity,
                                    "batch": is_batch_tracked,
                                    "active": is_active,
                                    "desc": description,
                                    "id": selected_id,
                                })
                                conn.commit()
                                log_audit("UPDATE_PRODUCT", "products", selected_id)
                                st.success("✅ Product updated!")
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"❌ Error: {e}")
                        
                        if delete:
                            try:
                                conn.execute(
                                    text("UPDATE products SET is_active = 0 WHERE id = :id"),
                                    {"id": selected_id}
                                )
                                conn.commit()
                                log_audit("DEACTIVATE_PRODUCT", "products", selected_id)
                                st.success("✅ Product deactivated")
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"❌ Error: {e}")
        finally:
            conn.close()
