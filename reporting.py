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

try:
    admin_emails = st.secrets["admin_emails"]
except:
    admin_emails = 'False'

def string_to_list_lowercase(string):
    if not string:
        return []
    return [item.strip() for item in string.lower().split(',')]

def query_data():
    """Load data using official Keboola Storage Client"""
    token = st.secrets["kbc_storage_token"]
    kbc_url = os.environ.get('KBC_URL')

    if not token or not kbc_url:
        raise RuntimeError('Missing required environment variables: kbc_storage_token or kbc_url.')

    # Initialize Keboola Storage Client
    client = Client(kbc_url, token)
    
    # Table ID in Keboola format
    table_id = "out.c-agency_partnership_app.agency_partnership_report"
    
    # Create temporary directory for export
    tmp_dir = tempfile.mkdtemp()
    
    try:
        # Download table from Storage - it will create a file named after the table
        client.tables.export_to_file(table_id=table_id, path_name=tmp_dir)
        
        # The file is created with the table name
        csv_file = os.path.join(tmp_dir, 'agency_partnership_report')
        
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

init()

st.session_state['user_email'] = st.context.headers.get("X-Kbc-User-Email")
st.write(f"Logged in: {st.session_state['user_email']}")

st.title("Agency Partnership Report")

# Load data
df = query_data()

# Convert date column to datetime
df['date'] = pd.to_datetime(df['date'])

# Filter by agency
if st.session_state['user_email'] is not None:
    if re.sub('.*@', '', st.session_state['user_email'].lower()) == 'firma.seznam.cz' and st.session_state['user_email'].lower() in string_to_list_lowercase(admin_emails):
        df_filtered = df.copy()
    else:
        df_filtered = df[df["agentura_email"] == st.session_state['user_email']].copy()
    df_filtered = df_filtered[["year_month", "system_user_id", "system_user_email", "client_name", "system", "revenue", "revenue_noncookies", "revenue_content"]]

if st.session_state['user_email'] is None:
    st.info('Access denied. Please contact the administrator if you require access.', icon="ℹ️")

if st.session_state['user_email'] is not None:
    # Date filter
    st.subheader("Filter by Date")
    
    if not df_filtered.empty:
        # Get min and max dates from the data
        min_date = df_filtered['date'].min().date()
        max_date = df_filtered['date'].max().date()
        
        # Default to last 30 days or all available data if less
        default_start = max(min_date, max_date - timedelta(days=30))
        
        # Date range selector
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=default_start,
                min_value=min_date,
                max_value=max_date
            )
        with col2:
            end_date = st.date_input(
                "End Date",
                value=max_date,
                min_value=min_date,
                max_value=max_date
            )
        
        # Apply date filter
        df_filtered = df_filtered[
            (df_filtered['date'].dt.date >= start_date) & 
            (df_filtered['date'].dt.date <= end_date)
        ]
        
        # Display summary
        st.write(f"Showing data from {start_date} to {end_date}")
        st.write(f"Total records: {len(df_filtered)}")
        
        # Data editor with full width and increased height
        edited_df = st.data_editor(
            df_filtered, 
            use_container_width=True, 
            hide_index=True,
            height=600
        )
