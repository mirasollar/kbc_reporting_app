import streamlit as st
import os
import tempfile
import shutil
from kbcstorage.client import Client
import pandas as pd
from datetime import datetime, timedelta
import re

# MUST BE FIRST - Set page to wide mode to use full width
st.set_page_config(layout="wide", page_title="Agency Partnership Report")

# Custom CSS for better styling
st.markdown("""
    <style>
    .filter-container {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

try:
    admin_emails = st.secrets["admin_emails"]
except:
    admin_emails = 'False'

try:
    fact_table_id = st.secrets["fact_table_id"]
except:
    fact_table_id = ''

def string_to_list_lowercase(string):
    if not string:
        return []
    return [item.strip() for item in string.lower().split(',')]

@st.cache_data(ttl=3600)
def query_data(table_id, kbc_url, token):
    """Load data using official Keboola Storage Client - cached to avoid reloading"""
    
    if not token or not kbc_url:
        raise RuntimeError('Missing required environment variables: kbc_storage_token or kbc_url.')

    # Initialize Keboola Storage Client
    client = Client(kbc_url, token)
    
    # Create temporary directory for export
    tmp_dir = tempfile.mkdtemp()
    
    try:
        # Download table from Storage - it will create a file named after the table
        client.tables.export_to_file(table_id=table_id, path_name=tmp_dir)
        
        # The file is created with the table name
        table_name = table_id.split('.')[-1]
        csv_file = os.path.join(tmp_dir, table_name)
        
        # Load CSV into DataFrame
        df = pd.read_csv(csv_file)
        return df
    finally:
        # Clean up temp directory and files
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)

def init():
    if 'user_email' not in st.session_state:
        st.session_state['user_email'] = None
    if 'logged_in_admin' not in st.session_state:
        st.session_state['logged_in_admin'] = None

init()

st.session_state['user_email'] = st.context.headers.get("X-Kbc-User-Email")
st.write(f"Logged in: {st.session_state['user_email']}")

st.title("Agency Partnership Report")

# Access denied check
if st.session_state['user_email'] is None:
    st.info('Access denied. Please contact the administrator if you require access.', icon="ℹ️")
    st.stop()

# Check if fact table is configured
if fact_table_id == '':
    st.error('Missing fact table configuration.')
    st.stop()

# Load data - this will be cached!
token = st.secrets["kbc_storage_token"]
kbc_url = os.environ.get('KBC_URL')
df = query_data(fact_table_id, kbc_url, token)

# Convert date column to datetime
df['date'] = pd.to_datetime(df['date'])

# Check admin status
if re.sub('.*@', '', st.session_state['user_email'].lower()) == 'firma.seznam.cz' and st.session_state['user_email'].lower() in string_to_list_lowercase(admin_emails):
    df_filtered = df.copy()
    st.session_state['logged_in_admin'] = True
else:
    df_filtered = df[df["agentura_email"] == st.session_state['user_email']].copy()
    st.session_state['logged_in_admin'] = False

if not df_filtered.empty:
    # Filters section with visual separation
    with st.container():
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        st.subheader("🔍 Filters")
        
        # Date filter
        col1, col2 = st.columns(2)
        
        min_date = df_filtered['date'].min().date()
        max_date = df_filtered['date'].max().date()
        default_start = max(min_date, max_date - timedelta(days=30))
        
        with col1:
            start_date = st.date_input(
                "📅 Start Date",
                value=default_start,
                min_value=min_date,
                max_value=max_date
            )
        with col2:
            end_date = st.date_input(
                "📅 End Date",
                value=max_date,
                min_value=min_date,
                max_value=max_date
            )
        
        # Apply date filter first
        df_filtered = df_filtered[
            (df_filtered['date'].dt.date >= start_date) & 
            (df_filtered['date'].dt.date <= end_date)
        ]
        
        st.divider()
        
        # System and Client Name filters (contextual) - Single select dropdowns
        col3, col4 = st.columns(2)
        
        with col3:
            # Get available systems from date-filtered data
            available_systems = ['All'] + sorted(df_filtered['system'].dropna().unique().tolist())
            
            selected_system = st.selectbox(
                "🖥️ System",
                options=available_systems,
                index=0,
                help="Select a system"
            )
        
        # Filter by selected system
        if selected_system != 'All':
            df_filtered = df_filtered[df_filtered['system'] == selected_system]
        
        with col4:
            # Get available clients from system-filtered data (contextual!)
            available_clients = ['All'] + sorted(df_filtered['client_name'].dropna().unique().tolist())
            
            selected_client = st.selectbox(
                "👤 Client Name",
                options=available_clients,
                index=0,
                help="Select a client (filtered by system)"
            )
        
        # Filter by selected client
        if selected_client != 'All':
            df_filtered = df_filtered[df_filtered['client_name'] == selected_client]
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Display summary with metrics
    st.divider()
    
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("📊 Total Records", len(df_filtered))
    with col_m2:
        st.metric("📅 Date Range", f"{start_date} to {end_date}")
    with col_m3:
        if 'revenue' in df_filtered.columns:
            total_revenue = df_filtered['revenue'].sum()
            st.metric("💰 Total Revenue", f"{total_revenue:,.0f}")
    
    st.divider()
    
    # Select columns based on admin status
    if not st.session_state['logged_in_admin']:
        df_filtered = df_filtered[["year_month", "system_user_id", "system_user_email", "client_name", "system", "revenue", "revenue_noncookies", "revenue_content"]]
    
    # Data section
    st.subheader("📈 Data")
    
    # Data editor with full width and increased height
    edited_df = st.data_editor(
        df_filtered, 
        use_container_width=True, 
        hide_index=True,
        height=600
    )
