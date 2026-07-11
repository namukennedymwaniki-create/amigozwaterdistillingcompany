import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import bcrypt
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
# DATABASE CONNECTION
# =========================================================
def get_db_connection():
    """Get database connection - works with PostgreSQL or SQLite"""
    try:
        # Try to get DATABASE_URL from secrets (Streamlit Cloud) or environment
        database_url = None
        
        # Check Streamlit secrets first
        try:
            database_url = st.secrets.get("DATABASE_URL")
        except:
            pass
        
        # If not in secrets, check environment
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
# AUTHENTICATION FUNCTIONS
# =========================================================
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

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
        'show_add_customer': False
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
        /* Main container */
        .main > div {
            padding: 0 1rem;
        }
        
        /* Metric cards */
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
        
        /* Login container */
        .login-container {
            max-width: 420px;
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
        
        /* Buttons */
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
        
        /* Sidebar */
        .css-1d391kg {
            background: linear-gradient(180deg, #1a1a2e 0%, #2d3436 100%);
        }
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# LOGIN PAGE
# =========================================================
def login_page():
    st.markdown("""
    <div class="login-container">
        <div class="login-title">
            <h2>💧 Amigoz Water Distilling</h2>
            <p>Enterprise Resource Planning System</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            username = st.text_input("Username", placeholder="Enter your username", key="login_username")
            password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")
            
            if st.button("🔐 Sign In", key="login_button", use_container_width=True):
                if username and password:
                    session = get_db_connection()
                    if session:
                        try:
                            # Check if users table exists
                            inspector = inspect(session.bind)
                            if not inspector.has_table('users'):
                                st.error("❌ Database not initialized. Please run init_db_streamlit.py first.")
                                return
                            
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
                                try:
                                    update_query = text("UPDATE users SET last_login = NOW() WHERE id = :user_id")
                                    session.execute(update_query, {"user_id": result.id})
                                    session.commit()
                                except:
                                    pass
                                
                                st.success("✅ Login successful!")
                                st.rerun()
                            else:
                                st.error("❌ Invalid username or password")
                        except Exception as e:
                            st.error(f"❌ Login error: {str(e)}")
                        finally:
                            session.close()
                    else:
                        st.error("❌ Database connection failed")
                else:
                    st.warning("⚠️ Please enter both username and password")

# =========================================================
# SIDEBAR NAVIGATION
# =========================================================
def sidebar_navigation():
    with st.sidebar:
        st.markdown("""
        <div style="padding: 20px 0; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.1);">
            <h3 style="color: white; margin: 0;">💧 Amigoz ERP</h3>
            <p style="color: rgba(255,255,255,0.6); font-size: 12px; margin: 5px 0 0;">Version 1.0.0</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # User info
        if st.session_state.authenticated:
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="width: 42px; height: 42px; background: linear-gradient(135deg, #667eea, #764ba2); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 18px;">
                        {st.session_state.full_name[0].upper() if st.session_state.full_name else 'U'}
                    </div>
                    <div style="flex: 1;">
                        <div style="color: white; font-weight: 600; font-size: 14px;">{st.session_state.full_name}</div>
                        <div style="color: rgba(255,255,255,0.5); font-size: 12px;">{st.session_state.role or 'No Role'}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Navigation
        st.markdown("### 📋 Navigation")
        
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
            if st.button(f"{icon} {page_name}", key=f"nav_{page_name}", use_container_width=True):
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
        
        # Logout
        if st.button("🚪 Logout", key="logout_button", use_container_width=True):
            for key in ['authenticated', 'user', 'user_id', 'role', 'full_name']:
                st.session_state[key] = None if key != 'authenticated' else False
            st.rerun()
    
    return st.session_state.page

# =========================================================
# DASHBOARD
# =========================================================
def dashboard_page():
    st.markdown("<h2 style='margin-bottom: 30px;'>📊 Dashboard</h2>", unsafe_allow_html=True)
    
    # Get data from database
    session = get_db_connection()
    if session:
        try:
            inspector = inspect(session.bind)
            if inspector.has_table('products'):
                product_count = session.execute(text("SELECT COUNT(*) FROM products WHERE is_active = true")).scalar() or 0
            else:
                product_count = 0
                
            if inspector.has_table('suppliers'):
                supplier_count = session.execute(text("SELECT COUNT(*) FROM suppliers WHERE is_active = true")).scalar() or 0
            else:
                supplier_count = 0
                
            if inspector.has_table('customers'):
                customer_count = session.execute(text("SELECT COUNT(*) FROM customers WHERE is_active = true")).scalar() or 0
            else:
                customer_count = 0
                
            if inspector.has_table('users'):
                user_count = session.execute(text("SELECT COUNT(*) FROM users WHERE is_active = true")).scalar() or 0
            else:
                user_count = 0
        except:
            product_count = supplier_count = customer_count = user_count = 0
        finally:
            session.close()
    else:
        product_count = supplier_count = customer_count = user_count = 0
    
    # Demo data for dashboard
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    production_data = [1200, 1900, 1500, 2100, 1800, 1400, 1600]
    sales_data = [5000, 7500, 6000, 9000, 8500, 5500, 7000]
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📦 Products", product_count, delta="Active")
    with col2:
        st.metric("🏭 Suppliers", supplier_count, delta="Active")
    with col3:
        st.metric("👥 Customers", customer_count, delta="Active")
    with col4:
        st.metric("👤 Users", user_count, delta="Active")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("<h4>📊 Production Trends</h4>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=days,
            y=production_data,
            mode='lines+markers',
            line=dict(color='#667eea', width=3),
            marker=dict(size=8, color='#667eea'),
            fill='tozeroy',
            fillcolor='rgba(102, 126, 234, 0.1)'
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("<h4>💰 Sales Overview</h4>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=days,
            y=sales_data,
            marker=dict(color='#f5576c', opacity=0.7)
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.info("💡 Welcome to Amigoz Water Distilling Company ERP System")

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
    
    # Page routing
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
