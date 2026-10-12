import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import hashlib
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MUST BE THE FIRST STREAMLIT COMMAND
st.set_page_config(
    page_title="Amigoz Water Distilling Company - ERP",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
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

def create_default_admin():
    """Create default Super Admin user if doesn't exist"""
    session = get_db_connection()
    if not session:
        return False
    
    try:
        # Check if users table exists
        inspector = inspect(session.bind)
        if not inspector.has_table('users'):
            return False
        
        # Check if admin exists
        result = session.execute(
            text("SELECT id FROM users WHERE LOWER(username) = :username"),
            {"username": "admin"}
        ).fetchone()
        
        if not result:
            # Insert Super Admin user
            admin_password = hash_password("cpsb123")
            
            # Get admin role
            admin_role = session.execute(
                text("SELECT id FROM roles WHERE LOWER(name) = :role"),
                {"role": "administrator"}
            ).fetchone()
            
            role_id = admin_role[0] if admin_role else None
            
            session.execute(
                text("""
                    INSERT INTO users (username, email, password_hash, first_name, last_name, role_id, is_active, is_superuser, created_at)
                    VALUES (:username, :email, :password_hash, :first_name, :last_name, :role_id, :is_active, :is_superuser, NOW())
                """),
                {
                    "username": "admin",
                    "email": "admin@amigoz.com",
                    "password_hash": admin_password,
                    "first_name": "System",
                    "last_name": "Administrator",
                    "role_id": role_id,
                    "is_active": True,
                    "is_superuser": True
                }
            )
            session.commit()
            session.close()
            return True
        else:
            session.close()
            return True
            
    except Exception as e:
        print(f"Error creating admin user: {e}")
        session.rollback()
        session.close()
        return False

# =========================================================
# DATABASE CONNECTION
# =========================================================
def get_db_connection():
    """Get database connection - works with PostgreSQL or SQLite"""
    try:
        # Try to get DATABASE_URL from secrets or environment
        database_url = None
        
        try:
            database_url = st.secrets.get("DATABASE_URL")
        except:
            pass
        
        if not database_url:
            database_url = os.getenv("DATABASE_URL")
        
        if database_url:
            # Use PostgreSQL
            engine = create_engine(database_url, pool_pre_ping=True)
            Session = sessionmaker(bind=engine)
            return Session()
        else:
            # Use SQLite for local development
            engine = create_engine('sqlite:///wb_erp.db', connect_args={'check_same_thread': False})
            Session = sessionmaker(bind=engine)
            return Session()
            
    except Exception as e:
        st.error(f"❌ Database connection error: {str(e)}")
        return None

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
        'db_initialized': False
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
        .main > div {
            padding: 0 1rem;
        }
        
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
        
        .dark-theme .metric-card {
            background: #1e1e2f;
            color: #e9ecef;
            border-left-color: #764ba2;
        }
        
        .dark-theme .login-container {
            background: #1e1e2f;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        
        .dark-theme .login-title h2 {
            color: #e9ecef;
        }
        
        .dark-theme .login-title p {
            color: #adb5bd;
        }
        
        .stButton button {
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.3s;
            width: 100%;
        }
        
        .stButton button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# LOGIN PAGE - PASSWORD BYPASS ACTIVATED
# =========================================================
def login_page():
    st.markdown("""
    <div class="login-container">
        <div class="login-title">
            <h2>💧 Amigoz Water Distilling</h2>
            <p>Enterprise Resource Planning System</p>
            <p style="color: #ff6b6b; font-size: 12px;">⚠️ Password bypass is ACTIVE - for testing only</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            # Auto-create admin on login page load
            if not st.session_state.db_initialized:
                with st.spinner("🔧 Checking database..."):
                    if create_default_admin():
                        st.session_state.db_initialized = True
                        st.success("✅ Database initialized with default admin user!")
            
            username = st.text_input("Username", placeholder="Enter your username", key="login_username")
            password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")
            
            # 🔓🔓🔓 PASSWORD BYPASS - ACCEPT ANY PASSWORD 🔓🔓🔓
            if st.button("🔐 Sign In (Any Password)", key="login_button", use_container_width=True):
                if username:
                    # 🔓 BYPASS - Ignore password, just check if user exists
                    session = get_db_connection()
                    if session:
                        try:
                            # Check if users table exists
                            inspector = inspect(session.bind)
                            if not inspector.has_table('users'):
                                # If no users table, create bypass login
                                st.session_state.authenticated = True
                                st.session_state.user = username
                                st.session_state.user_id = 1
                                st.session_state.role = "Administrator"
                                st.session_state.full_name = username
                                st.success("✅ Login successful! (Bypass - No DB)")
                                st.rerun()
                                return
                            
                            # Query user
                            query = text("""
                                SELECT u.*, r.name as role_name 
                                FROM users u
                                LEFT JOIN roles r ON u.role_id = r.id
                                WHERE LOWER(u.username) = LOWER(:username) AND u.is_active = true
                            """)
                            result = session.execute(query, {"username": username}).fetchone()
                            
                            if result:
                                # 🔓 ACCEPT ANY PASSWORD
                                st.session_state.authenticated = True
                                st.session_state.user = result.username
                                st.session_state.user_id = result.id
                                st.session_state.role = result.role_name or "User"
                                st.session_state.full_name = f"{result.first_name} {result.last_name}".strip() or result.username
                                
                                # Update last login
                                try:
                                    update_query = text("UPDATE users SET last_login = NOW() WHERE id = :user_id")
                                    session.execute(update_query, {"user_id": result.id})
                                    session.commit()
                                except:
                                    pass
                                
                                st.success("✅ Login successful! (Password bypassed)")
                                st.rerun()
                            else:
                                # User not found - create temporary session
                                st.session_state.authenticated = True
                                st.session_state.user = username
                                st.session_state.user_id = 1
                                st.session_state.role = "Administrator"
                                st.session_state.full_name = username
                                st.success("✅ Login successful! (Bypass - User created)")
                                st.rerun()
                        except Exception as e:
                            # If any error, bypass anyway
                            st.session_state.authenticated = True
                            st.session_state.user = username or "admin"
                            st.session_state.user_id = 1
                            st.session_state.role = "Administrator"
                            st.session_state.full_name = username or "Admin"
                            st.success("✅ Login successful! (Error bypass)")
                            st.rerun()
                        finally:
                            session.close()
                    else:
                        # No database - direct bypass
                        st.session_state.authenticated = True
                        st.session_state.user = username
                        st.session_state.user_id = 1
                        st.session_state.role = "Administrator"
                        st.session_state.full_name = username
                        st.success("✅ Login successful! (No DB)")
                        st.rerun()
                else:
                    st.warning("⚠️ Please enter a username")
            
            # 🔓🔓🔓 DIRECT BYPASS - Skip everything 🔓🔓🔓
            if st.button("🚪 Quick Bypass (No Login)", key="bypass_button", use_container_width=True):
                st.session_state.authenticated = True
                st.session_state.user = "admin"
                st.session_state.user_id = 1
                st.session_state.role = "Administrator"
                st.session_state.full_name = "System Administrator"
                st.success("✅ Bypass login successful!")
                st.rerun()
            
            st.markdown("""
            <p style="text-align: center; color: #888; font-size: 12px; margin-top: 20px;">
                🔓 Password check is disabled for testing<br>
                Any username works, any password works
            </p>
            """, unsafe_allow_html=True)

# =========================================================
# SIDEBAR NAVIGATION
# =========================================================
def sidebar_navigation():
    # =========================================================
    # PURPLE SIDEBAR STYLING
    # =========================================================
    st.markdown("""
    <style>
        /* Sidebar background - Purple gradient */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #4c1d95 0%, #5b21b6 50%, #6d28d9 100%) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.1) !important;
        }
        
        /* Sidebar content padding */
        section[data-testid="stSidebar"] .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
        }
        
        /* All text in sidebar - white */
        section[data-testid="stSidebar"] .stMarkdown,
        section[data-testid="stSidebar"] .stMarkdown p,
        section[data-testid="stSidebar"] .stMarkdown h1,
        section[data-testid="stSidebar"] .stMarkdown h2,
        section[data-testid="stSidebar"] .stMarkdown h3,
        section[data-testid="stSidebar"] .stMarkdown h4,
        section[data-testid="stSidebar"] .stMarkdown h5,
        section[data-testid="stSidebar"] .stMarkdown h6 {
            color: white !important;
        }
        
        /* Sidebar buttons - purple theme */
        section[data-testid="stSidebar"] .stButton button {
            background: rgba(255, 255, 255, 0.1) !important;
            color: white !important;
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            border-radius: 10px !important;
            font-weight: 500 !important;
            transition: all 0.3s ease !important;
            text-align: left !important;
            padding: 10px 15px !important;
            margin-bottom: 4px !important;
        }
        
        section[data-testid="stSidebar"] .stButton button:hover {
            background: rgba(255, 255, 255, 0.2) !important;
            border-color: rgba(255, 255, 255, 0.3) !important;
            transform: translateX(4px) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
        }
        
        /* Logout button - special styling */
        section[data-testid="stSidebar"] .stButton button[kind="secondary"] {
            background: linear-gradient(135deg, #ef4444, #dc2626) !important;
            border: none !important;
        }
        
        section[data-testid="stSidebar"] .stButton button[kind="secondary"]:hover {
            background: linear-gradient(135deg, #dc2626, #b91c1c) !important;
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4) !important;
        }
        
        /* Sidebar dividers - subtle white */
        section[data-testid="stSidebar"] hr {
            border-color: rgba(255, 255, 255, 0.15) !important;
            margin: 12px 0 !important;
        }
        
        /* Sidebar scrollbar - purple themed */
        section[data-testid="stSidebar"] ::-webkit-scrollbar {
            width: 6px !important;
        }
        
        section[data-testid="stSidebar"] ::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.05) !important;
        }
        
        section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.3) !important;
            border-radius: 3px !important;
        }
        
        section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.5) !important;
        }
        
        /* User profile card - glassmorphism effect */
        .user-profile-card {
            background: rgba(255, 255, 255, 0.1) !important;
            backdrop-filter: blur(10px) !important;
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            border-radius: 12px !important;
        }
        
        /* Header card styling */
        .sidebar-header {
            background: rgba(255, 255, 255, 0.08) !important;
            backdrop-filter: blur(10px) !important;
            border-radius: 12px !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-header" style="padding: 20px 0; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.15);">
            <h3 style="color: white; margin: 0;">💧 Amigoz ERP</h3>
            <p style="color: rgba(255,255,255,0.7); font-size: 12px; margin: 5px 0 0;">Version 1.0.0</p>
            <p style="color: #fbbf24; font-size: 10px; margin: 5px 0 0;">🔓 Bypass Mode</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.session_state.authenticated:
            st.markdown(f"""
            <div class="user-profile-card" style="padding: 15px; margin-bottom: 20px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="width: 42px; height: 42px; background: linear-gradient(135deg, #fbbf24, #f59e0b); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 18px; box-shadow: 0 2px 8px rgba(251, 191, 36, 0.3);">
                        {st.session_state.full_name[0].upper() if st.session_state.full_name else 'U'}
                    </div>
                    <div style="flex: 1;">
                        <div style="color: white; font-weight: 600; font-size: 14px;">{st.session_state.full_name}</div>
                        <div style="color: rgba(255,255,255,0.7); font-size: 12px;">{st.session_state.role or 'No Role'}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Navigation
        st.markdown("""
        <div style="
            color: white; 
            font-size: 14px; 
            font-weight: 600; 
            margin-bottom: 12px;
            padding-left: 5px;
            border-left: 3px solid #fbbf24;
            padding: 4px 0 4px 12px;
        ">
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
            "Sales": "💰",
            "Finance": "💳",
            "Reports": "📈",
            "Settings": "⚙️"
        }
        
        for page_name, icon in pages.items():
            # Highlight current page
            is_current = st.session_state.page == page_name
            button_label = f"{icon} {page_name}"
            
            if is_current:
                button_label = f"▶ {icon} {page_name}"
            
            if st.button(button_label, key=f"nav_{page_name}", use_container_width=True):
                st.session_state.page = page_name
                st.rerun()
        
        st.markdown("---")
        
        # Theme toggle
        col1, col2 = st.columns([1, 3])
        with col1:
            theme_icon = "🌙" if st.session_state.theme == 'light' else "☀️"
        with col2:
            if st.button(f"{theme_icon} Toggle Theme", key="theme_toggle", use_container_width=True):
                st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'
                st.rerun()
        
        st.markdown("---")
        
        if st.button("🚪 Logout", key="logout_button", use_container_width=True):
            for key in ['authenticated', 'user', 'user_id', 'role', 'full_name']:
                st.session_state[key] = None if key != 'authenticated' else False
            st.rerun()
        
        # =========================================================
        # FOOTER
        # =========================================================
        st.markdown("""
        <div style="
            text-align: center;
            margin-top: 20px;
            padding-top: 12px;
            border-top: 1px solid rgba(255,255,255,0.1);
            font-size: 10px;
            color: rgba(255,255,255,0.5);
        ">
            Amigoz ERP System<br>
            © 2026 Amigoz Water Distilling Co.
        </div>
        """, unsafe_allow_html=True)
    
    return st.session_state.page
# =========================================================
# DASHBOARD
# =========================================================
def dashboard_page():
    # =========================================================
    # LIGHT BLUE THEME STYLING
    # =========================================================
    st.markdown("""
    <style>
        /* Main app background - Light blue gradient */
        .stApp {
            background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important;
        }
        
        /* Main content container */
        .main > div {
            background: transparent !important;
        }
        
        .block-container {
            background: transparent !important;
            padding-top: 2rem !important;
        }
        
        /* Metric cards - Light blue glassmorphism */
        div[data-testid="metric-container"] {
            background: linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%) !important;
            border: 1px solid #bae6fd !important;
            border-radius: 14px !important;
            padding: 1.25rem !important;
            box-shadow: 0 4px 12px rgba(14, 165, 233, 0.1) !important;
            transition: all 0.3s ease !important;
        }
        
        div[data-testid="metric-container"]:hover {
            box-shadow: 0 8px 20px rgba(14, 165, 233, 0.2) !important;
            transform: translateY(-3px) !important;
            border-color: #7dd3fc !important;
        }
        
        div[data-testid="metric-container"] label {
            color: #0369a1 !important;
            font-weight: 600 !important;
        }
        
        div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
            color: #0c4a6e !important;
            font-weight: 700 !important;
        }
        
        /* Headers - Dark blue */
        h1, h2, h3, h4, h5, h6 {
            color: #0c4a6e !important;
        }
        
        /* Warning/Info/Success boxes - Light blue theme */
        .stAlert {
            border-radius: 10px !important;
            border-left: 4px solid #0ea5e9 !important;
        }
        
        /* Plotly charts background */
        .js-plotly-plot .plotly .main-svg {
            background: transparent !important;
        }
        
        /* Success message */
        div[data-testid="stNotification"] {
            background: linear-gradient(135deg, #ecfeff 0%, #cffafe 100%) !important;
            border-radius: 12px !important;
            border-left: 4px solid #06b6d4 !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # =========================================================
    # WELCOME MESSAGE (MOVED TO TOP - REPLACES HEADER)
    # =========================================================
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 50%, #7dd3fc 100%);
        padding: 24px 28px;
        border-radius: 16px;
        border-left: 6px solid #0284c7;
        margin-bottom: 24px;
        box-shadow: 0 6px 16px rgba(14, 165, 233, 0.2);
    ">
        <div style="display: flex; align-items: center; gap: 16px;">
            <span style="font-size: 36px;">✅</span>
            <div>
                <h2 style="color: #0c4a6e; margin: 0; font-weight: 700; font-size: 24px;">
                    Welcome to Amigoz Water Distilling Company ERP System
                </h2>
                <p style="color: #0369a1; margin: 6px 0 0; font-size: 15px;">
                    Your all-in-one solution for managing products, suppliers, customers, and more.
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show bypass warning
    st.warning("🔓 Password bypass is active - This is for testing only!")
    
    session = get_db_connection()
    product_count = 0
    if session:
        try:
            inspector = inspect(session.bind)
            if inspector.has_table('products'):
                result = session.execute(text("SELECT COUNT(*) FROM products WHERE is_active = true")).scalar()
                product_count = result if result else 0
        except:
            pass
        finally:
            session.close()
    
    # =========================================================
    # KPI METRICS
    # =========================================================
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📦 Products", product_count or 45)
    with col2:
        st.metric("🏭 Suppliers", 12)
    with col3:
        st.metric("👥 Customers", 89)
    with col4:
        st.metric("👤 Users", 5)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # =========================================================
    # CHARTS ROW
    # =========================================================
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div style="
            background: white;
            padding: 20px;
            border-radius: 14px;
            border: 1px solid #bae6fd;
            box-shadow: 0 4px 12px rgba(14, 165, 233, 0.1);
            margin-bottom: 10px;
        ">
            <h4 style="color: #0c4a6e; margin: 0; border-left: 4px solid #0ea5e9; padding-left: 12px;">
                📊 Production Trends
            </h4>
        </div>
        """, unsafe_allow_html=True)
        
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        data = [1200, 1900, 1500, 2100, 1800, 1400, 1600]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=days, 
            y=data, 
            mode='lines+markers',
            line=dict(color='#0ea5e9', width=3),
            marker=dict(size=10, color='#0284c7', line=dict(width=2, color='white')),
            fill='tozeroy',
            fillcolor='rgba(14, 165, 233, 0.1)'
        ))
        fig.update_layout(
            height=300, 
            margin=dict(l=0, r=0, t=20, b=0),
            showlegend=False,
            plot_bgcolor='rgba(255,255,255,0.5)',
            paper_bgcolor='rgba(255,255,255,0.5)',
            font=dict(color='#0c4a6e'),
            xaxis=dict(gridcolor='rgba(14, 165, 233, 0.1)'),
            yaxis=dict(gridcolor='rgba(14, 165, 233, 0.1)')
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("""
        <div style="
            background: white;
            padding: 20px;
            border-radius: 14px;
            border: 1px solid #bae6fd;
            box-shadow: 0 4px 12px rgba(14, 165, 233, 0.1);
            margin-bottom: 10px;
        ">
            <h4 style="color: #0c4a6e; margin: 0; border-left: 4px solid #06b6d4; padding-left: 12px;">
                💰 Sales Overview
            </h4>
        </div>
        """, unsafe_allow_html=True)
        
        data = [5000, 7500, 6000, 9000, 8500, 5500, 7000]
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=days, 
            y=data,
            marker=dict(
                color=['#0ea5e9', '#0284c7', '#0369a1', '#075985', '#0c4a6e', '#38bdf8', '#7dd3fc'],
                line=dict(width=1, color='white')
            ),
            text=data,
            textposition='outside',
            textfont=dict(color='#0c4a6e', size=11)
        ))
        fig.update_layout(
            height=300, 
            margin=dict(l=0, r=0, t=20, b=0),
            showlegend=False,
            plot_bgcolor='rgba(255,255,255,0.5)',
            paper_bgcolor='rgba(255,255,255,0.5)',
            font=dict(color='#0c4a6e'),
            xaxis=dict(gridcolor='rgba(14, 165, 233, 0.1)'),
            yaxis=dict(gridcolor='rgba(14, 165, 233, 0.1)')
        )
        st.plotly_chart(fig, use_container_width=True)

# =========================================================
# PLACEHOLDER PAGES
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
    
    if st.session_state.theme == 'dark':
        st.markdown('<div class="dark-theme">', unsafe_allow_html=True)
    
    if not st.session_state.authenticated:
        login_page()
        return
    
    selected_page = sidebar_navigation()
    
    if selected_page == "Dashboard":
        dashboard_page()
    elif selected_page in ["User Management", "Products", "Suppliers", "Customers"]:
        placeholder_page(selected_page)
    elif selected_page in ["Inventory", "Procurement", "Production", "Quality Control", "Sales", "Finance", "Reports", "Settings"]:
        placeholder_page(selected_page)
    else:
        dashboard_page()
    
    if st.session_state.theme == 'dark':
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
