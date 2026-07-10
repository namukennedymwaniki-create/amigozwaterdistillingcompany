import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import bcrypt
import os
from dotenv import load_dotenv
import base64
from streamlit_option_menu import option_menu
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.grid import grid

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Water Bottling ERP System",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database connection
def get_db_connection():
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/wb_erp')
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()

# Authentication functions
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Initialize session state
def init_session_state():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'role' not in st.session_state:
        st.session_state.role = None
    if 'theme' not in st.session_state:
        st.session_state.theme = 'light'
    if 'page' not in st.session_state:
        st.session_state.page = 'Dashboard'

# Custom CSS
def apply_custom_css():
    st.markdown("""
    <style>
        /* Main container */
        .main {
            padding: 0rem 1rem;
        }
        
        /* Sidebar styling */
        .css-1d391kg {
            background: linear-gradient(180deg, #1a1a2e 0%, #2d3436 100%);
        }
        
        .css-1d391kg .css-1v3fvcr {
            color: white;
        }
        
        /* Metric cards */
        .metric-card {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            transition: all 0.3s;
        }
        
        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.12);
        }
        
        .metric-icon {
            font-size: 24px;
            margin-bottom: 10px;
        }
        
        .metric-value {
            font-size: 28px;
            font-weight: 700;
            color: #2d3436;
        }
        
        .metric-label {
            font-size: 14px;
            color: #888;
            margin-top: 5px;
        }
        
        /* KPI Cards */
        .kpi-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border-left: 4px solid #667eea;
            margin-bottom: 15px;
        }
        
        .kpi-card .kpi-title {
            font-size: 13px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .kpi-card .kpi-value {
            font-size: 24px;
            font-weight: 700;
            color: #2d3436;
            margin: 5px 0;
        }
        
        .kpi-card .kpi-change {
            font-size: 12px;
            color: #28a745;
        }
        
        /* Data tables */
        .dataframe {
            font-size: 14px;
        }
        
        /* Buttons */
        .stButton button {
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.3s;
        }
        
        .stButton button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        /* Login container */
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 40px;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.1);
        }
        
        .login-title {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .login-title h2 {
            color: #2d3436;
            font-weight: 700;
        }
        
        .login-title p {
            color: #888;
        }
        
        /* Dark theme */
        .dark-theme .metric-card {
            background: #16213e;
            color: #e9ecef;
        }
        
        .dark-theme .kpi-card {
            background: #16213e;
            color: #e9ecef;
        }
        
        .dark-theme .kpi-card .kpi-value {
            color: #e9ecef;
        }
        
        .dark-theme .login-container {
            background: #16213e;
        }
        
        .dark-theme .login-title h2 {
            color: #e9ecef;
        }
    </style>
    """, unsafe_allow_html=True)

# Login page
def login_page():
    st.markdown("""
    <div class="login-container">
        <div class="login-title">
            <h2>💧 Water Bottling ERP</h2>
            <p>Enterprise Resource Planning System</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            remember = st.checkbox("Remember me")
            
            if st.button("Sign In", use_container_width=True):
                if username and password:
                    # Authenticate user
                    session = get_db_connection()
                    try:
                        query = text("""
                            SELECT u.*, r.name as role_name 
                            FROM users u
                            LEFT JOIN roles r ON u.role_id = r.id
                            WHERE u.username = :username AND u.is_active = true
                        """)
                        result = session.execute(query, {"username": username}).fetchone()
                        
                        if result and verify_password(password, result.password_hash):
                            st.session_state.authenticated = True
                            st.session_state.user = result.username
                            st.session_state.user_id = result.id
                            st.session_state.role = result.role_name
                            st.session_state.full_name = f"{result.first_name} {result.last_name}".strip() or result.username
                            
                            # Update last login
                            update_query = text("UPDATE users SET last_login = NOW() WHERE id = :user_id")
                            session.execute(update_query, {"user_id": result.id})
                            session.commit()
                            
                            st.rerun()
                        else:
                            st.error("Invalid username or password")
                    finally:
                        session.close()
                else:
                    st.warning("Please enter both username and password")

# Sidebar navigation
def sidebar_navigation():
    with st.sidebar:
        st.markdown("""
        <div style="padding: 20px 0; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.1);">
            <h3 style="color: white; margin: 0;">💧 WB-ERP</h3>
            <p style="color: rgba(255,255,255,0.6); font-size: 12px; margin: 5px 0 0;">Version 1.0.0</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # User info
        if st.session_state.authenticated:
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="width: 40px; height: 40px; background: #667eea; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 700;">
                        {st.session_state.full_name[0].upper() if st.session_state.full_name else 'U'}
                    </div>
                    <div>
                        <div style="color: white; font-weight: 600;">{st.session_state.full_name}</div>
                        <div style="color: rgba(255,255,255,0.6); font-size: 12px;">{st.session_state.role or 'No Role'}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Navigation menu
        selected = option_menu(
            menu_title=None,
            options=[
                "Dashboard",
                "User Management",
                "Products",
                "Suppliers",
                "Customers",
                "Inventory",
                "Procurement",
                "Production",
                "Quality Control",
                "Sales",
                "Finance",
                "Reports",
                "Settings"
            ],
            icons=[
                "house", "people", "box", "truck", "person",
                "archive", "cart", "gear", "clipboard-check",
                "cash-stack", "bank", "file-earmark-bar-graph", "gear"
            ],
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "rgba(255,255,255,0.6)", "font-size": "18px"},
                "nav-link": {
                    "color": "rgba(255,255,255,0.7)",
                    "font-size": "14px",
                    "text-align": "left",
                    "margin": "2px 0",
                    "padding": "10px 15px",
                    "border-radius": "10px",
                },
                "nav-link-selected": {
                    "background": "linear-gradient(135deg, rgba(102,126,234,0.3), rgba(118,75,162,0.3))",
                    "color": "white",
                },
            }
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<hr style='border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
        
        # Logout button
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.role = None
            st.rerun()
        
        # Theme toggle
        theme = st.toggle("🌙 Dark Mode", value=st.session_state.theme == 'dark')
        if theme and st.session_state.theme == 'light':
            st.session_state.theme = 'dark'
            st.rerun()
        elif not theme and st.session_state.theme == 'dark':
            st.session_state.theme = 'light'
            st.rerun()
    
    return selected

# Dashboard page
def dashboard_page():
    st.markdown("<h2 style='margin-bottom: 30px;'>📊 Dashboard</h2>", unsafe_allow_html=True)
    
    # Get real data from database
    session = get_db_connection()
    try:
        # Get counts
        product_count = session.execute(text("SELECT COUNT(*) FROM products WHERE is_active = true")).scalar()
        supplier_count = session.execute(text("SELECT COUNT(*) FROM suppliers WHERE is_active = true")).scalar()
        customer_count = session.execute(text("SELECT COUNT(*) FROM customers WHERE is_active = true")).scalar()
        user_count = session.execute(text("SELECT COUNT(*) FROM users WHERE is_active = true")).scalar()
        
        # Low stock products
        low_stock = session.execute(text("""
            SELECT COUNT(*) FROM products 
            WHERE current_stock <= min_stock_level AND is_active = true
        """)).scalar()
        
        # Total stock value
        total_stock_value = session.execute(text("""
            SELECT COALESCE(SUM(current_stock * unit_price), 0) 
            FROM products WHERE is_active = true
        """)).scalar()
        
        # Recent transactions
        recent_transactions = session.execute(text("""
            SELECT 
                st.created_at,
                p.name as product_name,
                st.transaction_type,
                st.quantity,
                u.username as user_name
            FROM stock_transactions st
            JOIN products p ON st.product_id = p.id
            LEFT JOIN users u ON st.created_by = u.id
            ORDER BY st.created_at DESC
            LIMIT 10
        """)).fetchall()
        
        # Production stats (mock for demo)
        production_today = 1245
        production_month = 34200
        machine_utilization = 76
        
        # Sales stats (mock)
        sales_today = 2450.50
        monthly_revenue = 48200.00
        outstanding = 12500.00
        
        # Quality stats (mock)
        water_status = "Passed"
        failed_batches = 3
        approved_batches = 87
        
        # Delivery stats (mock)
        vehicles_out = 5
        deliveries_completed = 12
        
    finally:
        session.close()
    
    # KPI Cards - Row 1
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric(
            label="📦 Total Products",
            value=product_count,
            delta="Active",
            delta_color="normal"
        )
    
    with col2:
        st.metric(
            label="🏭 Suppliers",
            value=supplier_count,
            delta="Active",
            delta_color="normal"
        )
    
    with col3:
        st.metric(
            label="👥 Customers",
            value=customer_count,
            delta="Active",
            delta_color="normal"
        )
    
    with col4:
        st.metric(
            label="👤 Users",
            value=user_count,
            delta="Active",
            delta_color="normal"
        )
    
    with col5:
        st.metric(
            label="⚠️ Low Stock Alerts",
            value=low_stock,
            delta="Needs attention",
            delta_color="inverse" if low_stock > 0 else "normal"
        )
    
    with col6:
        st.metric(
            label="💰 Stock Value",
            value=f"${total_stock_value:,.2f}",
            delta="Total inventory",
            delta_color="normal"
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # KPI Cards - Row 2 (Production, Sales, Quality, Delivery)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">⚙️ Production Today</div>
            <div class="kpi-value">{production_today:,}</div>
            <div style="display: flex; gap: 15px; margin-top: 5px;">
                <span style="font-size: 12px; color: #888;">Units</span>
                <span style="font-size: 12px; color: #28a745;">↑ 12%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">📈 Machine Utilization</div>
            <div class="kpi-value">{machine_utilization}%</div>
            <div style="width: 100%; height: 6px; background: #e9ecef; border-radius: 3px; margin-top: 8px;">
                <div style="width: {machine_utilization}%; height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); border-radius: 3px;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">💰 Today's Sales</div>
            <div class="kpi-value">${sales_today:,.2f}</div>
            <div style="display: flex; gap: 15px; margin-top: 5px;">
                <span style="font-size: 12px; color: #888;">Revenue</span>
                <span style="font-size: 12px; color: #28a745;">↑ 8%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">🧪 Quality Status</div>
            <div class="kpi-value" style="color: #28a745;">
                <span style="font-size: 20px;">✅</span> {water_status}
            </div>
            <div style="display: flex; gap: 15px; margin-top: 5px;">
                <span style="font-size: 12px; color: #888;">Failed: {failed_batches}</span>
                <span style="font-size: 12px; color: #28a745;">Approved: {approved_batches}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Charts Row
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("<h4>📊 Production Trends</h4>", unsafe_allow_html=True)
        # Sample production data
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        production_data = [1200, 1900, 1500, 2100, 1800, 1400, 1600]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=days,
            y=production_data,
            mode='lines+markers',
            line=dict(color='#667eea', width=3),
            marker=dict(size=8, color='#667eea'),
            fill='tozeroy',
            fillcolor='rgba(102, 126, 234, 0.1)',
            name='Production'
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            xaxis=dict(gridcolor='rgba(0,0,0,0.05)'),
            yaxis=dict(gridcolor='rgba(0,0,0,0.05)')
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("<h4>💰 Sales Overview</h4>", unsafe_allow_html=True)
        # Sample sales data
        sales_data = [5000, 7500, 6000, 9000, 8500, 5500, 7000]
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=days,
            y=sales_data,
            marker=dict(
                color='#f5576c',
                opacity=0.7,
                line=dict(color='#f5576c', width=2)
            ),
            name='Revenue'
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            xaxis=dict(gridcolor='rgba(0,0,0,0.05)'),
            yaxis=dict(gridcolor='rgba(0,0,0,0.05)')
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Recent Transactions
    st.markdown("<br><h4>🔄 Recent Stock Transactions</h4>", unsafe_allow_html=True)
    
    if recent_transactions:
        df = pd.DataFrame(recent_transactions, columns=['Date', 'Product', 'Type', 'Quantity', 'User'])
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d %H:%M')
        
        # Color code transaction types
        def color_type(val):
            if val == 'IN':
                return 'background-color: #d4edda; color: #155724;'
            elif val == 'OUT':
                return 'background-color: #f8d7da; color: #721c24;'
            else:
                return 'background-color: #fff3cd; color: #856404;'
        
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Type": st.column_config.TextColumn("Type", width="small"),
                "Quantity": st.column_config.NumberColumn("Qty", width="small"),
            }
        )
    else:
        st.info("No recent transactions found")

# User Management page
def user_management_page():
    st.markdown("<h2>👤 User Management</h2>", unsafe_allow_html=True)
    
    # Add user button
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("➕ Add User", use_container_width=True):
            st.session_state.show_add_user = True
    
    # Add user form
    if st.session_state.get('show_add_user', False):
        with st.expander("Add New User", expanded=True):
            with st.form("add_user_form"):
                col1, col2 = st.columns(2)
                with col1:
                    username = st.text_input("Username*")
                    email = st.text_input("Email*")
                    first_name = st.text_input("First Name")
                    last_name = st.text_input("Last Name")
                with col2:
                    password = st.text_input("Password*", type="password")
                    phone = st.text_input("Phone")
                    
                    # Get roles
                    session = get_db_connection()
                    roles = session.execute(text("SELECT id, name FROM roles WHERE is_active = true")).fetchall()
                    session.close()
                    
                    role_options = {r.name: r.id for r in roles}
                    selected_role = st.selectbox("Role", list(role_options.keys()))
                    is_active = st.checkbox("Active", value=True)
                    is_superuser = st.checkbox("Superuser (Full Access)", value=False)
                
                submitted = st.form_submit_button("Create User")
                if submitted:
                    if username and email and password:
                        session = get_db_connection()
                        try:
                            hashed_pw = hash_password(password)
                            query = text("""
                                INSERT INTO users 
                                (username, email, password_hash, first_name, last_name, phone, 
                                 role_id, is_active, is_superuser, created_at)
                                VALUES 
                                (:username, :email, :password_hash, :first_name, :last_name, :phone,
                                 :role_id, :is_active, :is_superuser, NOW())
                            """)
                            session.execute(query, {
                                "username": username,
                                "email": email,
                                "password_hash": hashed_pw,
                                "first_name": first_name,
                                "last_name": last_name,
                                "phone": phone,
                                "role_id": role_options[selected_role],
                                "is_active": is_active,
                                "is_superuser": is_superuser
                            })
                            session.commit()
                            st.success("User created successfully!")
                            st.session_state.show_add_user = False
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error creating user: {str(e)}")
                        finally:
                            session.close()
                    else:
                        st.warning("Please fill in all required fields (*)")
    
    # Display users
    session = get_db_connection()
    try:
        users = session.execute(text("""
            SELECT 
                u.id, u.username, u.email, u.first_name, u.last_name, u.phone,
                u.is_active, u.is_superuser, u.last_login, u.created_at,
                r.name as role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            ORDER BY u.created_at DESC
        """)).fetchall()
    finally:
        session.close()
    
    if users:
        df = pd.DataFrame(users, columns=[
            'ID', 'Username', 'Email', 'First Name', 'Last Name', 'Phone',
            'Active', 'Superuser', 'Last Login', 'Created At', 'Role'
        ])
        
        # Format dates
        df['Last Login'] = pd.to_datetime(df['Last Login']).dt.strftime('%Y-%m-%d %H:%M') if df['Last Login'].any() else 'Never'
        df['Created At'] = pd.to_datetime(df['Created At']).dt.strftime('%Y-%m-%d')
        
        # Status badges
        df['Status'] = df['Active'].apply(lambda x: '✅ Active' if x else '❌ Inactive')
        
        # Display table with column configuration
        st.dataframe(
            df[['Username', 'Email', 'Role', 'Status', 'Last Login', 'Created At']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Username": st.column_config.TextColumn("Username", width="small"),
                "Email": st.column_config.TextColumn("Email"),
                "Role": st.column_config.TextColumn("Role", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Last Login": st.column_config.TextColumn("Last Login", width="small"),
                "Created At": st.column_config.TextColumn("Created", width="small"),
            }
        )
    else:
        st.info("No users found")

# Products page
def products_page():
    st.markdown("<h2>📦 Products Management</h2>", unsafe_allow_html=True)
    
    # Product filters
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        search = st.text_input("🔍 Search Products", placeholder="Search by name or code...")
    with col2:
        session = get_db_connection()
        categories = session.execute(text("SELECT id, name FROM product_categories WHERE is_active = true")).fetchall()
        session.close()
        category_options = [""] + [c.name for c in categories]
        category_filter = st.selectbox("Category", category_options)
    with col3:
        show_inactive = st.checkbox("Show Inactive")
    
    # Add product button
    if st.button("➕ Add Product", use_container_width=True):
        st.session_state.show_add_product = True
    
    # Add product form
    if st.session_state.get('show_add_product', False):
        with st.expander("Add New Product", expanded=True):
            with st.form("add_product_form"):
                col1, col2 = st.columns(2)
                with col1:
                    code = st.text_input("Product Code*")
                    name = st.text_input("Product Name*")
                    description = st.text_area("Description")
                    category = st.selectbox("Category", [""] + [c.name for c in categories])
                with col2:
                    unit = st.selectbox("Unit", ["piece", "kg", "liter", "bottle", "case", "pallet"])
                    unit_price = st.number_input("Unit Price ($)", min_value=0.0, step=0.01)
                    cost_price = st.number_input("Cost Price ($)", min_value=0.0, step=0.01)
                    min_stock = st.number_input("Minimum Stock", min_value=0, value=10)
                    max_stock = st.number_input("Maximum Stock", min_value=0, value=1000)
                    barcode = st.text_input("Barcode")
                
                submitted = st.form_submit_button("Create Product")
                if submitted:
                    if code and name:
                        session = get_db_connection()
                        try:
                            # Get category ID
                            cat_id = None
                            if category:
                                cat_result = session.execute(
                                    text("SELECT id FROM product_categories WHERE name = :name"),
                                    {"name": category}
                                ).fetchone()
                                if cat_result:
                                    cat_id = cat_result.id
                            
                            query = text("""
                                INSERT INTO products 
                                (code, name, description, category_id, unit, unit_price, cost_price,
                                 min_stock_level, max_stock_level, barcode, is_active, created_at)
                                VALUES 
                                (:code, :name, :description, :category_id, :unit, :unit_price, :cost_price,
                                 :min_stock_level, :max_stock_level, :barcode, true, NOW())
                            """)
                            session.execute(query, {
                                "code": code,
                                "name": name,
                                "description": description,
                                "category_id": cat_id,
                                "unit": unit,
                                "unit_price": unit_price,
                                "cost_price": cost_price,
                                "min_stock_level": min_stock,
                                "max_stock_level": max_stock,
                                "barcode": barcode
                            })
                            session.commit()
                            st.success("Product created successfully!")
                            st.session_state.show_add_product = False
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error creating product: {str(e)}")
                        finally:
                            session.close()
                    else:
                        st.warning("Please fill in all required fields (*)")
    
    # Get products
    session = get_db_connection()
    try:
        query = """
            SELECT 
                p.id, p.code, p.name, p.description, p.unit, p.unit_price, p.cost_price,
                p.current_stock, p.min_stock_level, p.max_stock_level, p.is_active,
                p.barcode, pc.name as category_name
            FROM products p
            LEFT JOIN product_categories pc ON p.category_id = pc.id
            WHERE 1=1
        """
        params = {}
        
        if search:
            query += " AND (p.name ILIKE :search OR p.code ILIKE :search)"
            params["search"] = f"%{search}%"
        
        if category_filter:
            query += " AND pc.name = :category"
            params["category"] = category_filter
        
        if not show_inactive:
            query += " AND p.is_active = true"
        
        query += " ORDER BY p.name"
        
        products = session.execute(text(query), params).fetchall()
    finally:
        session.close()
    
    if products:
        df = pd.DataFrame(products, columns=[
            'ID', 'Code', 'Name', 'Description', 'Unit', 'Unit Price', 'Cost Price',
            'Stock', 'Min Stock', 'Max Stock', 'Active', 'Barcode', 'Category'
        ])
        
        # Add status column
        df['Status'] = df.apply(
            lambda row: '🟢 In Stock' if row['Stock'] > row['Min Stock'] 
            else '🟡 Low Stock' if row['Stock'] > 0 
            else '🔴 Out of Stock',
            axis=1
        )
        
        # Format currency
        df['Unit Price'] = df['Unit Price'].apply(lambda x: f"${x:,.2f}" if x else "$0.00")
        df['Cost Price'] = df['Cost Price'].apply(lambda x: f"${x:,.2f}" if x else "$0.00")
        
        st.dataframe(
            df[['Code', 'Name', 'Category', 'Stock', 'Unit Price', 'Status', 'Active']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Code": st.column_config.TextColumn("Code", width="small"),
                "Name": st.column_config.TextColumn("Product Name"),
                "Category": st.column_config.TextColumn("Category", width="small"),
                "Stock": st.column_config.NumberColumn("Stock", width="small"),
                "Unit Price": st.column_config.TextColumn("Unit Price", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Active": st.column_config.CheckboxColumn("Active", width="small"),
            }
        )
    else:
        st.info("No products found")

# Suppliers page
def suppliers_page():
    st.markdown("<h2>🏭 Supplier Management</h2>", unsafe_allow_html=True)
    
    # Add supplier
    if st.button("➕ Add Supplier", use_container_width=True):
        st.session_state.show_add_supplier = True
    
    if st.session_state.get('show_add_supplier', False):
        with st.expander("Add New Supplier", expanded=True):
            with st.form("add_supplier_form"):
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input("Company Name*")
                    contact_person = st.text_input("Contact Person")
                    email = st.text_input("Email")
                    phone = st.text_input("Phone")
                with col2:
                    address = st.text_area("Address")
                    tax_number = st.text_input("Tax/VAT Number")
                    payment_terms = st.number_input("Payment Terms (days)", min_value=0, value=30)
                
                submitted = st.form_submit_button("Create Supplier")
                if submitted:
                    if name:
                        session = get_db_connection()
                        try:
                            query = text("""
                                INSERT INTO suppliers 
                                (name, contact_person, email, phone, address, tax_number, payment_terms, is_active, created_at)
                                VALUES 
                                (:name, :contact_person, :email, :phone, :address, :tax_number, :payment_terms, true, NOW())
                            """)
                            session.execute(query, {
                                "name": name,
                                "contact_person": contact_person,
                                "email": email,
                                "phone": phone,
                                "address": address,
                                "tax_number": tax_number,
                                "payment_terms": payment_terms
                            })
                            session.commit()
                            st.success("Supplier created successfully!")
                            st.session_state.show_add_supplier = False
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error creating supplier: {str(e)}")
                        finally:
                            session.close()
                    else:
                        st.warning("Company name is required")
    
    # Get suppliers
    session = get_db_connection()
    try:
        suppliers = session.execute(text("""
            SELECT id, name, contact_person, email, phone, address, tax_number, payment_terms, is_active
            FROM suppliers
            WHERE is_active = true
            ORDER BY name
        """)).fetchall()
    finally:
        session.close()
    
    if suppliers:
        df = pd.DataFrame(suppliers, columns=['ID', 'Name', 'Contact', 'Email', 'Phone', 'Address', 'Tax', 'Payment Terms', 'Active'])
        df['Status'] = df['Active'].apply(lambda x: '✅ Active' if x else '❌ Inactive')
        
        st.dataframe(
            df[['Name', 'Contact', 'Email', 'Phone', 'Payment Terms', 'Status']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Name": st.column_config.TextColumn("Company Name"),
                "Contact": st.column_config.TextColumn("Contact Person"),
                "Email": st.column_config.TextColumn("Email"),
                "Phone": st.column_config.TextColumn("Phone", width="small"),
                "Payment Terms": st.column_config.NumberColumn("Terms (days)", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
            }
        )
    else:
        st.info("No suppliers found")

# Customers page
def customers_page():
    st.markdown("<h2>👥 Customer Management</h2>", unsafe_allow_html=True)
    
    # Add customer
    if st.button("➕ Add Customer", use_container_width=True):
        st.session_state.show_add_customer = True
    
    if st.session_state.get('show_add_customer', False):
        with st.expander("Add New Customer", expanded=True):
            with st.form("add_customer_form"):
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input("Customer Name*")
                    contact_person = st.text_input("Contact Person")
                    email = st.text_input("Email")
                    phone = st.text_input("Phone")
                with col2:
                    address = st.text_area("Address")
                    tax_number = st.text_input("Tax/VAT Number")
                    credit_limit = st.number_input("Credit Limit ($)", min_value=0.0, step=100.0)
                
                submitted = st.form_submit_button("Create Customer")
                if submitted:
                    if name:
                        session = get_db_connection()
                        try:
                            query = text("""
                                INSERT INTO customers 
                                (name, contact_person, email, phone, address, tax_number, credit_limit, is_active, created_at)
                                VALUES 
                                (:name, :contact_person, :email, :phone, :address, :tax_number, :credit_limit, true, NOW())
                            """)
                            session.execute(query, {
                                "name": name,
                                "contact_person": contact_person,
                                "email": email,
                                "phone": phone,
                                "address": address,
                                "tax_number": tax_number,
                                "credit_limit": credit_limit
                            })
                            session.commit()
                            st.success("Customer created successfully!")
                            st.session_state.show_add_customer = False
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error creating customer: {str(e)}")
                        finally:
                            session.close()
                    else:
                        st.warning("Customer name is required")
    
    # Get customers
    session = get_db_connection()
    try:
        customers = session.execute(text("""
            SELECT id, name, contact_person, email, phone, address, tax_number, credit_limit, current_balance, is_active
            FROM customers
            WHERE is_active = true
            ORDER BY name
        """)).fetchall()
    finally:
        session.close()
    
    if customers:
        df = pd.DataFrame(customers, columns=['ID', 'Name', 'Contact', 'Email', 'Phone', 'Address', 'Tax', 'Credit Limit', 'Balance', 'Active'])
        df['Status'] = df['Active'].apply(lambda x: '✅ Active' if x else '❌ Inactive')
        df['Credit Limit'] = df['Credit Limit'].apply(lambda x: f"${x:,.2f}")
        df['Balance'] = df['Balance'].apply(lambda x: f"${x:,.2f}")
        
        st.dataframe(
            df[['Name', 'Contact', 'Email', 'Phone', 'Credit Limit', 'Balance', 'Status']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Name": st.column_config.TextColumn("Customer Name"),
                "Contact": st.column_config.TextColumn("Contact Person"),
                "Email": st.column_config.TextColumn("Email"),
                "Phone": st.column_config.TextColumn("Phone", width="small"),
                "Credit Limit": st.column_config.TextColumn("Credit Limit", width="small"),
                "Balance": st.column_config.TextColumn("Balance", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
            }
        )
    else:
        st.info("No customers found")

# Main app
def main():
    # Initialize session
    init_session_state()
    
    # Apply custom CSS
    apply_custom_css()
    
    # Check authentication
    if not st.session_state.authenticated:
        login_page()
        return
    
    # Sidebar navigation
    selected_page = sidebar_navigation()
    
    # Page routing
    if selected_page == "Dashboard":
        dashboard_page()
    elif selected_page == "User Management":
        user_management_page()
    elif selected_page == "Products":
        products_page()
    elif selected_page == "Suppliers":
        suppliers_page()
    elif selected_page == "Customers":
        customers_page()
    elif selected_page == "Inventory":
        st.markdown("<h2>📦 Inventory Management</h2>", unsafe_allow_html=True)
        st.info("Inventory module coming soon...")
    elif selected_page == "Procurement":
        st.markdown("<h2>🛒 Procurement Management</h2>", unsafe_allow_html=True)
        st.info("Procurement module coming soon...")
    elif selected_page == "Production":
        st.markdown("<h2>🏭 Production Management</h2>", unsafe_allow_html=True)
        st.info("Production module coming soon...")
    elif selected_page == "Quality Control":
        st.markdown("<h2>🧪 Quality Control</h2>", unsafe_allow_html=True)
        st.info("Quality Control module coming soon...")
    elif selected_page == "Sales":
        st.markdown("<h2>📊 Sales Management</h2>", unsafe_allow_html=True)
        st.info("Sales module coming soon...")
    elif selected_page == "Finance":
        st.markdown("<h2>💰 Finance</h2>", unsafe_allow_html=True)
        st.info("Finance module coming soon...")
    elif selected_page == "Reports":
        st.markdown("<h2>📊 Reports</h2>", unsafe_allow_html=True)
        st.info("Reports module coming soon...")
    elif selected_page == "Settings":
        st.markdown("<h2>⚙️ Settings</h2>", unsafe_allow_html=True)
        st.info("Settings module coming soon...")

if __name__ == "__main__":
    main()