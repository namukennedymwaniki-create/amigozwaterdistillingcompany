# =========================================================
# AMIGOZ WATER DISTILLING COMPANY - ERP SYSTEM
# Main Application Entry Point
# =========================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import hashlib
from pages_inventory import inventory_page
from pages_quality import quality_page
from pages_customers import customers_page
from pages_sales import sales_page
from pages_warehouse import warehouse_page
from pages_delivery import delivery_page
from pages_suppliers import suppliers_page
from pages_procurement import procurement_page
from pages_reports import reports_page
from pages_containers import containers_page
from pages_reports_hub import reports_hub_page
from services_permissions import get_visible_menu
from pages_payments import payments_page
from pages_users import users_page
from sqlalchemy import text
from pages_test_data import test_data_page

# =========================================================
# MUST BE FIRST STREAMLIT COMMAND
# =========================================================
st.set_page_config(
    page_title="Amigoz Water Distilling Company - ERP",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# IMPORT DATABASE MODULE
# =========================================================
from database import (
    get_db_connection,
    get_is_cloud,
    initialize_database,
    log_audit,
    get_next_code
)

# =========================================================
# SECURITY FUNCTIONS
# =========================================================
def hash_password(password):
    """Hash a password using SHA256 with salt"""
    salt = "amigoz_secure_salt_2024"
    return hashlib.sha256((salt + password).encode()).hexdigest()

def verify_password(password, hashed):
    """Verify a password against its hash"""
    return hash_password(password) == hashed

# =========================================================
# SESSION STATE INITIALIZATION
# =========================================================
def init_session_state():
    defaults = {
        'authenticated': False,
        'user': None,
        'user_id': None,
        'role': None,
        'full_name': None,
        'theme': 'light',
        'page': 'Dashboard',
        'show_add_user': False,
        'show_add_product': False,
        'show_add_supplier': False,
        'show_add_customer': False,
        'show_add_warehouse': False,
        'db_initialized': False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# =========================================================
# CUSTOM CSS
# =========================================================
def apply_custom_css():
    st.markdown("""
    <style>
        .metric-card {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            transition: all 0.3s;
            border-left: 4px solid #667eea;
            margin-bottom: 15px;
        }
        
        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.12);
        }
        
        .login-container {
            max-width: 420px;
            margin: 80px auto;
            padding: 40px;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.1);
        }
        
        .stButton button {
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.3s;
        }
        
        .stButton button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# LOGIN PAGE (SECURE)
# =========================================================
def login_page():
    st.markdown("""
    <div class="login-container">
        <div style="text-align: center; margin-bottom: 30px;">
            <h2 style="color: #2d3436; font-weight: 700;">💧 Amigoz Water Distilling</h2>
            <p style="color: #888;">Enterprise Resource Planning System</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input(
            "Username",
            placeholder="Enter username",
            key="login_username",
        )
        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter password",
            key="login_password",
        )
        
        if st.button("🔐 Sign In", key="login_button",
                     use_container_width=True, type="primary"):
            if not username or not password:
                st.warning("⚠️ Please enter both username and password")
                return
            
            from services_users import verify_password, touch_login
            from datetime import datetime
            
            session = get_db_connection()
            if not session:
                st.error("❌ Database connection failed. Please try again.")
                return
            
            try:
                result = session.execute(
                    text("""SELECT u.id, u.username, u.password_hash,
                                   u.first_name, u.last_name, u.is_superuser,
                                   u.is_active, u.must_change_password,
                                   r.name as role_name
                            FROM users u
                            LEFT JOIN roles r ON u.role_id = r.id
                            WHERE LOWER(u.username) = LOWER(:u)
                         """),
                    {"u": username.strip()}
                ).fetchone()
                
                # ------------------------------------------------
                # USER NOT FOUND
                # ------------------------------------------------
                if not result:
                    st.error("❌ Invalid username or password")
                    try:
                        touch_login(user_id=0, success=False,
                                    reason=f"Unknown user: {username}")
                    except Exception:
                        pass
                    return
                
                (user_id, uname, pwd_hash,
                 first_name, last_name, is_superuser,
                 is_active, must_change_pwd, role_name) = result
                
                # ------------------------------------------------
                # INACTIVE USER
                # ------------------------------------------------
                if not is_active:
                    st.error("❌ This account has been deactivated. Contact your administrator.")
                    touch_login(user_id=user_id, success=False,
                                reason="Inactive account")
                    return
                
                # ------------------------------------------------
                # PASSWORD CHECK
                # ------------------------------------------------
                if not pwd_hash:
                    st.error("❌ This account has no password set. Contact your administrator.")
                    touch_login(user_id=user_id, success=False,
                                reason="No password hash")
                    return
                
                if not verify_password(password, pwd_hash):
                    st.error("❌ Invalid username or password")
                    touch_login(user_id=user_id, success=False,
                                reason="Wrong password")
                    return
                
                # ------------------------------------------------
                # SUCCESS
                # ------------------------------------------------
                st.session_state.authenticated = True
                st.session_state.user = uname
                st.session_state.user_id = user_id
                st.session_state.role = role_name or ("Administrator" if is_superuser else "User")
                st.session_state.full_name = f"{first_name or ''} {last_name or ''}".strip() or uname
                st.session_state.force_pwd_change = bool(must_change_pwd)
                
                # Log the successful login
                touch_login(user_id=user_id, success=True)
                
                # Audit
                try:
                    from database import log_audit
                    log_audit("LOGIN_SUCCESS", "users", user_id)
                except Exception:
                    pass
                
                st.rerun()
            
            except Exception as e:
                st.error(f"❌ Login error: {e}")
                try:
                    from database import log_audit
                    log_audit("LOGIN_ERROR", "users", None,
                              new_values={"error": str(e), "username": username})
                except Exception:
                    pass
            finally:
                session.close()
        
        st.markdown("""
        <p style="text-align: center; color: #888; font-size: 12px; margin-top: 20px;">
            🔒 Secured login · Contact your administrator for access
        </p>
        """, unsafe_allow_html=True)

# =========================================================
# SIDEBAR NAVIGATION
# =========================================================
def sidebar_navigation():
    st.markdown("""
    <style>
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #4c1d95 0%, #5b21b6 50%, #6d28d9 100%) !important;
        }
        section[data-testid="stSidebar"] .stMarkdown,
        section[data-testid="stSidebar"] .stMarkdown p,
        section[data-testid="stSidebar"] .stMarkdown h1,
        section[data-testid="stSidebar"] .stMarkdown h2,
        section[data-testid="stSidebar"] .stMarkdown h3 {
            color: white !important;
        }
        section[data-testid="stSidebar"] .stButton button {
            background: rgba(255, 255, 255, 0.1) !important;
            color: white !important;
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            border-radius: 10px !important;
            text-align: left !important;
            padding: 10px 15px !important;
            margin-bottom: 4px !important;
        }
        section[data-testid="stSidebar"] .stButton button:hover {
            background: rgba(255, 255, 255, 0.2) !important;
            transform: translateX(4px) !important;
        }
        section[data-testid="stSidebar"] hr {
            border-color: rgba(255, 255, 255, 0.15) !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("""
        <div style="padding: 20px 0; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.15);">
            <h3 style="color: white; margin: 0;">💧 Amigoz ERP</h3>
            <p style="color: rgba(255,255,255,0.7); font-size: 12px; margin: 5px 0 0;">Version 1.0.0</p>
            <p style="color: #fbbf24; font-size: 10px; margin: 5px 0 0;">🔓 Bypass Mode</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.session_state.authenticated:
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 12px; margin-bottom: 20px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="width: 42px; height: 42px; background: linear-gradient(135deg, #fbbf24, #f59e0b); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 18px;">
                        {st.session_state.full_name[0].upper() if st.session_state.full_name else 'U'}
                    </div>
                    <div style="flex: 1;">
                        <div style="color: white; font-weight: 600; font-size: 14px;">{st.session_state.full_name}</div>
                        <div style="color: rgba(255,255,255,0.7); font-size: 12px;">{st.session_state.role or 'User'}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="color: white; font-size: 14px; font-weight: 600; margin-bottom: 12px;
                    border-left: 3px solid #fbbf24; padding: 4px 0 4px 12px;">
            📋 Navigation
        </div>
        """, unsafe_allow_html=True)
        
        pages = {
            "Dashboard": "🏠",
            "User Management": "👤",
            "Products": "📦",
            "Suppliers": "🏭",
            "Customers": "👥",
            "Inventory": "📊",
            "Procurement": "🛒",
            "Production": "⚙️",
            "Quality Control": "🧪",
            "Warehouse": "🏭",
            "Deliveries": "📬",
            "Suppliers": "🏭",
            "Procurement": "🛒",
            "Reports": "📈",
            "Sales": "💰",
            "Containers": "🍶",
            "Payments": "💳",
            "Reports": "📈",
            "Test Data": "🧪",
            "Settings": "⚙️",
        }
        
        # Role-based menu filtering
        role = st.session_state.get('role') or 'Viewer'
        visible = get_visible_menu(role, list(pages.keys()))
        
        for page_name, icon in pages.items():
            if page_name not in visible:
                continue
            is_current = st.session_state.page == page_name
            label = f"▶ {icon} {page_name}" if is_current else f"{icon} {page_name}"
            if st.button(label, key=f"nav_{page_name}", use_container_width=True):
                st.session_state.page = page_name
                st.rerun()
        
        st.markdown("---")
        
        if st.button("🚪 Logout", key="logout_button", use_container_width=True):
            for key in ['authenticated', 'user', 'user_id', 'role', 'full_name']:
                st.session_state[key] = None if key != 'authenticated' else False
            st.rerun()
    
    return st.session_state.page

# =========================================================
# DASHBOARD
# =========================================================
def dashboard_page():
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important;
        }
        div[data-testid="metric-container"] {
            background: linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%) !important;
            border: 1px solid #bae6fd !important;
            border-radius: 14px !important;
            padding: 1.25rem !important;
            box-shadow: 0 4px 12px rgba(14, 165, 233, 0.1) !important;
        }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 50%, #7dd3fc 100%);
        padding: 24px 28px; border-radius: 16px; border-left: 6px solid #0284c7;
        margin-bottom: 24px; box-shadow: 0 6px 16px rgba(14, 165, 233, 0.2);
    ">
        <div style="display: flex; align-items: center; gap: 16px;">
            <span style="font-size: 36px;">✅</span>
            <div>
                <h2 style="color: #0c4a6e; margin: 0; font-weight: 700; font-size: 24px;">
                    Welcome to Amigoz Water Distilling Company ERP
                </h2>
                <p style="color: #0369a1; margin: 6px 0 0; font-size: 15px;">
                    Your all-in-one solution for managing products, suppliers, customers, and more.
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Fetch real counts
    conn = get_db_connection()
    product_count = supplier_count = customer_count = user_count = 0
    
    if conn:
        try:
            for table, var in [
                ("products", "product_count"),
                ("suppliers", "supplier_count"),
                ("customers", "customer_count"),
                ("users", "user_count"),
            ]:
                try:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    if var == "product_count": product_count = result or 0
                    elif var == "supplier_count": supplier_count = result or 0
                    elif var == "customer_count": customer_count = result or 0
                    elif var == "user_count": user_count = result or 0
                except:
                    pass
        finally:
            conn.close()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📦 Products", product_count)
    with col2:
        st.metric("🏭 Suppliers", supplier_count)
    with col3:
        st.metric("👥 Customers", customer_count)
    with col4:
        st.metric("👤 Users", user_count)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    with col1:
        st.markdown("#### 📊 Production Trends")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=days, y=[1200, 1900, 1500, 2100, 1800, 1400, 1600],
            mode='lines+markers',
            line=dict(color='#0ea5e9', width=3),
            fill='tozeroy',
            fillcolor='rgba(14, 165, 233, 0.1)'
        ))
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0),
                          showlegend=False, plot_bgcolor='rgba(255,255,255,0.5)',
                          paper_bgcolor='rgba(255,255,255,0.5)')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("#### 💰 Sales Overview")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=days, y=[5000, 7500, 6000, 9000, 8500, 5500, 7000],
            marker_color='#0ea5e9'
        ))
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0),
                          showlegend=False, plot_bgcolor='rgba(255,255,255,0.5)',
                          paper_bgcolor='rgba(255,255,255,0.5)')
        st.plotly_chart(fig, use_container_width=True)
   
    # Reorder alerts widget
    st.markdown("---")
    st.markdown("#### ⚠️ Reorder Alerts")
    from services_procurement import get_reorder_alerts
    reorder_df = get_reorder_alerts()
    if reorder_df.empty:
        st.success("✅ All products above reorder level")
    else:
        st.warning(f"⚠️ {len(reorder_df)} product(s) below reorder level")
        st.dataframe(
            reorder_df[['product_code', 'product_name', 'current_stock',
                        'reorder_level']].head(10),
            use_container_width=True, hide_index=True,
        )
# =========================================================
# IMPORT PAGE MODULES
# =========================================================
from pages_products import products_page
from pages_settings import settings_page

# =========================================================
# PLACEHOLDER PAGE
# =========================================================
def placeholder_page(page_name):
    st.markdown(f"<h2>{page_name}</h2>", unsafe_allow_html=True)
    st.info(f"🚧 {page_name} module coming soon...")
    st.progress(0.3)
    st.caption("Development progress: 30%")

# =========================================================
# MAIN APP
# =========================================================
def main():
    apply_custom_css()
    
    # ============================================
    # INITIALIZE DATABASE (ONCE)
    # ============================================
    if not st.session_state.db_initialized:
        with st.spinner("🔧 Initializing database..."):
            if initialize_database():
                # Run stage migrations
                from database_migrations import run_migrations
                run_migrations()
                from database_migrations_delivery import run_delivery_migrations
                run_delivery_migrations()
                from database_migrations_delivery import run_delivery_migrations
                run_delivery_migrations()
                
                from database_migrations_procurement import run_procurement_migrations
                run_procurement_migrations()
                from database_migrations_containers import run_container_migrations
                run_container_migrations()
                from database_migrations_payments import run_payments_migrations
                run_payments_migrations()
                from database_migrations_users import run_users_migrations
                run_users_migrations()
                
                st.session_state.db_initialized = True
                st.toast("✅ Database ready!", icon="✅")
            else:
                st.error("❌ Database initialization failed")
    
    if not st.session_state.authenticated:
        login_page()
        return
    
    selected_page = sidebar_navigation()

    # ----------------------------------------------------------
    # FORCE PASSWORD CHANGE ON FIRST LOGIN / AFTER ADMIN RESET
    # ----------------------------------------------------------
    if st.session_state.get('force_pwd_change'):
        st.markdown("### 🔒 Password Change Required")
        st.info("Your account requires a new password before you can continue.")
        
        from services_users import change_own_password
        
        with st.form("force_pwd_change_form"):
            new1 = st.text_input("New Password", type="password", key="fpwd_new1")
            new2 = st.text_input("Confirm New Password", type="password", key="fpwd_new2")
            submitted = st.form_submit_button("🔐 Change Password", type="primary",
                                              use_container_width=True)
            
            if submitted:
                if not new1 or not new2:
                    st.error("Both fields are required")
                elif new1 != new2:
                    st.error("Passwords do not match")
                elif len(new1) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    # We use change_own_password with old == new to skip the check
                    # (or better: use reset_password internally)
                    from services_users import reset_password
                    ok, msg, _ = reset_password(
                        st.session_state.user_id,
                        new_password=new1,
                        must_change=False,
                    )
                    if ok:
                        st.session_state.force_pwd_change = False
                        st.success("✅ Password changed. Welcome!")
                        st.rerun()
                    else:
                        st.error(msg)
        
        # Logout option
        if st.button("🚪 Logout", key="force_pwd_logout"):
            for key in ['authenticated', 'user', 'user_id', 'role',
                        'full_name', 'force_pwd_change']:
                st.session_state[key] = False if key == 'authenticated' else None
            st.rerun()
        
        return  # Stop here — don't render the app until password is changed
    # ============================================
    # ROUTER
    # ============================================
    if selected_page == "Dashboard":
        dashboard_page()
    elif selected_page == "Products":
        products_page()
    elif selected_page == "Customers":
        customers_page()
    elif selected_page == "Inventory":
        inventory_page()
    elif selected_page == "Quality Control":
        quality_page()
    elif selected_page == "Warehouse":
        warehouse_page()
    elif selected_page == "Deliveries":
        delivery_page()
    elif selected_page == "Containers":
        containers_page()
    elif selected_page == "Sales":
        sales_page()
    elif selected_page == "Payments":
        payments_page()
    elif selected_page == "Suppliers":
        suppliers_page()
    elif selected_page == "Procurement":
        procurement_page()
    elif selected_page == "Reports":
        reports_hub_page()
    elif selected_page == "Settings":
        settings_page()
    elif selected_page == "User Management":
        users_page()
    elif selected_page == "Test Data":
        test_data_page()
    elif selected_page in ["Production"]:
        placeholder_page(selected_page)
    else:
        dashboard_page()


if __name__ == "__main__":
    main()
