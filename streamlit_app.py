#!/usr/bin/env python3
"""
CloudFlare IP Scanner - Streamlit Interface
A user-friendly web interface for testing CloudFlare IPs with VLESS connections
Developer: AHB
"""
import streamlit as st
import os
import sys
import json
import yaml
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path
import time
import subprocess
import socket

from main import kill_process_on_port


# Import helper functions
from streamlit_helpers import (
    load_config_yaml,
    save_config_yaml,
    validate_config,
    check_xray_binary,
    check_port_availability,
    test_single_ip_connection,
    run_system_diagnostics,
    format_speed,
    format_latency,
    export_results_csv,
    export_results_json
)

# Page configuration
st.set_page_config(
    page_title="CloudFlare IP Scanner",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3.5rem !important;
        font-weight: bold !important;
        color: #2E86AB !important;
        text-align: center !important;
        margin-bottom: 1rem !important;
        font-family: "Courier New" !important;
    }
        
    /* Universal font for all elements */
    html, body, [class*="css"] {
        font-family: "Courier New", monospace;
    }
            
    /* Explicitly target headings */
    h1, h2, h3, h4, h5, h6 {
        font-family: "Courier New", monospace !important;
    }
    
    /* Targetting Streamlit elements */
    .stApp, .stSidebar, .stMarkdown, .stButton, .stTextInput, stInfo, stImage,
    .stSelectbox, .stMultiSelect, .stNumberInput, .stSlider,
    div[data-testid="stMarkdownContainer"], 
    div[data-testid="stText"],
    .element-container {
        font-family: "Courier New", monospace;
    }
    
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        font-family:  "Courier New";
    }
    .stAlert {
        margin-top: 1rem;
        font-family:  "Courier New";
    }
</style>
""", unsafe_allow_html=True)

# Initialise session state
if 'quick_test_mode' not in st.session_state:
    st.session_state.quick_test_mode = False
if 'stop_requested' not in st.session_state:
    st.session_state.stop_requested = False
if 'scan_running' not in st.session_state:
    st.session_state.scan_running = False
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None
if 'scan_history' not in st.session_state:
    st.session_state.scan_history = []
if 'current_config' not in st.session_state:
    st.session_state.current_config = None
if 'logs' not in st.session_state:
    st.session_state.logs = []

# Paths
CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = os.path.join(CURRENT_DIR, 'config', 'config.yaml')
RESULTS_DIR = os.path.join(CURRENT_DIR, 'results')
XRAY_BINARY = os.path.join(CURRENT_DIR, 'converters', 'xray-core', 
                           'xray.exe' if os.name == 'nt' else 'xray')

# Create results directory if it doesn't exist
os.makedirs(RESULTS_DIR, exist_ok=True)

# Helper function to add log
def add_log(message, level="info"):
    """Add a log message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {
        "time": timestamp,
        "level": level,
        "message": message
    }
    st.session_state.logs.append(log_entry)
    
    # Keep only last 100 logs
    if len(st.session_state.logs) > 100:
        st.session_state.logs = st.session_state.logs[-100:]



# ==================== SIDEBAR: CONFIGURATION ====================
st.sidebar.title("⚙️ Configuration")

# Config file upload
st.sidebar.subheader("📁 Upload Configuration")
uploaded_config = st.sidebar.file_uploader(
    "Upload config.yaml", 
    type=['yaml', 'yml'],
    help="Upload your VLESS configuration file"
)

uploaded_test_config = st.sidebar.file_uploader(
    "Upload test_vless_config.json (optional)", 
    type=['json'],
    help="Upload a test VLESS config to validate your setup"
)

if uploaded_config:
    try:
        config_data = yaml.safe_load(uploaded_config)
        st.session_state.current_config = config_data
        st.sidebar.success("✅ Config loaded successfully!")
    except Exception as e:
        st.sidebar.error(f"❌ Error loading config: {e}")

# Load default config if none uploaded
if st.session_state.current_config is None:
    if os.path.exists(CONFIG_FILE):
        st.session_state.current_config = load_config_yaml(CONFIG_FILE)
    else:
        # Default configuration
        st.session_state.current_config = {
            'vless_uuid': 'c1f6fe11-7446-4663-9630-09aa1a3af46a',
            'vless_port': '443',
            'server_name': 'private777.digikala.lat',
            'host_header': 'private3.digikala.lat',
            'ws_path': '/',
            'ip_num': '20',
            'sorted_by': 'download',
            'local_socks_port': '1080'
        }

config = st.session_state.current_config

# VLESS Configuration Form
st.sidebar.subheader("🔧 VLESS Settings")
with st.sidebar.expander("Edit VLESS Configuration", expanded=False):
    config['vless_uuid'] = st.text_input(
        "VLESS UUID", 
        value=config.get('vless_uuid', ''),
        help="Your VLESS server UUID"
    )
    
    config['server_name'] = st.text_input(
        "Server Name (SNI)", 
        value=config.get('server_name', ''),
        help="TLS Server Name Indication"
    )
    
    config['host_header'] = st.text_input(
        "Host Header", 
        value=config.get('host_header', ''),
        help="WebSocket Host header"
    )
    
    config['ws_path'] = st.text_input(
        "WebSocket Path", 
        value=config.get('ws_path', '/'),
        help="WebSocket connection path"
    )
    
    config['vless_port'] = st.text_input(
        "Port", 
        value=config.get('vless_port', '443'),
        help="VLESS server port (usually 443)"
    )
    
    config['local_socks_port'] = st.text_input(
        "Local SOCKS Port", 
        value=config.get('local_socks_port', '1080'),
        help="Local proxy port for testing"
    )

# Test IP Configuration
st.sidebar.subheader("Test IP Configuration")
test_ip_default = "173.245.49.235"
test_ip = st.sidebar.text_input(
    "Known Good Test IP",
    value=test_ip_default,
    help="This IP confirms your VLESS server works correctly"
)

include_test_ip = st.sidebar.checkbox(
    "Include test IP in scan",
    value=True,
    help="Add the test IP to the list of IPs to scan"
)

# Download current config
st.sidebar.subheader("💾 Export Configuration")
col1, col2 = st.sidebar.columns(2)
with col1:
    config_yaml_str = yaml.dump(config, default_flow_style=False)
    st.download_button(
        label="📥 Download YAML",
        data=config_yaml_str,
        file_name="config.yaml",
        mime="text/yaml"
    )

with col2:
    if st.button("🔄 Reset Config"):
        st.session_state.current_config = None
        st.rerun()

# ==================== SIDEBAR: SCAN PARAMETERS ====================
st.sidebar.markdown("---")
st.sidebar.title("🎛️ Scan Parameters")

# Preset selection
preset = st.sidebar.selectbox(
    "Choose Preset",
    ["🐌 Slow Internet (Safe)", "💨Fast Internet (Aggressive)", "🎛️ Custom"],
    help="Optimised settings for different connection speeds"
)

# Apply preset values
if preset == "🐌 Slow Internet (Safe)":
    default_timeout = 30
    default_test_duration = 10
    default_ip_num = 10
    default_concurrent = 1
elif preset == "💨 Fast Internet (Aggressive)":
    default_timeout = 10
    default_test_duration = 5
    default_ip_num = 20
    default_concurrent = 3
else:  # Custom
    default_timeout = int(config.get('timeout', 20))
    default_test_duration = int(config.get('test_duration', 5))
    default_ip_num = int(config.get('ip_num', 20))
    default_concurrent = 1

# Advanced controls
with st.sidebar.expander("⚙️ Advanced Controls", expanded=(preset == "🎛️ Custom")):
    connection_timeout = st.slider(
        "Connection Timeout (seconds)",
        min_value=5,
        max_value=60,
        value=default_timeout,
        help="How long to wait for each connection"
    )
    
    test_duration = st.slider(
        "Speed Test Duration (seconds)",
        min_value=3,
        max_value=30,
        value=default_test_duration,
        help="Duration of download speed test"
    )
    
    ip_num = st.slider(
        "Number of IPs to Test",
        min_value=5,
        max_value=50,
        value=default_ip_num,
        help="How many IPs to test with VLESS"
    )
    
    tcp_ping_timeout = st.slider(
        "TCP Ping Timeout (seconds)",
        min_value=1,
        max_value=5,
        value=2,
        help="Timeout for initial TCP connectivity test"
    )
    
    retry_failed = st.checkbox(
        "Retry Failed IPs",
        value=False,
        help="Attempt to retry IPs that failed on first attempt"
    )
    
    if retry_failed:
        retry_attempts = st.number_input(
            "Retry Attempts",
            min_value=1,
            max_value=3,
            value=1
        )

# Update config with scan parameters
config['ip_num'] = str(ip_num)
config['timeout'] = connection_timeout
config['test_duration'] = test_duration
config['tcp_ping_timeout'] = tcp_ping_timeout

# Sort by option
st.sidebar.subheader("📊 Results Sorting")
config['sorted_by'] = st.sidebar.selectbox(
    "Sort Results By",
    ["download", "latency"],
    help="How to sort the final results"
)

# ==================== MAIN AREA: TABS ====================
tab1, tab2, tab3, tab4 = st.tabs(["🔍 Scanner", "📊 Results", "🛠️ Diagnostics", "ℹ️ Help"])

# ==================== TAB 1: SCANNER ====================
with tab1:
    st.title("Nahaan - CloudFlare IP Scanner")
    st.markdown("### Test CloudFlare IPs for optimal VLESS connection performance")
    
    # System status
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if check_xray_binary(XRAY_BINARY):
            st.success("✅ xray-core: Ready")
        else:
            st.error("❌ xray-core: Not Found")
    
    with col2:
        port = int(config.get('local_socks_port', 1080))
        if check_port_availability(port):
            st.success(f"✅ Port {port}: Available")
        else:
            st.warning(f"⚠️ Port {port}: In Use")
    
    with col3:
        validation = validate_config(config)
        if validation['valid']:
            st.success("✅ Config: Valid")
        else:
            st.error(f"❌ Config: {validation['error']}")
    
    st.markdown("---")
    
    # Scan control buttons
# Callback functions for button state management
    def start_scan_callback():
        st.session_state.scan_running = True
        st.session_state.quick_test_mode = False
        st.session_state.logs = []
    
    def quick_test_callback():
        st.session_state.scan_running = True
        st.session_state.quick_test_mode = True
        st.session_state.logs = []
    
    def stop_scan_callback():
        st.session_state.scan_running = False
        st.session_state.stop_requested = True
        # Kill any xray process currently running on the configured port
        try:
            from main import kill_process_on_port
            port = int(st.session_state.current_config.get('local_socks_port', 1080))
            kill_process_on_port(port)
        except:
            pass
        add_log("🛑 Stop command sent. Cleaning up...", "warning")

    # Scan control buttons
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        st.button(
            "▶️ START SCAN",
            type="primary",
            disabled=st.session_state.scan_running,
            use_container_width=True,
            on_click=start_scan_callback
        )
    
    with col2:
        st.button(
            "⏹️ STOP SCAN",
            type="secondary",
            disabled=not st.session_state.scan_running,
            use_container_width=True,
            on_click=stop_scan_callback
        )
    
    with col3:
        st.button(
            "🔬 Quick Test",
            help="Test only 5 IPs",
            use_container_width=True,
            disabled=st.session_state.scan_running,
            on_click=quick_test_callback
        )
    
    # Start scan logic
    if st.session_state.scan_running:
        if not check_xray_binary(XRAY_BINARY):
            st.error("❌ xray-core binary not found! Please ensure xray.exe is in converters/xray-core/")
        else:
            
            # Save config
            save_config_yaml(config, CONFIG_FILE)
            
            if st.session_state.scan_running:
                # Quick test mode
                if st.session_state.get('quick_test_mode', False):
                    config['ip_num'] = '3'
                    add_log("🔬 Quick test mode: Testing only 3 IPs", "info")
            
            # Progress containers
            progress_container = st.container()
            log_container = st.container()
            
            with progress_container:
                st.markdown("### 📊 Scan Progress")
                
                # Phase 1: DNS Collection
                with st.status("🔍︎ Phase 1: DNS Collection", expanded=True) as status:
                    dns_progress = st.progress(0)
                    dns_status = st.empty()
                    
                    add_log("Collecting CloudFlare IPs from DNS providers...", "info")
                    
                    try:
                        # Import and run DNS resolver
                        from cf_editor.cf_ip_rev2 import DNSResolver
                        
                        resolver = DNSResolver()
                        collected_ips = resolver.collect(use_cloudflare_ranges=True)
                        resolver.export_handler(collected_ips)
                        
                        dns_progress.progress(100)
                        dns_status.success(f"✅ Collected {len(collected_ips['ipv4'])} IPs")
                        add_log(f"✅ Collected {len(collected_ips['ipv4'])} IPs", "success")
                        
                        status.update(label="✅ Phase 1: DNS Collection Complete", state="complete")
                        
                    except Exception as e:
                        st.error(f"❌ DNS collection failed: {e}")
                        add_log(f"❌ DNS collection failed: {e}", "error")
                        st.session_state.scan_running = False
                        st.stop()
                
                # Phase 2: TCP Ping
                with st.status("⇄ Phase 2: TCP Connectivity Test", expanded=True) as status:
                    ping_progress = st.progress(0)
                    ping_status = st.empty()
                    
                    add_log("Testing TCP connectivity (port 443)...", "info")
                    
                    try:
                        sorted_by_ping = resolver.ping_handler(collected_ips)
                        
                        # Add test IP if requested
                        if include_test_ip and test_ip:
                            add_log(f"Adding test IP: {test_ip}", "info")
                            sorted_by_ping.append((test_ip, 0.005, 'TEST'))
                        
                        ping_progress.progress(100)
                        ping_status.success(f"✅ Found {len(sorted_by_ping)} accessible IPs")
                        add_log(f"✅ Found {len(sorted_by_ping)} accessible IPs", "success")
                        status.update(label="✅ Phase 2: TCP Connectivity Complete", state="complete")
                        
                    except Exception as e:
                        st.error(f"❌ TCP ping failed: {e}")
                        add_log(f"❌ TCP ping failed: {e}", "error")
                        st.session_state.scan_running = False
                        st.stop()

                # Phase 3: VLESS Speed Test
                with st.status("⏲ Phase 3: VLESS Speed Test", expanded=True) as status:
                    st.markdown(f"**Testing top {ip_num} IPs with actual VLESS connections**")
                    vless_progress = st.progress(0)
                    vless_status = st.empty()
                    current_test = st.empty()
                    
                    add_log(f"Starting VLESS speed tests on {ip_num} IPs...", "info")
                    
                    # Import test function
                    from main import test_vless_connection, generate_vless_config, kill_process_on_port
                    
                    # Free up port
                    socks_port = int(config.get('local_socks_port', 1080))
                    if not check_port_availability(socks_port):
                        add_log(f"Port {socks_port} in use, attempting to free...", "warning")
                        kill_process_on_port(socks_port)
                        time.sleep(1)
                    
                    result_list = []
                    test_ips = list(reversed(sorted_by_ping[-ip_num:]))
                    
                    VLESS_TEMPLATE_FILE = os.path.join(CURRENT_DIR, 'config', 'template_config_vless.json')
                    
                    for idx, ip_tuple in enumerate(test_ips, 1):
                        if st.session_state.get('stop_requested', False):
                            add_log("⏹️ Scan stopped by user", "warning")
                            # Reset flags
                            st.session_state.stop_requested = False
                            st.session_state.scan_running = False
                            st.rerun()
                            
                            # Force kill any hanging xray process on your socks port
                            kill_process_on_port(int(config.get('local_socks_port', 1080)))
                            
                            st.warning("Scan stopped by user. Cleaning up background processes...")
                            st.stop()

                        ip = ip_tuple[0]
                        ping_ms = round(float(ip_tuple[1] * 1000), 1)
                        
                        current_test.info(f"🔬 Testing: **{ip}** (ping: {ping_ms}ms)")
                        add_log(f"Testing {ip} (ping: {ping_ms}ms)", "info")
                        
                        # Generate config
                        config_file = generate_vless_config(VLESS_TEMPLATE_FILE, config, ip)
                        
                        # Test connection
                        result = test_vless_connection(
                            config_file, 
                            timeout=connection_timeout,
                            debug=False
                        )
                        
                        # Clean up
                        try:
                            os.unlink(config_file)
                        except:
                            pass
                        
                        if result is None:
                            add_log(f"❌ {ip} - Connection failed", "error")
                        else:
                            add_log(f"✅ {ip} - {result['download_rate']} @ {result['latency_rate']}", "success")
                            result['address_str'] = ip
                            result['port_str'] = config.get('vless_port')
                            result['uuid_str'] = config.get('vless_uuid')
                            result['operator'] = ip_tuple[2] if len(ip_tuple) > 2 else 'Unknown'
                            result_list.append(result)
                        
                        # Update progress
                        progress_pct = int((idx / len(test_ips)) * 100)
                        vless_progress.progress(progress_pct)
                        vless_status.info(f"Progress: {idx}/{len(test_ips)} ({progress_pct}%) | ✅ {len(result_list)} passed")
                        
                        time.sleep(0.5)
                        # Check for stop request
                        if st.session_state.get('stop_requested', False):
                            add_log("⏹️ Scan stopped by user", "warning")
                            st.session_state.stop_requested = False
                            break
                    
                    vless_progress.progress(100)
                    
                    if result_list:
                        add_log(f"✅ Scan complete! Found {len(result_list)} working IPs", "success")
                        status.update(label=f"✅ Phase 3: Found {len(result_list)} Working IPs", state="complete")
                        
                        # Process results
                        for r in result_list:
                            try:
                                r['download_numeric'] = float(r['download_rate'].replace(' MB/s', ''))
                            except:
                                r['download_numeric'] = 0
                            try:
                                r['latency_numeric'] = float(r['latency_rate'].replace(' ms', ''))
                            except:
                                r['latency_numeric'] = 999999
                        
                        # Sort results
                        sorted_by = config.get('sorted_by', 'download')
                        if sorted_by.lower() == 'download':
                            sorted_list = sorted(result_list, key=lambda d: d['download_numeric'], reverse=True)
                        elif sorted_by.lower() == 'latency':
                            sorted_list = sorted(result_list, key=lambda d: d['latency_numeric'])
                        else:
                            sorted_list = sorted(result_list, key=lambda d: d['download_numeric'], reverse=True)
                        
                        # Save results
                        st.session_state.scan_results = sorted_list
                        
                        # Save to file
                        results_file = os.path.join(RESULTS_DIR, 'vless_tested_list.json')
                        with open(results_file, 'w') as f:
                            json.dump(sorted_list, f, indent=4)
                        
                        # Add to history
                        st.session_state.scan_history.append({
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'ips_tested': len(test_ips),
                            'ips_passed': len(result_list),
                            'best_speed': sorted_list[0]['download_rate'],
                            'best_ip': sorted_list[0]['address_str']
                        })
                        
                        # Display best IP
                        st.success("### 🏆 Scan Complete!")
                        st.markdown(f"""
                        <div class="success-box">
                            <h3>🏆 BEST IP FOUND</h3>
                            <p><strong>IP:</strong> {sorted_list[0]['address_str']}</p>
                            <p><strong>Download:</strong> {sorted_list[0]['download_rate']}</p>
                            <p><strong>Latency:</strong> {sorted_list[0]['latency_rate']}</p>
                            <p><strong>Operator:</strong> {sorted_list[0].get('operator', 'Unknown')}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    else:
                        add_log("❌ No working IPs found", "error")
                        status.update(label="❌ Phase 3: No Working IPs Found", state="error")
                        st.error("❌ No responsive IPs found. Check your VLESS server configuration.")
            
            st.session_state.scan_running = False
            st.rerun()
    
    # Show logs
    if st.session_state.logs:
        with st.expander("📜 View Scan Logs", expanded=False):
            for log in reversed(st.session_state.logs[-50:]):  # Show last 50 logs
                if log['level'] == 'error':
                    st.error(f"[{log['time']}] {log['message']}")
                elif log['level'] == 'warning':
                    st.warning(f"[{log['time']}] {log['message']}")
                elif log['level'] == 'success':
                    st.success(f"[{log['time']}] {log['message']}")
                else:
                    st.info(f"[{log['time']}] {log['message']}")

# ==================== TAB 2: RESULTS ====================
with tab2:
    st.title("📊 Scan Results")
    
    if st.session_state.scan_results:
        results = st.session_state.scan_results
        
        # Convert to DataFrame
        df = pd.DataFrame(results)
        df['Rank'] = range(1, len(df) + 1)
        
        # Display best IP highlight
        best = results[0]
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            st.markdown(f"""
            <div class="success-box">
                <h3>🏆 BEST IP</h3>
                <p><strong>IP:</strong> {best['address_str']}</p>
                <p><strong>Speed:</strong> {best['download_rate']}</p>
                <p><strong>Latency:</strong> {best['latency_rate']}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="success-box">
                <h3>📈 STATISTICS</h3>
                <p><strong>IPs Tested:</strong> {len(results)}</p>
                <p><strong>Avg Speed:</strong> {sum(r['download_numeric'] for r in results) / len(results):.2f} MB/s</p>
                <p><strong>Avg Latency:</strong> {sum(r['latency_numeric'] for r in results) / len(results):.0f} ms</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.button("📋 Copy Best IP", help="Copy to clipboard")
            st.download_button(
                "📥 Export JSON",
                data=json.dumps(results, indent=2),
                file_name=f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
            st.download_button(
                "📥 Export CSV",
                data=export_results_csv(results),
                file_name=f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        st.markdown("---")
        
        # Filters
        st.subheader("🔍 Filter Results")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            min_speed = st.slider(
                "Minimum Speed (MB/s)",
                0.0,
                max(r['download_numeric'] for r in results),
                0.0
            )
        
        with col2:
            max_latency = st.slider(
                "Maximum Latency (ms)",
                0,
                int(max(r['latency_numeric'] for r in results)),
                int(max(r['latency_numeric'] for r in results))
            )
        
        with col3:
            operators = list(set([r.get('operator', 'Unknown') for r in results]))
            selected_operators = st.multiselect(
                "Filter by Operator",
                operators,
                default=operators
            )
        
        # Apply filters
        filtered_results = [
            r for r in results
            if r['download_numeric'] >= min_speed
            and r['latency_numeric'] <= max_latency
            and r.get('operator', 'Unknown') in selected_operators
        ]
        
        # Results table
        st.subheader(f"📋 Results Table ({len(filtered_results)} IPs)")
        
        display_df = pd.DataFrame([{
            'Rank': idx + 1,
            'IP Address': r['address_str'],
            'Download': r['download_rate'],
            'Latency': r['latency_rate'],
            'Operator': r.get('operator', 'Unknown')
        } for idx, r in enumerate(filtered_results)])
        
        st.dataframe(display_df, use_container_width=True, height=400)
        
        # Visualizations
        st.markdown("---")
        st.subheader("📊 Visualizations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Speed distribution histogram
            fig_speed = px.histogram(
                df,
                x='download_numeric',
                nbins=20,
                title="Download Speed Distribution",
                labels={'download_numeric': 'Speed (MB/s)', 'count': 'Frequency'},
                color_discrete_sequence=['#28a745']
            )
            st.plotly_chart(fig_speed, use_container_width=True)
        
        with col2:
            # Latency box plot by operator
            fig_latency = px.box(
                df,
                x='operator',
                y='latency_numeric',
                title="Latency by Operator",
                labels={'latency_numeric': 'Latency (ms)', 'operator': 'Operator'},
                color='operator'
            )
            st.plotly_chart(fig_latency, use_container_width=True)
        
        # Speed vs Latency scatter
        fig_scatter = px.scatter(
            df,
            x='latency_numeric',
            y='download_numeric',
            color='operator',
            size='download_numeric',
            hover_data=['address_str'],
            title="Speed vs Latency",
            labels={'latency_numeric': 'Latency (ms)', 'download_numeric': 'Speed (MB/s)'}
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
        
    else:
        st.info("📭 No results yet. Run a scan to see results here!")
        
        # Show scan history if available
        if st.session_state.scan_history:
            st.subheader("📚 Scan History")
            history_df = pd.DataFrame(st.session_state.scan_history)
            st.dataframe(history_df, use_container_width=True)

# ==================== TAB 3: DIAGNOSTICS ====================
with tab3:
    st.title("🛠️ Diagnostics & Testing")
    
    # System check
    st.subheader("🔍 System Check")
    if st.button("Run System Diagnostics"):
        diagnostics = run_system_diagnostics(XRAY_BINARY, config)
        
        for check in diagnostics:
            if check['status'] == 'pass':
                st.success(f"✅ {check['name']}: {check['message']}")
            elif check['status'] == 'warning':
                st.warning(f"⚠️ {check['name']}: {check['message']}")
            else:
                st.error(f"❌ {check['name']}: {check['message']}")
    
    st.markdown("---")
    
    # Single IP test
    st.subheader("🔬 Test Single IP")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        test_single_ip = st.text_input(
            "Enter IP to test",
            placeholder="e.g., 173.245.49.235",
            help="Test a specific CloudFlare IP"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_single_test = st.button("🚀 Test IP", use_container_width=True)
    
    if run_single_test and test_single_ip:
        with st.spinner(f"Testing {test_single_ip}..."):
            from main import test_vless_connection, generate_vless_config
            
            VLESS_TEMPLATE_FILE = os.path.join(CURRENT_DIR, 'config', 'template_config_vless.json')
            config_file = generate_vless_config(VLESS_TEMPLATE_FILE, config, test_single_ip)
            
            result = test_vless_connection(config_file, timeout=connection_timeout, debug=True)
            
            try:
                os.unlink(config_file)
            except:
                pass
            
            if result:
                st.success(f"✅ Connection Successful!")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Download Speed", result['download_rate'])
                with col2:
                    st.metric("Latency", result['latency_rate'])
            else:
                st.error(f"❌ Connection Failed")
                st.info("Possible issues:\n- Incorrect VLESS configuration\n- IP blocked by ISP\n- Server unreachable")
    
    st.markdown("---")
    
    # Configuration validator
    st.subheader("✅ Configuration Validator")
    if st.button("Validate VLESS Configuration"):
        validation = validate_config(config)
        
        if validation['valid']:
            st.success("✅ Configuration is valid!")
            st.json(config)
        else:
            st.error(f"❌ Configuration Error: {validation['error']}")
            st.info("Please check your config.yaml file and ensure all required fields are present.")

# ==================== TAB 4: HELP ====================
with tab4:
    st.title("ℹ️ Help & Instructions")
    
    st.markdown("""
    ## 📖 Quick Start Guide
    
    ### 1️⃣ Configure Your VLESS Server
    - Upload your `config.yaml` file in the sidebar, or
    - Edit the VLESS settings directly in the form
    
    ### 2️⃣ Choose Scan Preset
    - **Slow Internet**: Safer settings with longer timeouts (recommended for Iran)
    - **Fast Internet**: Aggressive settings for faster scans
    - **Custom**: Adjust all parameters manually
    
    ### 3️⃣ Run the Scan
    - Click "START SCAN" to begin
    - Watch real-time progress through 3 phases:
      1. DNS Collection (gather CloudFlare IPs)
      2. TCP Connectivity (test port 443)
      3. VLESS Speed Test (measure actual performance)
    
    ### 4️⃣ View Results
    - Check the "Results" tab for detailed analysis
    - Export results as JSON or CSV
    - Copy the best IP for use in your VLESS client
    
    ---
    
    ## 🔧 Troubleshooting
    
    ### ❌ "xray-core binary not found"
    **Solution:** Download xray-core from https://github.com/XTLS/Xray-core/releases
    - Extract `xray.exe` to `converters/xray-core/`
    
    ### ⚠️ "Port 1080 in use"
    **Solution:** The app will try to free the port automatically
    - Or change the SOCKS port in configuration
    - Or manually close applications using port 1080
    
    ### ❌ "All IPs failed"
    **Possible causes:**
    - Incorrect VLESS UUID/server configuration
    - CloudFlare IPs blocked by your ISP
    - VLESS server is down
    
    **Solutions:**
    1. Test with the known good IP (173.245.49.235)
    2. Verify your config in the Diagnostics tab
    3. Try "Slow Internet" preset for better reliability
    
    ### ⚠️ Windows Firewall Warning
    **Solution:** Allow xray.exe through Windows Firewall when prompted
    
    ---
    
    ## 🌐 About CloudFlare IPs
    
    This tool helps you find optimal CloudFlare IP addresses that work well with your Iranian ISP.
    
    **Why does this matter?**
    - Some CloudFlare IPs are throttled or blocked by ISPs
    - Different IPs have different routing performance
    - Finding the best IP can significantly improve your connection speed
    
    **ISP Codes:**
    - **MCI**: Mobile Communication Company of Iran (Hamrah Aval)
    - **MTN**: MTN Irancell
    - **MKH**: Mokhaberat (TCI)
    - Others: Regional ISPs
    
    ---
    
    ## 📞 Support
    
    If you encounter issues:
    1. Check the Diagnostics tab for system checks
    2. Review the scan logs in the Scanner tab
    3. Try testing a single IP first
    4. Ensure your VLESS server is accessible
    5. Open an issue
    6. Email me: aminhb@tutanota.com
    
    **Version:** 2.0 (Streamlit Interface)
    """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "CloudFlare IP Scanner v2.0 | Built with Streamlit | "
    "For personal use in improving internet connectivity"
    "</div>",
    unsafe_allow_html=True
)
