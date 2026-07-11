import streamlit as st
import hashlib
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

st.set_page_config(
    page_title="Set Admin Password",
    page_icon="🔑",
    layout="centered"
)

st.title("🔑 Set Admin Password")

def hash_password(password):
    """Hash a password using SHA256 with salt"""
    salt = "amigoz_secure_salt_2024"
    result = hashlib.sha256((salt + password).encode()).hexdigest()
    return result

def get_db():
    try:
        url = st.secrets.get("DATABASE_URL")
        if not url:
            st.error("❌ DATABASE_URL not found in secrets!")
            return None
        engine = create_engine(url, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        return Session()
    except Exception as e:
        st.error(f"❌ Connection error: {str(e)}")
        return None

# Generate the hash
st.write("### 🔐 Generate and Set Password")

# Show the hash generation process
st.write("**Password:** cpsb123")
st.write("**Salt:** amigoz_secure_salt_2024")

# Generate hash
test_hash = hash_password("cpsb123")
st.write(f"**Generated Hash:** {test_hash}")
st.write(f"**Hash Length:** {len(test_hash)} characters")

if st.button("✅ Set Password to: cpsb123", type="primary", use_container_width=True):
    session = get_db()
    if session:
        try:
            # Generate the hash
            new_hash = hash_password("cpsb123")
            
            # Update the database
            result = session.execute(
                text("UPDATE users SET password_hash = :hash WHERE username = 'admin'"),
                {"hash": new_hash}
            )
            session.commit()
            
            if result.rowcount > 0:
                st.success("✅ Password updated successfully!")
                st.balloons()
                st.info("🔐 Login with:")
                st.code("Username: admin\nPassword: cpsb123")
                
                # Verify
                verify = session.execute(
                    text("SELECT password_hash FROM users WHERE username = 'admin'")
                ).fetchone()
                if verify:
                    stored_hash = verify[0]
                    if stored_hash == new_hash:
                        st.success("✅ Hash verified in database!")
                        st.write(f"Hash in DB: {stored_hash}")
                        st.write(f"Generated: {new_hash}")
                        st.write(f"Match: {stored_hash == new_hash}")
                    else:
                        st.warning(f"⚠️ Hash mismatch!")
                        st.write(f"DB Hash: {stored_hash}")
                        st.write(f"Generated: {new_hash}")
            else:
                st.error("❌ Admin user not found!")
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
        finally:
            session.close()
    else:
        st.error("❌ Cannot connect to database")

st.markdown("---")

# Manual entry option
st.write("### 🔧 Manual Password Entry")
manual_password = st.text_input("Enter new password", type="password", value="cpsb123")

if st.button("🔑 Set Custom Password", use_container_width=True):
    if manual_password:
        session = get_db()
        if session:
            try:
                new_hash = hash_password(manual_password)
                result = session.execute(
                    text("UPDATE users SET password_hash = :hash WHERE username = 'admin'"),
                    {"hash": new_hash}
                )
                session.commit()
                
                if result.rowcount > 0:
                    st.success(f"✅ Password updated to: {manual_password}")
                    st.info(f"Hash: {new_hash[:30]}...")
                else:
                    st.error("❌ Admin user not found!")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
            finally:
                session.close()
        else:
            st.error("❌ Cannot connect to database")
    else:
        st.warning("⚠️ Please enter a password")

# Check current hash
st.markdown("---")
if st.button("🔍 Check Current Hash", use_container_width=True):
    session = get_db()
    if session:
        try:
            result = session.execute(
                text("SELECT username, password_hash FROM users WHERE username = 'admin'")
            ).fetchone()
            if result:
                st.write("**Current Admin User:**")
                st.write(f"- Username: {result[0]}")
                st.write(f"- Hash: {result[1][:30]}...")
                st.write(f"- Hash length: {len(result[1])} characters")
                
                # Test if it matches cpsb123
                test_hash = hash_password("cpsb123")
                if result[1] == test_hash:
                    st.success("✅ Hash matches 'cpsb123'!")
                else:
                    st.warning("❌ Hash does NOT match 'cpsb123'")
                    st.write(f"Expected: {test_hash[:30]}...")
                    st.write(f"Found: {result[1][:30]}...")
            else:
                st.error("❌ Admin user not found")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
        finally:
            session.close()
    else:
        st.error("❌ Cannot connect to database")
