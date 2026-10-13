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

def dashboard_page():
    import pandas as pd
    from datetime import date, timedelta
    from database import read_sql

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
        .kpi-card {
            background: white;
            padding: 18px;
            border-radius: 12px;
            border-left: 4px solid #0284c7;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            margin-bottom: 12px;
        }
        .kpi-label { color: #64748b; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
        .kpi-value { color: #0c4a6e; font-size: 26px; font-weight: 700; margin: 4px 0; }
        .kpi-delta { font-size: 12px; }
        .kpi-delta.up { color: #16a34a; }
        .kpi-delta.down { color: #dc2626; }
        .alert-card {
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .alert-danger {
            background: #fee2e2;
            border-left-color: #dc2626;
        }
    </style>
    """, unsafe_allow_html=True)

    # ---------------- Header ----------------
    user = st.session_state.get('full_name') or st.session_state.get('user') or 'User'
    role = st.session_state.get('role') or ''
    today_str = date.today().strftime('%A, %d %B %Y')

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 50%, #7dd3fc 100%);
        padding: 24px 28px; border-radius: 16px; border-left: 6px solid #0284c7;
        margin-bottom: 24px; box-shadow: 0 6px 16px rgba(14, 165, 233, 0.2);
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
                <h2 style="color: #0c4a6e; margin: 0; font-weight: 700; font-size: 24px;">
                    👋 Welcome back, {user}
                </h2>
                <p style="color: #0369a1; margin: 6px 0 0; font-size: 15px;">
                    {today_str} · {role}
                </p>
            </div>
            <div style="font-size: 48px;">💧</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ---------------- Filters ----------------
    col1, col2, col3 = st.columns([2, 2, 3])
    with col1:
        period = st.selectbox("Period", ["Last 7 days", "Last 30 days",
                                          "Last 90 days", "Year to date"],
                              key="dash_period")
    with col2:
        warehouse_filter = st.selectbox("Warehouse", ["All Warehouses"] + [
            r['code'] for _, r in read_sql(
                "SELECT code FROM warehouses WHERE is_active = TRUE ORDER BY code"
            ).iterrows()
        ], key="dash_wh")

    # Compute date range
    today = date.today()
    if period == "Last 7 days":
        from_date = today - timedelta(days=7)
    elif period == "Last 30 days":
        from_date = today - timedelta(days=30)
    elif period == "Last 90 days":
        from_date = today - timedelta(days=90)
    else:
        from_date = date(today.year, 1, 1)

    wh_clause = ""
    wh_params = {}
    if warehouse_filter != "All Warehouses":
        wh_clause = " AND w.code = :wh_code "
        wh_params["wh_code"] = warehouse_filter

    # =========================================================
    # KPI ROW 1 — Business health
    # =========================================================
    st.markdown("### 📊 Business Overview")

    # Counts
    counts_df = read_sql("""
        SELECT
            (SELECT COUNT(*) FROM products WHERE is_active = TRUE AND product_code NOT LIKE 'TPRD-%') AS products,
            (SELECT COUNT(*) FROM customers WHERE is_active = TRUE AND customer_code NOT LIKE 'TST-%') AS customers,
            (SELECT COUNT(*) FROM suppliers WHERE is_active = TRUE AND supplier_code NOT LIKE 'TST-%') AS suppliers,
            (SELECT COUNT(*) FROM users WHERE is_active = TRUE) AS users
    """)
    if not counts_df.empty:
        c = counts_df.iloc[0]
    else:
        c = {'products': 0, 'customers': 0, 'suppliers': 0, 'users': 0}

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">📦 Active Products</div>
            <div class="kpi-value">{int(c['products']):,}</div>
            <div class="kpi-delta">Live SKUs</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="kpi-card" style="border-left-color:#10b981;">
            <div class="kpi-label">👥 Active Customers</div>
            <div class="kpi-value">{int(c['customers']):,}</div>
            <div class="kpi-delta">Registered accounts</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="kpi-card" style="border-left-color:#f59e0b;">
            <div class="kpi-label">🏭 Active Suppliers</div>
            <div class="kpi-value">{int(c['suppliers']):,}</div>
            <div class="kpi-delta">Vendor accounts</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="kpi-card" style="border-left-color:#8b5cf6;">
            <div class="kpi-label">👤 System Users</div>
            <div class="kpi-value">{int(c['users']):,}</div>
            <div class="kpi-delta">Active logins</div>
        </div>
        """, unsafe_allow_html=True)

    # =========================================================
    # KPI ROW 2 — Financial period metrics
    # =========================================================
    st.markdown("### 💰 Financial Performance")

    fin_df = read_sql("""
        SELECT
            COALESCE(SUM(CASE WHEN so.status NOT IN ('Cancelled','Draft') THEN so.total_amount END), 0) AS period_sales,
            COALESCE(SUM(CASE WHEN so.status NOT IN ('Cancelled','Draft') THEN so.subtotal END), 0) AS period_subtotal,
            COALESCE(SUM(CASE WHEN so.status NOT IN ('Cancelled','Draft') THEN so.tax_amount END), 0) AS period_tax,
            COUNT(DISTINCT so.id) FILTER (WHERE so.status NOT IN ('Cancelled','Draft')) AS order_count,
            COALESCE(SUM(CASE WHEN so.status IN ('Dispatched','Invoiced') THEN so.total_amount END), 0) AS dispatched_value
        FROM sales_orders so
        WHERE so.order_date BETWEEN :fd AND :td
    """, {"fd": from_date, "td": today})

    if not fin_df.empty:
        f = fin_df.iloc[0]
    else:
        f = {'period_sales': 0, 'period_subtotal': 0, 'period_tax': 0,
             'order_count': 0, 'dispatched_value': 0}

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="kpi-card" style="border-left-color:#0284c7;">
            <div class="kpi-label">💵 Period Sales</div>
            <div class="kpi-value">KES {float(f['period_sales']):,.0f}</div>
            <div class="kpi-delta">{period}</div>
        </div>
        """, unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="kpi-card" style="border-left-color:#10b981;">
            <div class="kpi-label">📋 Orders</div>
            <div class="kpi-value">{int(f['order_count']):,}</div>
            <div class="kpi-delta">Confirmed & above</div>
        </div>
        """, unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="kpi-card" style="border-left-color:#f59e0b;">
            <div class="kpi-label">🏛️ VAT Collected</div>
            <div class="kpi-value">KES {float(f['period_tax']):,.0f}</div>
            <div class="kpi-delta">Output tax</div>
        </div>
        """, unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
        <div class="kpi-card" style="border-left-color:#8b5cf6;">
            <div class="kpi-label">🚚 Dispatched Value</div>
            <div class="kpi-value">KES {float(f['dispatched_value']):,.0f}</div>
            <div class="kpi-delta">In transit & delivered</div>
        </div>
        """, unsafe_allow_html=True)

    # =========================================================
    # ROW 3 — Sales trend + Stock value
    # =========================================================
    st.markdown("### 📈 Trends")

    col_left, col_right = st.columns([3, 2])

    with col_left:
        # Sales over time
        trend_df = read_sql("""
            SELECT 
                so.order_date AS day,
                SUM(so.total_amount) AS sales,
                COUNT(*) AS orders
            FROM sales_orders so
            WHERE so.order_date BETWEEN :fd AND :td
              AND so.status NOT IN ('Cancelled','Draft')
            GROUP BY so.order_date
            ORDER BY so.order_date
        """, {"fd": from_date, "td": today})

        if trend_df.empty:
            st.info("No sales in this period.")
        else:
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=trend_df['day'], y=trend_df['sales'],
                mode='lines+markers',
                line=dict(color='#0ea5e9', width=3),
                fill='tozeroy',
                fillcolor='rgba(14, 165, 233, 0.15)',
                name='Sales',
            ))
            fig.update_layout(
                title="Sales Over Time",
                height=320,
                margin=dict(l=0, r=0, t=40, b=0),
                showlegend=False,
                plot_bgcolor='rgba(255,255,255,0.5)',
                paper_bgcolor='rgba(255,255,255,0.5)',
                hovermode='x unified',
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        # Stock value at cost
        stock_val = read_sql("""
            SELECT
                COALESCE(SUM(p.cost_price * COALESCE((
                    SELECT SUM(sm.quantity_change)
                    FROM stock_movements sm
                    WHERE sm.product_id = p.id AND sm.is_posted = TRUE
                ), 0)), 0) AS cost_value
            FROM products p
            WHERE p.is_active = TRUE
        """)
        cost_value = float(stock_val.iloc[0]['cost_value']) if not stock_val.empty else 0

        # AR / AP
        ar_df = read_sql("""
            SELECT COALESCE(SUM(balance_due), 0) AS ar
            FROM invoices
            WHERE status IN ('Unpaid','Partial')
        """)
        ar = float(ar_df.iloc[0]['ar']) if not ar_df.empty else 0

        ap_df = read_sql("""
            SELECT COALESCE(SUM(total_amount), 0) AS ap
            FROM purchase_orders
            WHERE status IN ('Approved','Partially Received','Fully Received')
        """)
        ap = float(ap_df.iloc[0]['ap']) if not ap_df.empty else 0

        st.markdown(f"""
        <div class="kpi-card" style="border-left-color:#16a34a;">
            <div class="kpi-label">🏭 Total Stock Value (at cost)</div>
            <div class="kpi-value">KES {cost_value:,.0f}</div>
            <div class="kpi-delta">Physical inventory</div>
        </div>
        <div class="kpi-card" style="border-left-color:#dc2626;">
            <div class="kpi-label">📥 Accounts Receivable</div>
            <div class="kpi-value">KES {ar:,.0f}</div>
            <div class="kpi-delta">Unpaid customer invoices</div>
        </div>
        <div class="kpi-card" style="border-left-color:#f59e0b;">
            <div class="kpi-label">📤 Accounts Payable</div>
            <div class="kpi-value">KES {ap:,.0f}</div>
            <div class="kpi-delta">Open supplier POs</div>
        </div>
        """, unsafe_allow_html=True)

    # =========================================================
    # ROW 4 — Top performers
    # =========================================================
    st.markdown("### 🏆 Top Performers")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### 🥇 Top Products by Revenue")
        top_prods = read_sql("""
            SELECT 
                p.product_name,
                SUM(soi.quantity_ordered) AS qty_sold,
                SUM(soi.line_total) AS revenue
            FROM sales_order_items soi
            JOIN sales_orders so ON soi.order_id = so.id
            JOIN products p ON soi.product_id = p.id
            WHERE so.order_date BETWEEN :fd AND :td
              AND so.status NOT IN ('Cancelled','Draft')
            GROUP BY p.product_name
            ORDER BY revenue DESC
            LIMIT 10
        """, {"fd": from_date, "td": today})

        if top_prods.empty:
            st.caption("No product sales in this period.")
        else:
            import plotly.express as px
            fig = px.bar(
                top_prods, x='revenue', y='product_name',
                orientation='h',
                color='revenue',
                color_continuous_scale='Blues',
                labels={'revenue': 'Revenue (KES)', 'product_name': ''},
            )
            fig.update_layout(
                height=350,
                margin=dict(l=0, r=0, t=20, b=0),
                showlegend=False,
                yaxis={'categoryorder': 'total ascending'},
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("#### 🥇 Top Customers by Spend")
        top_custs = read_sql("""
            SELECT 
                c.customer_name,
                COUNT(DISTINCT so.id) AS order_count,
                SUM(so.total_amount) AS total_spend
            FROM sales_orders so
            JOIN customers c ON so.customer_id = c.id
            WHERE so.order_date BETWEEN :fd AND :td
              AND so.status NOT IN ('Cancelled','Draft')
            GROUP BY c.customer_name
            ORDER BY total_spend DESC
            LIMIT 10
        """, {"fd": from_date, "td": today})

        if top_custs.empty:
            st.caption("No customer sales in this period.")
        else:
            import plotly.express as px
            fig = px.bar(
                top_custs, x='total_spend', y='customer_name',
                orientation='h',
                color='total_spend',
                color_continuous_scale='Greens',
                labels={'total_spend': 'Spend (KES)', 'customer_name': ''},
            )
            fig.update_layout(
                height=350,
                margin=dict(l=0, r=0, t=20, b=0),
                showlegend=False,
                yaxis={'categoryorder': 'total ascending'},
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    # =========================================================
    # ROW 5 — Status distribution + Alerts
    # =========================================================
    st.markdown("### 🔔 Alerts & Status")

    col_x, col_y = st.columns([2, 3])

    with col_x:
        st.markdown("#### 📋 Order Status Distribution")
        status_df = read_sql("""
            SELECT status, COUNT(*) AS cnt
            FROM sales_orders
            WHERE order_date BETWEEN :fd AND :td
            GROUP BY status
            ORDER BY cnt DESC
        """, {"fd": from_date, "td": today})

        if status_df.empty:
            st.caption("No orders in this period.")
        else:
            import plotly.graph_objects as go
            fig = go.Figure(data=[go.Pie(
                labels=status_df['status'],
                values=status_df['cnt'],
                hole=0.5,
                marker=dict(colors=['#0ea5e9','#10b981','#f59e0b',
                                    '#8b5cf6','#ef4444'][:len(status_df)]),
            )])
            fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=20, b=0),
                showlegend=True,
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_y:
        st.markdown("#### ⚠️ Action Items")

        # Low stock
        low_stock = read_sql("""
            SELECT p.product_code, p.product_name,
                   COALESCE(SUM(sm.quantity_change), 0) AS stock,
                   p.reorder_level
            FROM products p
            LEFT JOIN stock_movements sm 
                ON sm.product_id = p.id AND sm.is_posted = TRUE
            WHERE p.is_active = TRUE
              AND p.reorder_level > 0
            GROUP BY p.id, p.product_code, p.product_name, p.reorder_level
            HAVING COALESCE(SUM(sm.quantity_change), 0) < p.reorder_level
            ORDER BY (COALESCE(SUM(sm.quantity_change), 0) - p.reorder_level) ASC
            LIMIT 5
        """)

        if not low_stock.empty:
            for _, r in low_stock.iterrows():
                st.markdown(f"""
                <div class="alert-card">
                    <strong>⚠️ Low Stock:</strong> {r['product_name']}
                    <br><small>Current: {int(r['stock'])} / Reorder at: {int(r['reorder_level'])}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ All products above reorder level")

        # Overdue invoices
        overdue = read_sql("""
            SELECT invoice_number, due_date, balance_due, customer_id
            FROM invoices
            WHERE status IN ('Unpaid','Partial')
              AND due_date < CURRENT_DATE
            ORDER BY due_date ASC
            LIMIT 5
        """)
        if not overdue.empty:
            st.markdown(f"""
            <div class="alert-card alert-danger">
                <strong>💸 {len(overdue)} overdue invoice(s)</strong>
                <br><small>Oldest due: {overdue.iloc[0]['due_date']}</small>
            </div>
            """, unsafe_allow_html=True)

        # Batches expiring soon
        expiring = read_sql("""
            SELECT COUNT(*) AS cnt
            FROM product_batches
            WHERE quality_status = 'Released'
              AND expiry_date IS NOT NULL
              AND expiry_date <= CURRENT_DATE + INTERVAL '90 days'
              AND expiry_date >= CURRENT_DATE
        """)
        if not expiring.empty and int(expiring.iloc[0]['cnt'] or 0) > 0:
            st.markdown(f"""
            <div class="alert-card">
                <strong>⏰ {int(expiring.iloc[0]['cnt'])} batch(es) expiring in 90 days</strong>
                <br><small>Review Quality Control → Expiry Monitor</small>
            </div>
            """, unsafe_allow_html=True)

        # Pending POs
        pending_pos = read_sql("""
            SELECT COUNT(*) AS cnt
            FROM purchase_orders
            WHERE status IN ('Approved','Partially Received')
        """)
        if not pending_pos.empty and int(pending_pos.iloc[0]['cnt'] or 0) > 0:
            st.markdown(f"""
            <div class="alert-card">
                <strong>📦 {int(pending_pos.iloc[0]['cnt'])} POs awaiting delivery</strong>
                <br><small>Review Procurement → Purchase Orders</small>
            </div>
            """, unsafe_allow_html=True)

    # =========================================================
    # ROW 6 — Activity feed
    # =========================================================
    st.markdown("### 📝 Recent Activity")

    activity = read_sql("""
        SELECT timestamp, username, action, table_name, record_id
        FROM audit_logs
        ORDER BY timestamp DESC
        LIMIT 15
    """)

    if activity.empty:
        st.caption("No activity yet.")
    else:
        display = activity.copy()
        display['timestamp'] = display['timestamp'].astype(str).str[:19]
        display = display[['timestamp', 'username', 'action', 'table_name', 'record_id']]
        display.columns = ['Time', 'User', 'Action', 'Table', 'Record ID']
        st.dataframe(display, use_container_width=True, hide_index=True, height=400)

    # =========================================================
    # FOOTER
    # =========================================================
    st.markdown("---")
    st.caption(
        f"💧 Amigoz ERP · Period: {from_date} → {today} · "
        f"Warehouse: {warehouse_filter} · "
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
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
