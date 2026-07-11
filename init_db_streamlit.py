"""
Database Initialization Script for Water Bottling ERP System
Supports both SQLite (local development) and PostgreSQL (production)
"""

import os
import bcrypt
import sqlite3
import psycopg2
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def get_db_connection():
    """Get database connection - works for both SQLite and PostgreSQL"""
    
    # Check for DATABASE_URL in environment or secrets
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # Use PostgreSQL (Streamlit Cloud or production)
        try:
            engine = create_engine(database_url, pool_pre_ping=True)
            Session = sessionmaker(bind=engine)
            return Session(), engine
        except Exception as e:
            print(f"❌ PostgreSQL connection error: {e}")
            return None, None
    else:
        # Use SQLite (local development)
        try:
            # Create SQLite engine
            engine = create_engine('sqlite:///wb_erp.db', connect_args={'check_same_thread': False})
            Session = sessionmaker(bind=engine)
            return Session(), engine
        except Exception as e:
            print(f"❌ SQLite connection error: {e}")
            return None, None

def create_tables_sqlite():
    """Create all tables for SQLite"""
    conn = sqlite3.connect('wb_erp.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            is_active INTEGER DEFAULT 1,
            is_superuser INTEGER DEFAULT 0,
            last_login DATETIME,
            role_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Roles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Permissions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            module TEXT NOT NULL,
            action TEXT NOT NULL,
            description TEXT
        )
    ''')
    
    # Role permissions junction table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER,
            permission_id INTEGER,
            granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (role_id, permission_id),
            FOREIGN KEY (role_id) REFERENCES roles(id),
            FOREIGN KEY (permission_id) REFERENCES permissions(id)
        )
    ''')
    
    # Product categories
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Products
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            unit TEXT DEFAULT 'piece',
            unit_price REAL DEFAULT 0,
            cost_price REAL DEFAULT 0,
            min_stock_level INTEGER DEFAULT 0,
            max_stock_level INTEGER DEFAULT 1000,
            current_stock INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            barcode TEXT,
            weight REAL,
            volume REAL,
            category_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES product_categories(id)
        )
    ''')
    
    # Suppliers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_person TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            tax_number TEXT,
            payment_terms INTEGER DEFAULT 30,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Customers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_person TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            tax_number TEXT,
            credit_limit REAL DEFAULT 0,
            current_balance REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Stock transactions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            transaction_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            reference_type TEXT,
            reference_id INTEGER,
            notes TEXT,
            created_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ SQLite tables created successfully")

def create_tables_postgresql(engine):
    """Create all tables for PostgreSQL using SQLAlchemy"""
    session = sessionmaker(bind=engine)()
    
    try:
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
        
        # Role permissions junction
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS role_permissions (
                role_id INTEGER REFERENCES roles(id),
                permission_id INTEGER REFERENCES permissions(id),
                granted_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (role_id, permission_id)
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
                category_id INTEGER REFERENCES product_categories(id),
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
                product_id INTEGER REFERENCES products(id),
                transaction_type VARCHAR(20) NOT NULL,
                quantity INTEGER NOT NULL,
                reference_type VARCHAR(50),
                reference_id INTEGER,
                notes TEXT,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT NOW()
            )
        '''))
        
        session.commit()
        print("✅ PostgreSQL tables created successfully")
        
    except Exception as e:
        print(f"❌ Error creating PostgreSQL tables: {e}")
        session.rollback()
    finally:
        session.close()

def seed_default_data(session, is_postgresql=False):
    """Insert default roles and admin user"""
    
    try:
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
        
        # Check if roles exist
        if is_postgresql:
            # PostgreSQL query
            existing_roles = session.execute(text("SELECT name FROM roles")).fetchall()
            existing_role_names = [r[0] for r in existing_roles]
        else:
            # SQLite query
            existing_roles = session.execute(text("SELECT name FROM roles")).fetchall()
            existing_role_names = [r[0] for r in existing_roles]
        
        # Insert roles that don't exist
        for name, description in roles:
            if name not in existing_role_names:
                if is_postgresql:
                    session.execute(
                        text("INSERT INTO roles (name, description, is_active, created_at) VALUES (:name, :description, true, NOW())"),
                        {"name": name, "description": description}
                    )
                else:
                    session.execute(
                        text("INSERT INTO roles (name, description, is_active, created_at) VALUES (:name, :description, 1, CURRENT_TIMESTAMP)"),
                        {"name": name, "description": description}
                    )
        
        session.commit()
        print("✅ Default roles inserted")
        
        # Get admin role ID
        if is_postgresql:
            admin_role = session.execute(
                text("SELECT id FROM roles WHERE name = 'Administrator'")
            ).fetchone()
            now_value = "NOW()"
        else:
            admin_role = session.execute(
                text("SELECT id FROM roles WHERE name = 'Administrator'")
            ).fetchone()
            now_value = "CURRENT_TIMESTAMP"
        
        # Create admin user if not exists
        if admin_role:
            # Check if admin exists
            existing_admin = session.execute(
                text("SELECT id FROM users WHERE username = 'admin'")
            ).fetchone()
            
            if not existing_admin:
                hashed_pw = hash_password('admin123')
                
                if is_postgresql:
                    session.execute(
                        text("""
                            INSERT INTO users 
                            (username, email, password_hash, first_name, last_name, is_superuser, role_id, is_active, created_at)
                            VALUES 
                            ('admin', 'admin@wb-erp.com', :password, 'System', 'Administrator', true, :role_id, true, NOW())
                        """),
                        {"password": hashed_pw, "role_id": admin_role[0]}
                    )
                else:
                    session.execute(
                        text("""
                            INSERT INTO users 
                            (username, email, password_hash, first_name, last_name, is_superuser, role_id, is_active, created_at)
                            VALUES 
                            ('admin', 'admin@wb-erp.com', :password, 'System', 'Administrator', 1, :role_id, 1, CURRENT_TIMESTAMP)
                        """),
                        {"password": hashed_pw, "role_id": admin_role[0]}
                    )
                
                session.commit()
                print("✅ Admin user created: admin / admin123")
            else:
                print("ℹ️ Admin user already exists")
        else:
            print("⚠️ Admin role not found")
            
    except Exception as e:
        print(f"❌ Error seeding default data: {e}")
        session.rollback()

def init_database():
    """Main function to initialize the database"""
    print("=" * 50)
    print("💧 Water Bottling ERP - Database Initialization")
    print("=" * 50)
    
    # Get database connection
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        print(f"📊 Using PostgreSQL: {database_url.split('@')[1] if '@' in database_url else 'PostgreSQL'}")
        session, engine = get_db_connection()
        if session and engine:
            create_tables_postgresql(engine)
            seed_default_data(session, is_postgresql=True)
            session.close()
        else:
            print("❌ Failed to connect to PostgreSQL")
            return False
    else:
        print("📊 Using SQLite: wb_erp.db")
        create_tables_sqlite()
        
        # Seed SQLite data
        engine = create_engine('sqlite:///wb_erp.db', connect_args={'check_same_thread': False})
        Session = sessionmaker(bind=engine)
        session = Session()
        seed_default_data(session, is_postgresql=False)
        session.close()
    
    print("=" * 50)
    print("✅ Database initialization completed successfully!")
    print("🔐 Login credentials:")
    print("   Username: admin")
    print("   Password: admin123")
    print("=" * 50)
    return True

# Run the initialization
if __name__ == "__main__":
    init_database()
