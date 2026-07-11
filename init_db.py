"""
Database Initialization Script for Neon PostgreSQL
Run this on Streamlit Cloud to initialize your database
"""

import streamlit as st
import os
import bcrypt
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

st.set_page_config(
    page_title="Database Initialization",
    page_icon="🔧",
    layout="centered"
)

st.title("🔧 Database Initialization")

# Get database connection
def get_db_connection():
    try:
        database_url = st.secrets.get("DATABASE_URL")
        if not database_url:
            st.error("❌ DATABASE_URL not found in secrets!")
            return None
        
        engine = create_engine(database_url, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        return Session()
    except Exception as e:
        st.error(f"❌ Connection error: {str(e)}")
        return None

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_tables(session):
    """Create all tables"""
    try:
        st.info("📊 Creating tables...")
        
        # Users table
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                first_name VARCHAR(50),
                last_name VARCHAR(50),
                phone VARCHAR(20),
                is_active BOOLEAN DEFAULT true,
                is_superuser BOOLEAN DEFAULT false,
                last_login TIMESTAMP,
                role_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        '''))
        
        # Roles table
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS roles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                description VARCHAR(200),
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        '''))
        
        # Permissions table
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS permissions (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                module VARCHAR(50) NOT NULL,
                action VARCHAR(50) NOT NULL,
                description VARCHAR(200)
            )
        '''))
        
        # Product categories
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS product_categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        '''))
        
        # Products
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                code VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                unit VARCHAR(20) DEFAULT 'piece',
                unit_price DECIMAL(10,2) DEFAULT 0,
                cost_price DECIMAL(10,2) DEFAULT 0,
                min_stock_level INTEGER DEFAULT 0,
                max_stock_level INTEGER DEFAULT 1000,
                current_stock INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT true,
                barcode VARCHAR(50),
                weight DECIMAL(10,2),
                volume DECIMAL(10,2),
                category_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        '''))
        
        # Suppliers
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS suppliers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                contact_person VARCHAR(100),
                email VARCHAR(100),
                phone VARCHAR(20),
                address TEXT,
                tax_number VARCHAR(50),
                payment_terms INTEGER DEFAULT 30,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        '''))
        
        # Customers
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS customers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                contact_person VARCHAR(100),
                email VARCHAR(100),
                phone VARCHAR(20),
                address TEXT,
                tax_number VARCHAR(50),
                credit_limit DECIMAL(10,2) DEFAULT 0,
                current_balance DECIMAL(10,2) DEFAULT 0,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        '''))
        
        # Stock transactions
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS stock_transactions (
                id SERIAL PRIMARY KEY,
                product_id INTEGER,
                transaction_type VARCHAR(20) NOT NULL,
                quantity INTEGER NOT NULL,
                reference_type VARCHAR(50),
                reference_id INTEGER,
                notes TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            )
        '''))
        
        # Role permissions junction
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS role_permissions (
                role_id INTEGER,
                permission_id INTEGER,
                granted_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (role_id, permission_id)
            )
        '''))
        
        session.commit()
        st.success("✅ Tables created successfully!")
        return True
        
    except Exception as e:
        st.error(f"❌ Error creating tables: {str(e)}")
        session.rollback()
        return False

def seed_data(session):
    """Insert default data"""
    try:
        st.info("👤 Seeding default data...")
        
        # Check if roles exist
        existing_roles = session.execute(text("SELECT name FROM roles")).fetchall()
        existing_role_names = [r[0] for r in existing_roles]
        
        # Default roles
        roles = [
            ('Administrator', 'Full system access'),
            ('Managing Director', 'View all data'),
            ('Production Manager', 'Manage production'),
            ('Quality Control Officer', 'Manage quality control'),
            ('Storekeeper', 'Manage inventory'),
            ('Procurement Officer', 'Manage procurement'),
            ('Sales Officer', 'Manage sales'),
            ('Accountant', 'Manage finances'),
            ('Driver', 'Manage deliveries')
        ]
        
        # Insert roles that don't exist
        for name, description in roles:
            if name not in existing_role_names:
                session.execute(
                    text("INSERT INTO roles (name, description, is_active, created_at) VALUES (:name, :description, true, NOW())"),
                    {"name": name, "description": description}
                )
        
        session.commit()
        st.success("✅ Default roles inserted!")
        
        # Get admin role ID
        admin_role = session.execute(
            text("SELECT id FROM roles WHERE name = 'Administrator'")
        ).fetchone()
        
        # Create admin user if not exists
        if admin_role:
            existing_admin = session.execute(
                text("SELECT id FROM users WHERE username = 'admin'")
            ).fetchone()
            
            if not existing_admin:
                hashed_pw = hash_password('admin123')
                session.execute(
                    text("""
                        INSERT INTO users 
                        (username, email, password_hash, first_name, last_name, is_superuser, role_id, is_active, created_at)
                        VALUES 
                        ('admin', 'admin@wb-erp.com', :password, 'System', 'Administrator', true, :role_id, true, NOW())
                    """),
                    {"password": hashed_pw, "role_id": admin_role[0]}
                )
                session.commit()
                st.success("✅ Admin user created: admin / admin123")
            else:
                st.info("ℹ️ Admin user already exists")
        else:
            st.warning("⚠️ Admin role not found")
            
        return True
        
    except Exception as e:
        st.error(f"❌ Error seeding data: {str(e)}")
        session.rollback()
        return False

def check_tables(session):
    """Check if tables exist"""
    inspector = inspect(session.bind)
    return inspector.get_table_names()

# Main UI
def main():
    session = get_db_connection()
    
    if not session:
        st.error("❌ Cannot connect to database. Check your DATABASE_URL secret.")
        return
    
    # Check existing tables
    tables = check_tables(session)
    
    st.write("### 📊 Current Database Status")
    
    col1, col2 = st.columns(2)
    with col1:
        if tables:
            st.success(f"✅ Found {len(tables)} tables")
            st.write("**Tables:**")
            for table in tables:
                st.write(f"- {table}")
        else:
            st.warning("⚠️ No tables found. Database needs initialization.")
    
    with col2:
        st.info("🔐 Admin credentials after init:")
        st.code("Username: admin\nPassword: admin123")
    
    st.markdown("---")
    
    # Initialize button
    if st.button("🚀 Initialize Database", use_container_width=True, type="primary"):
        if create_tables(session):
            if seed_data(session):
                st.balloons()
                st.success("🎉 Database initialized successfully!")
                st.info("🔐 You can now login with: admin / admin123")
                
                # Show tables after init
                tables = check_tables(session)
                if tables:
                    st.write("✅ Tables created:")
                    for table in tables:
                        st.write(f"- {table}")
            else:
                st.error("❌ Failed to seed data")
        else:
            st.error("❌ Failed to create tables")
    
    session.close()

if __name__ == "__main__":
    main()
