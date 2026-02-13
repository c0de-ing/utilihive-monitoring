#!/usr/bin/env python3
"""
UtiliHive Metrics Dashboard V3 - With integrated data refresh
Run with: streamlit run dashboard_v3.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import glob
import subprocess
import sys
import time
import json
import base64
import hashlib

# Page configuration
st.set_page_config(
    page_title="UtiliHive Metrics Dashboard V3",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding-top: 2rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    .section-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
        font-size: 1.2rem;
        font-weight: 600;
    }
    .refresh-button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        font-size: 1rem;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)


def find_latest_csv(pattern):
    """Find the most recent CSV file matching the pattern (dated files)"""
    files = glob.glob(pattern)

    if not files:
        return None

    # Sort by filename (date prefix YYYY-MM-DD ensures chronological order)
    files.sort(reverse=True)

    # Return the most recent file
    return files[0]


@st.cache_data
def load_data(csv_file, granularity='daily'):
    """Load data from CSV file with support for hourly and daily granularity"""
    if not os.path.exists(csv_file):
        return None

    df = pd.read_csv(csv_file)
    df['collection_timestamp'] = pd.to_datetime(df['collection_timestamp'])

    if granularity == 'hourly':
        # For hourly data
        df['datetime'] = pd.to_datetime(df['datetime'])
        df['date'] = pd.to_datetime(df['date'])
        df['hour'] = df['hour'].astype(int)
    else:
        # For daily data
        df['date'] = pd.to_datetime(df['date'])

    return df


@st.cache_data
def load_flow_list(flow_file):
    """Load list of flows from text file"""
    if not os.path.exists(flow_file):
        return []

    with open(flow_file, 'r') as f:
        flows = [line.strip() for line in f if line.strip()]
    return flows


def run_data_collection(start_date, end_date, days_back=None):
    """
    Run the data collection script with specified parameters
    Returns: (success, output_message, csv_files)
    """
    try:
        # Prepare the script path
        script_path = "monitoring_data_scrap.py"

        if not os.path.exists(script_path):
            return False, f"Script not found: {script_path}", None

        # Build command
        cmd = [sys.executable, script_path]

        # Set environment variables for date range and token
        env = os.environ.copy()
        if start_date and end_date:
            env['START_DATE'] = start_date.strftime('%Y-%m-%d')
            env['END_DATE'] = end_date.strftime('%Y-%m-%d')
        elif days_back:
            # Let the script use DAYS_BACK from config
            pass

        # Pass token via environment variable
        if st.session_state.token_data and 'token' in st.session_state.token_data:
            env['API_TOKEN'] = st.session_state.token_data['token']

        # Run the script
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            bufsize=1
        )

        # Collect output
        output_lines = []
        for line in process.stdout:
            output_lines.append(line)

        # Wait for completion
        return_code = process.wait()

        output = ''.join(output_lines)

        if return_code == 0:
            # Extract the output filenames from the script output
            collection_date = datetime.now().strftime("%Y-%m-%d")
            hourly_file = f"{collection_date}_utilihive_metrics_hourly.csv"
            daily_file = f"{collection_date}_utilihive_metrics_daily.csv"

            return True, output, {'hourly': hourly_file, 'daily': daily_file}
        else:
            return False, f"Script failed with code {return_code}\n\n{output}", None

    except Exception as e:
        return False, f"Error running script: {str(e)}", None


def create_summary_metrics(df):
    """Create summary metrics cards"""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_flows = df['flow_id'].nunique()
        st.metric("Total Flows", f"{total_flows}")

    with col2:
        total_exchanges = df['total_exchanges'].sum()
        st.metric("Total Exchanges", f"{total_exchanges:,.0f}")

    with col3:
        success_rate = (df['successful_exchanges'].sum() / df['total_exchanges'].sum() * 100) if df['total_exchanges'].sum() > 0 else 0
        st.metric("Success Rate", f"{success_rate:.1f}%")

    with col4:
        total_failures = df['failed_exchanges'].sum()
        st.metric("Total Failures", f"{total_failures:,.0f}")


def create_time_series_chart(df, title="Exchanges Over Time", granularity='daily', log_scale=False):
    """Create time series chart for selected metric with support for hourly/daily data"""

    if granularity == 'hourly':
        # Group by datetime for hourly view
        time_data = df.groupby('datetime').agg({
            'total_exchanges': 'sum',
            'successful_exchanges': 'sum',
            'failed_exchanges': 'sum'
        }).reset_index()
        x_column = 'datetime'
        x_title = 'Date and Time'
    else:
        # Group by date for daily view
        time_data = df.groupby('date').agg({
            'total_exchanges': 'sum',
            'successful_exchanges': 'sum',
            'failed_exchanges': 'sum'
        }).reset_index()
        x_column = 'date'
        x_title = 'Date'

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=time_data[x_column],
        y=time_data['total_exchanges'],
        name='Total',
        mode='lines+markers',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=8 if granularity == 'daily' else 4)
    ))

    fig.add_trace(go.Scatter(
        x=time_data[x_column],
        y=time_data['successful_exchanges'],
        name='Successful',
        mode='lines+markers',
        line=dict(color='#2ca02c', width=3),
        marker=dict(size=8 if granularity == 'daily' else 4)
    ))

    fig.add_trace(go.Scatter(
        x=time_data[x_column],
        y=time_data['failed_exchanges'],
        name='Failed',
        mode='lines+markers',
        line=dict(color='#d62728', width=3),
        marker=dict(size=8 if granularity == 'daily' else 4)
    ))

    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        yaxis_title='Number of Exchanges' + (' (Log Scale)' if log_scale else ''),
        yaxis_type='log' if log_scale else 'linear',
        hovermode='x unified',
        height=700,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    return fig


def create_flow_performance_chart(df, top_n=10, log_scale=False):
    """Create bar chart for top flows by performance"""
    flow_data = df.groupby('flow_id').agg({
        'total_exchanges': 'sum',
        'successful_exchanges': 'sum',
        'failed_exchanges': 'sum'
    }).reset_index()

    flow_data = flow_data.sort_values('total_exchanges', ascending=False).head(top_n)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=flow_data['flow_id'],
        y=flow_data['successful_exchanges'],
        name='Successful',
        marker_color='#2ca02c'
    ))

    fig.add_trace(go.Bar(
        x=flow_data['flow_id'],
        y=flow_data['failed_exchanges'],
        name='Failed',
        marker_color='#d62728'
    ))

    fig.update_layout(
        title=f'Top {top_n} Flows by Volume',
        xaxis_title='Flow ID',
        yaxis_title='Number of Exchanges' + (' (Log Scale)' if log_scale else ''),
        yaxis_type='log' if log_scale else 'linear',
        barmode='stack',
        xaxis={'tickangle': -45},
        height=500
    )

    return fig


def create_response_time_chart(df, top_n=10):
    """Create chart for average response times"""
    flow_data = df[df['avg_response_time_ms'] > 0].groupby('flow_id').agg({
        'avg_response_time_ms': 'mean',
        'total_exchanges': 'sum'
    }).reset_index()

    flow_data = flow_data.sort_values('avg_response_time_ms', ascending=False).head(top_n)

    fig = px.bar(
        flow_data,
        x='flow_id',
        y='avg_response_time_ms',
        title=f'Top {top_n} Flows by Response Time',
        labels={'avg_response_time_ms': 'Avg Response Time (ms)', 'flow_id': 'Flow ID'},
        color='avg_response_time_ms',
        color_continuous_scale='Reds'
    )

    fig.update_layout(
        xaxis={'tickangle': -45},
        height=500
    )

    return fig


def create_success_by_flow_chart(df, granularity='daily', log_scale=False):
    """Create bar chart showing successful exchanges by flow over time"""

    if granularity == 'hourly':
        # Pivot data by datetime
        pivot_data = df.pivot_table(
            index='datetime',
            columns='flow_id',
            values='successful_exchanges',
            aggfunc='sum',
            fill_value=0
        )
        x_title = 'Date and Time'
        title_suffix = '(Hourly)'
    else:
        # Pivot data by date
        pivot_data = df.pivot_table(
            index='date',
            columns='flow_id',
            values='successful_exchanges',
            aggfunc='sum',
            fill_value=0
        )
        x_title = 'Date'
        title_suffix = '(Daily)'

    # Get top flows by total success
    top_flows = df.groupby('flow_id')['successful_exchanges'].sum().nlargest(10).index.tolist()
    pivot_data = pivot_data[top_flows]

    fig = go.Figure()

    for flow_id in pivot_data.columns:
        fig.add_trace(go.Bar(
            x=pivot_data.index,
            y=pivot_data[flow_id],
            name=flow_id
        ))

    fig.update_layout(
        title=f'Successful Exchanges by Flow {title_suffix} (Top 10 Flows)',
        xaxis_title=x_title,
        yaxis_title='Successful Exchanges' + (' (Log Scale)' if log_scale else ''),
        yaxis_type='log' if log_scale else 'linear',
        barmode='stack',
        height=700,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02
        ),
        xaxis={'tickangle': -45}
    )

    return fig


# ==================== AUTHENTICATION ====================

def check_password():
    """Returns `True` if the user had a correct password."""

    def hash_password(password):
        """Hash a password for storing."""
        return hashlib.sha256(password.encode()).hexdigest()

    # Load credentials from secrets or use defaults
    try:
        # Try to load from Streamlit secrets (for deployment)
        credentials = st.secrets.get("credentials", {})
        USERS = credentials.get("users", {"admin": "admin"})
    except:
        # Default credentials for local development
        USERS = {
            "admin": "admin",  # Change these!
            "user": "password"
        }

    # Hash the user database (only hash values, not keys)
    USERS_HASHED = {username: hash_password(pwd) for username, pwd in USERS.items()}

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        username = st.session_state["username"]
        password = st.session_state["password"]

        if username in USERS_HASHED and USERS_HASHED[username] == hash_password(password):
            st.session_state["authenticated"] = True
            st.session_state["current_user"] = username
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["authenticated"] = False

    # Check if already authenticated
    if st.session_state.get("authenticated", False):
        return True

    # Show login form
    st.markdown("# 🔐 UtiliHive Monitoring Login")
    st.markdown("Please enter your credentials to access the dashboard.")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.text_input("Username", key="username", placeholder="Enter your username")
        st.text_input("Password", type="password", key="password", placeholder="Enter your password")
        st.button("Login", on_click=password_entered, type="primary", use_container_width=True)

        if "authenticated" in st.session_state and not st.session_state["authenticated"]:
            st.error("😕 Username or password incorrect")

    return False


def main():
    # Header
    st.title("📊 UtiliHive Metrics Dashboard V3")
    st.markdown("Enhanced visualization with integrated data refresh")

    # Sidebar
    st.sidebar.header("⚙️ Configuration")

    # User info and logout
    if st.session_state.get("current_user"):
        st.sidebar.markdown(f"👤 **Logged in as:** {st.session_state['current_user']}")
        if st.sidebar.button("🚪 Logout", use_container_width=True):
            st.session_state["authenticated"] = False
            st.session_state["current_user"] = None
            st.rerun()
        st.sidebar.markdown("---")

    # ========== TOKEN MANAGEMENT SECTION ==========
    st.sidebar.subheader("🔑 Authentication Token")

    # Initialize session state for token
    if 'token_data' not in st.session_state:
        st.session_state.token_data = None

        # Try to load from file (for local use only)
        token_file = "token.json"
        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    st.session_state.token_data = json.load(f)
            except:
                pass

    # Check token status
    if st.session_state.token_data:
        token_data = st.session_state.token_data
        if 'expires_at' in token_data:
            try:
                expires_at = datetime.fromisoformat(token_data['expires_at'])
                if datetime.now() >= expires_at:
                    st.sidebar.warning("⚠️ Token expired!")
                else:
                    time_left = expires_at - datetime.now()
                    st.sidebar.success(f"✅ Token valid ({time_left.days}d {time_left.seconds//3600}h left)")
            except:
                st.sidebar.info("ℹ️ Token loaded")
        else:
            st.sidebar.info("ℹ️ Token loaded")
    else:
        st.sidebar.warning("⚠️ No token found")

    # Token input expander
    with st.sidebar.expander("📝 Paste New Token", expanded=not st.session_state.token_data):
        st.markdown("Get your token from [UtiliHive Console](https://console.ch.utilihive.io)")
        st.markdown("**Steps:**")
        st.markdown("1. Open browser DevTools (F12)")
        st.markdown("2. Go to Application → Local Storage")
        st.markdown("3. Find key: `JWT_MIDDLEWARE:authToken`")
        st.markdown("4. Copy the `token` value")

        new_token = st.text_area(
            "Paste Token Here",
            height=100,
            placeholder="eyJ0eXAiOiJKV1QiLCJhbGc...",
            help="Paste the JWT token from browser localStorage"
        )

        if st.button("💾 Save Token", type="primary"):
            if new_token.strip():
                # Validate token format (basic check)
                if new_token.strip().startswith('eyJ'):
                    try:
                        # Try to decode JWT to get expiration
                        parts = new_token.strip().split('.')
                        if len(parts) == 3:
                            # Decode payload
                            payload = parts[1]
                            padding = 4 - len(payload) % 4
                            if padding != 4:
                                payload += '=' * padding

                            decoded = base64.urlsafe_b64decode(payload)
                            payload_data = json.loads(decoded)

                            # Create token data
                            token_data = {
                                'token': new_token.strip(),
                                'retrieved_at': datetime.now().isoformat(),
                                'retrieved_by': 'dashboard_v3'
                            }

                            if 'exp' in payload_data:
                                exp_timestamp = payload_data['exp']
                                exp_datetime = datetime.fromtimestamp(exp_timestamp)
                                token_data['expires_at'] = exp_datetime.isoformat()

                            if 'sub' in payload_data:
                                token_data['user'] = payload_data['sub']

                            # Save to session state (works on Streamlit Cloud)
                            st.session_state.token_data = token_data

                            # Also try to save to file (for local use)
                            try:
                                with open("token.json", 'w') as f:
                                    json.dump(token_data, f, indent=2)
                            except:
                                pass  # Fails on Streamlit Cloud, but that's OK

                            st.success("✅ Token saved successfully!")
                            st.rerun()
                        else:
                            st.error("❌ Invalid token format (not a valid JWT)")
                    except Exception as e:
                        st.error(f"❌ Error saving token: {str(e)}")
                else:
                    st.error("❌ Token should start with 'eyJ'")
            else:
                st.warning("⚠️ Please paste a token first")

    # ========== DATA REFRESH SECTION ==========
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔄 Data Refresh")

    # Date range selector for data collection
    st.sidebar.markdown("**Select date range to collect:**")

    # Calculate default date range (last 7 days)
    default_end = datetime.now().date()
    default_start = default_end - timedelta(days=7)

    refresh_start_date = st.sidebar.date_input(
        "From Date",
        value=default_start,
        key='refresh_start'
    )

    refresh_end_date = st.sidebar.date_input(
        "To Date",
        value=default_end,
        key='refresh_end'
    )

    # Refresh button
    if st.sidebar.button("🔄 Refresh Data", type="primary", use_container_width=True):
        with st.spinner(f'Collecting data from {refresh_start_date} to {refresh_end_date}...'):
            # Show progress
            progress_bar = st.sidebar.progress(0)
            status_text = st.sidebar.empty()

            status_text.text("Starting data collection...")
            progress_bar.progress(10)

            # Run the collection script
            success, output, csv_files = run_data_collection(
                datetime.combine(refresh_start_date, datetime.min.time()),
                datetime.combine(refresh_end_date, datetime.max.time())
            )

            progress_bar.progress(90)

            if success:
                status_text.text("Collection complete!")
                progress_bar.progress(100)

                st.sidebar.success(f"✅ Data collected successfully!")
                st.sidebar.info(f"Files created:\n- {csv_files['hourly']}\n- {csv_files['daily']}")

                # Clear cache to reload new data
                load_data.clear()

                # Show output in expander
                with st.sidebar.expander("📋 Collection Log"):
                    st.text(output)

                time.sleep(1)
                st.rerun()
            else:
                status_text.text("Collection failed!")
                progress_bar.progress(100)
                st.sidebar.error("❌ Data collection failed!")

                # Show error details
                with st.sidebar.expander("⚠️ Error Details"):
                    st.text(output)

    st.sidebar.markdown("---")

    # ========== GRANULARITY SELECTOR ==========
    st.sidebar.subheader("🔍 Time Granularity")
    granularity = st.sidebar.radio(
        "Select View",
        options=['daily', 'hourly'],
        format_func=lambda x: '📅 Daily View' if x == 'daily' else '⏰ Hourly View',
        help="Daily view: Aggregated data by day\nHourly view: Detailed hour-by-hour data"
    )

    # File selectors based on granularity
    # Get all available CSV files based on granularity
    if granularity == 'hourly':
        # Find all hourly files in both data/ and root
        files_in_data = glob.glob("data/*_utilihive_metrics_hourly.csv")
        files_in_root = glob.glob("*_utilihive_metrics_hourly.csv")
        all_files = files_in_data + files_in_root
    else:
        # Find all daily files in both data/ and root
        files_in_data = glob.glob("data/*_utilihive_metrics_daily.csv")
        files_in_root = glob.glob("*_utilihive_metrics_daily.csv")
        all_files = files_in_data + files_in_root

    # Sort files by name (newest first due to date prefix)
    all_files.sort(reverse=True)

    # Set default to most recent file
    if all_files:
        default_csv = all_files[0]
    else:
        default_csv = "data/utilihive_metrics_hourly.csv" if granularity == 'hourly' else "data/utilihive_metrics_daily.csv"
        all_files = [default_csv]  # Add placeholder

    # Create dropdown selector
    csv_file = st.sidebar.selectbox(
        "📁 Select CSV File",
        options=all_files,
        index=0 if default_csv in all_files else 0,
        help="Select from available CSV files"
    )

    # Show file info
    if os.path.exists(csv_file):
        file_size = os.path.getsize(csv_file) / 1024  # KB
        st.sidebar.success(f"✅ File loaded ({file_size:.1f} KB)")
    else:
        st.sidebar.warning(f"⚠️ File not found")

    flow_list_file = st.sidebar.text_input(
        "Flow List File",
        value="list-flows.txt"
    )

    # Load data
    df = load_data(csv_file, granularity)

    if df is None:
        st.error(f"❌ Could not find CSV file: {csv_file}")
        st.info("💡 Click the '🔄 Refresh Data' button to collect new data!")
        st.info("Or make sure to run the data collection script first")
        return

    # Load flow list
    target_flows = load_flow_list(flow_list_file)

    if not target_flows:
        st.warning(f"⚠️ Could not load flow list from: {flow_list_file}")
        st.info("Using all flows from the data")
        target_flows = df['flow_id'].unique().tolist()
    else:
        st.sidebar.success(f"✅ Loaded {len(target_flows)} flows from list")

    st.sidebar.success(f"✅ Loaded {len(df)} records")

    # Date filter in sidebar
    st.sidebar.subheader("📅 Date Filter")
    min_date = df['date'].min().date()
    max_date = df['date'].max().date()

    date_range = st.sidebar.date_input(
        "Select Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    if len(date_range) == 2:
        start_date, end_date = date_range
        df_date_filtered = df[(df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)]
    else:
        df_date_filtered = df

    # Display data info
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Granularity:** {granularity.title()}")
    st.sidebar.markdown(f"**Total Records:** {len(df_date_filtered)}")
    st.sidebar.markdown(f"**Date Range:** {df_date_filtered['date'].min().date()} to {df_date_filtered['date'].max().date()}")

    # Main content
    if len(df_date_filtered) == 0:
        st.warning("⚠️ No data available for the selected date range")
        return

    # ========== SECTION 1: OVERVIEW (ALL FLOWS, NO FILTERING) ==========
    st.markdown('<div class="section-header">📈 OVERVIEW - All Flows (Unfiltered)</div>', unsafe_allow_html=True)

    # Summary metrics for ALL flows
    st.subheader("Key Metrics - All Flows")
    create_summary_metrics(df_date_filtered)

    st.markdown("---")

    # Time series chart for ALL flows
    col_header, col_toggle = st.columns([3, 1])
    with col_header:
        st.subheader("Trend Over Time - All Flows")
    with col_toggle:
        log_scale_all = st.checkbox("📊 Log Scale", key='log_all', help="Use logarithmic scale for Y-axis")

    time_label = "Hourly" if granularity == 'hourly' else "Daily"
    time_series_all = create_time_series_chart(df_date_filtered, f"{time_label} Exchanges Over Time (All Flows)", granularity, log_scale_all)
    st.plotly_chart(time_series_all, use_container_width=True)

    st.markdown("---")

    # ========== SECTION 2: FOCUSED ANALYSIS (FILTERED FLOWS) ==========
    st.markdown('<div class="section-header">🎯 FOCUSED ANALYSIS - Selected Flows</div>', unsafe_allow_html=True)

    # Filter data to target flows only
    df_filtered = df_date_filtered[df_date_filtered['flow_id'].isin(target_flows)]

    if len(df_filtered) == 0:
        st.warning("⚠️ No data available for the selected flows")
        return

    # Summary metrics for filtered flows
    st.subheader(f"Key Metrics - Selected Flows ({len(target_flows)} flows)")
    create_summary_metrics(df_filtered)

    # Additional filter options in sidebar for filtered section
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Additional Filters (for Focused Analysis)")

    # Flow state filter
    flow_states = st.sidebar.multiselect(
        "Flow State",
        options=df_filtered['flow_state'].unique().tolist(),
        default=df_filtered['flow_state'].unique().tolist()
    )

    df_filtered = df_filtered[df_filtered['flow_state'].isin(flow_states)]

    st.sidebar.markdown(f"**Filtered Records:** {len(df_filtered)}")

    st.markdown("---")

    # Time series for filtered flows
    col_header2, col_toggle2 = st.columns([3, 1])
    with col_header2:
        st.subheader("Trend Over Time - Selected Flows")
    with col_toggle2:
        log_scale_filtered = st.checkbox("📊 Log Scale", key='log_filtered', help="Use logarithmic scale for Y-axis")

    time_series_filtered = create_time_series_chart(df_filtered, f"{time_label} Exchanges Over Time (Selected Flows)", granularity, log_scale_filtered)
    st.plotly_chart(time_series_filtered, use_container_width=True)

    st.markdown("---")

    # Performance charts in two columns
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔝 Top Flows by Volume")
        top_n = st.slider("Number of flows to show", 5, 20, 10, key='volume')
        log_scale_volume = st.checkbox("📊 Log Scale", key='log_volume', help="Use logarithmic scale for Y-axis")
        flow_chart = create_flow_performance_chart(df_filtered, top_n, log_scale_volume)
        st.plotly_chart(flow_chart, use_container_width=True)

    with col2:
        st.subheader("⏱️ Top Flows by Response Time")
        top_n_rt = st.slider("Number of flows to show", 5, 20, 10, key='response_time')
        response_time_chart = create_response_time_chart(df_filtered, top_n_rt)
        st.plotly_chart(response_time_chart, use_container_width=True)

    st.markdown("---")

    # Success by flow chart (hourly or daily)
    col_header3, col_toggle3 = st.columns([3, 1])
    with col_header3:
        st.subheader(f"📊 {time_label} Successful Exchanges by Flow")
    with col_toggle3:
        log_scale_success = st.checkbox("📊 Log Scale", key='log_success', help="Use logarithmic scale for Y-axis")

    success_chart = create_success_by_flow_chart(df_filtered, granularity, log_scale_success)
    st.plotly_chart(success_chart, use_container_width=True)

    st.markdown("---")

    # Data tables
    st.subheader("📋 Detailed Data")

    tab1, tab2, tab3 = st.tabs(["Summary Table", "Raw Data", "Flow List"])

    with tab1:
        # Summary pivot table
        summary_data = df_filtered.groupby('flow_id').agg({
            'total_exchanges': 'sum',
            'successful_exchanges': 'sum',
            'failed_exchanges': 'sum',
            'avg_response_time_ms': 'mean',
            'avg_processing_time_ms': 'mean'
        }).reset_index()

        summary_data = summary_data.sort_values('total_exchanges', ascending=False)

        # Format numbers
        summary_data['avg_response_time_ms'] = summary_data['avg_response_time_ms'].round(1)
        summary_data['avg_processing_time_ms'] = summary_data['avg_processing_time_ms'].round(1)

        st.dataframe(summary_data, use_container_width=True, height=400)

        # Download button
        csv = summary_data.to_csv(index=False)
        st.download_button(
            label="📥 Download Summary",
            data=csv,
            file_name=f"flow_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

    with tab2:
        st.dataframe(df_filtered, use_container_width=True, height=400)

        # Download button for raw data
        csv_raw = df_filtered.to_csv(index=False)
        st.download_button(
            label="📥 Download Filtered Data",
            data=csv_raw,
            file_name=f"filtered_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

    with tab3:
        st.write(f"**Monitoring {len(target_flows)} flows:**")
        st.write(", ".join(target_flows))

        # Show which flows have data
        flows_with_data = df_filtered['flow_id'].unique().tolist()
        flows_without_data = [f for f in target_flows if f not in flows_with_data]

        if flows_without_data:
            st.warning(f"⚠️ {len(flows_without_data)} flows in list have no data:")
            st.write(", ".join(flows_without_data))


if __name__ == "__main__":
    # Check authentication first
    if check_password():
        main()
