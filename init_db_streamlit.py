import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import bcrypt
import os
from dotenv import load_dotenv

load_dotenv()

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def init_database():
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/wb_erp')
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Create tables
        print("Creating tables...")
        
        # Users table
        session.execute(text("""
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
        """))
        
        # Roles table
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS roles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                description VARCHAR(200),
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        # Permissions table
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS permissions (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                module VARCHAR(50) NOT NULL,
                action VARCHAR(50) NOT NULL,
                description VARCHAR(200)
            )
        """))
        
        # Role permissions junction
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS role_permissions (
                role_id INTEGER REFERENCES roles(id),
                permission_id INTEGER REFERENCES permissions(id),
                granted_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (role_id, permission_id)
            )
        """))
        
        # Product categories
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS product_categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        # Products
        session.execute(text("""
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
                category_id INTEGER REFERENCES product_categories(id),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        # Suppliers
        session.execute(text("""
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
        """))
        
        # Customers
        session.execute(text("""
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
        """))
        
        # Stock transactions
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS stock_transactions (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES products(id),
                transaction_type VARCHAR(20) NOT NULL,
                quantity INTEGER NOT NULL,
                reference_type VARCHAR(50),
                reference_id INTEGER,
                notes TEXT,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        # Insert default roles
        print("Inserting default roles...")
        session.execute(text("""
            INSERT INTO roles (name, description, is_active)
            VALUES 
                ('Administrator', 'Full system access', true),
                ('Managing Director', 'View all data', true),
                ('Production Manager', 'Manage production', true),
                ('Quality Control Officer', 'Manage quality control', true),
                ('Storekeeper', 'Manage inventory', true),
                ('Procurement Officer', 'Manage procurement', true),
                ('Sales Officer', 'Manage sales', true),
                ('Accountant', 'Manage finances', true),
                ('Driver', 'Manage deliveries', true)
            ON CONFLICT (name) DO NOTHING
        """))
        
        # Get admin role ID
        admin_role = session.execute(
            text("SELECT id FROM roles WHERE name = 'Administrator'")
        ).fetchone()
        
        # Create admin user
        if admin_role:
            print("Creating admin user...")
            hashed_pw = hash_password('admin123')
            session.execute(text("""
                INSERT INTO users 
                (username, email, password_hash, first_name, last_name, is_superuser, role_id, is_active, created_at)
                VALUES 
                ('admin', 'admin@wb-erp.com', :password, 'System', 'Administrator', true, :role_id, true, NOW())
                ON CONFLICT (username) DO NOTHING
            """), {
                "password": hashed_pw,
                "role_id": admin_role.id
            })
        
        session.commit()
        print("✅ Database initialized successfully!")
        print("✅ Default admin user created: admin / admin123")
        
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    init_database()