import os
import hashlib
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

def hash_password(password):
    """Hash a password using SHA256 with salt"""
    salt = "amigoz_secure_salt_2024"
    return hashlib.sha256((salt + password).encode()).hexdigest()

def get_db_connection():
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        engine = create_engine(database_url, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        return Session()
    else:
        engine = create_engine('sqlite:///wb_erp.db', connect_args={'check_same_thread': False})
        Session = sessionmaker(bind=engine)
        return Session()

def init_database():
    session = get_db_connection()
    
    try:
        print("📊 Creating tables...")
        
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
        
        # Products table
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
                category_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        '''))
        
        # Suppliers table
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
        
        # Customers table
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
        
        session.commit()
        print("✅ Tables created successfully!")
        
        # Insert default roles
        print("👤 Inserting default roles...")
        session.execute(text('''
            INSERT INTO roles (name, description, is_active, created_at) VALUES
                ('Administrator', 'Full system access', true, NOW()),
                ('Managing Director', 'View all data', true, NOW()),
                ('Production Manager', 'Manage production', true, NOW()),
                ('Quality Control Officer', 'Manage quality control', true, NOW()),
                ('Storekeeper', 'Manage inventory', true, NOW()),
                ('Procurement Officer', 'Manage procurement', true, NOW()),
                ('Sales Officer', 'Manage sales', true, NOW()),
                ('Accountant', 'Manage finances', true, NOW()),
                ('Driver', 'Manage deliveries', true, NOW())
            ON CONFLICT (name) DO NOTHING
        '''))
        session.commit()
        
        # Create admin user
        print("🔐 Creating admin user...")
        admin_password = hash_password("cpsb123")
        
        # Get admin role ID
        admin_role = session.execute(
            text("SELECT id FROM roles WHERE name = 'Administrator'")
        ).fetchone()
        
        session.execute(
            text("""
                INSERT INTO users 
                (username, email, password_hash, first_name, last_name, is_superuser, role_id, is_active, created_at)
                VALUES 
                ('admin', 'admin@amigoz.com', :hash, 'System', 'Administrator', true, :role_id, true, NOW())
                ON CONFLICT (username) DO NOTHING
            """),
            {"hash": admin_password, "role_id": admin_role[0] if admin_role else None}
        )
        session.commit()
        
        print("✅ Database initialized successfully!")
        print("🔐 Login credentials:")
        print("   Username: admin")
        print("   Password: cpsb123")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    init_database()
