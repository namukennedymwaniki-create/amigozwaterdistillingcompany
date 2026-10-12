# pages_settings.py
# Settings Module — Stage 01, Step 2
# Includes: Warehouse/Stock Locations register

import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import text
from database import get_db_connection, log_audit


def settings_page():
    """Settings page - Warehouse register and system configuration"""
    
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important;
        }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='color: #0c4a6e;'>⚙️ Settings</h2>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["🏢 Warehouses / Stock Locations", "📁 Product Categories", "ℹ️ System Info"])
    
    # ============================================
    # TAB 1: WAREHOUSES
    # ============================================
    with tab1:
        st.markdown("#### 🏢 Warehouses / Stock Locations")
        st.c
