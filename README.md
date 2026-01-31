<div align="center">

**🌐 Language / زبان**

[![English](https://img.shields.io/badge/English-blue?style=for-the-badge)](README.md)
[![Farsi](https://img.shields.io/badge/فارسی-green?style=for-the-badge)](README_FA.md)

</div>

---


# CloudFlare IP Scanner - Nahaan

A user-friendly web interface for testing CloudFlare IPs with VLESS connections. Designed for users in Iran to find optimal CloudFlare IPs that work well with their ISP.

## Features

- **Easy Configuration**: Upload or edit your VLESS config directly in the browser
- **Smart Presets**: Optimised settings for slow/fast internet connections
- **Real-Time Progress**: Watch your scan progress through DNS collection, TCP ping, and speed tests
- **Visual Results**: Interactive charts showing speed distribution and operator performance
- **Export Options**: Download results as JSON or CSV
- **Diagnostics**: Built-in system checks and single IP testing
- **Scan History**: Keep track of previous scans

## Installation

### Prerequisites

1. **Python 3.8 or higher**
2. **xray-core binary** (download from https://github.com/XTLS/Xray-core/releases)

### Windows Installation Steps

1. **Install Python** (if not already installed)
   - Download from https://www.python.org/downloads/
   - During installation, check "Add Python to PATH"

2. **Download xray-core**
   ```
   1. Go to: https://github.com/XTLS/Xray-core/releases/latest
   2. Download: Xray-windows-64.zip
   3. Extract xray.exe to: converters/xray-core/xray.exe
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements_streamlit.txt
   ```

4. **Run the Application**
   ```bash
   streamlit run streamlit_app.py
   ```
   
   Or simply double-click `run_streamlit.bat` (Windows)

## Quick Start

### Method 1: Using the Batch File (Windows)

1. Double-click `run_streamlit.bat`
2. Your browser will open automatically
3. Start configuring and scanning!

### Method 2: Command Line

```bash
streamlit run streamlit_app.py
```

The app will open in your default browser at `http://localhost:8501`

## User Guide

### 1. Configuration

#### Upload Config File
- Sidebar → "Upload config.yaml"
- Drag and drop or browse for your configuration file

#### Or Edit Directly
- Sidebar → "Edit VLESS Configuration"
- Enter your VLESS UUID, server name, host header, etc.

#### Test IP Configuration
- Set a "Known Good Test IP" (default: 173.245.49.235)
- This IP confirms your VLESS server works correctly
- Check "Include test IP in scan" to add it to the test list

### 2. Scan Parameters

#### Choose a Preset
- **Slow Internet (Safe)**: Best for Iran's internet conditions
  - Connection timeout: 30s
  - Test duration: 10s
  - IPs to test: 10
  - Recommended for most users

- **Fast Internet (Aggressive)**: For stable connections
  - Connection timeout: 10s
  - Test duration: 5s
  - IPs to test: 20

- **Custom**: Adjust all parameters manually

#### Advanced Controls
- Connection Timeout: How long to wait for each IP
- Speed Test Duration: How long to measure download speed
- Number of IPs to Test: How many IPs to test with VLESS
- TCP Ping Timeout: Initial connectivity check timeout

### 3. Running a Scan

1. Click **"START SCAN"**

2. Watch the progress through 3 phases:
   - **Phase 1**: DNS Collection (gathering CloudFlare IPs)
   - **Phase 2**: TCP Connectivity (testing port 443 access)
   - **Phase 3**: VLESS Speed Test (measuring actual performance)

3. View results in real-time:
   - Progress bars for each phase
   - Live log stream showing each IP being tested
   - Success/failure counters

4. **Quick Test**: Click "Quick Test" to test only 5 IPs (faster)

### 4. Viewing Results

Switch to the **"Results"** tab to see:

- **Best IP Highlight**: The fastest IP found
- **Statistics**: Average speed, latency, number of IPs tested
- **Results Table**: Sortable table of all working IPs
- **Filters**: Filter by speed, latency, or operator
- **Charts**:
  - Speed distribution histogram
  - Latency by operator
  - Speed vs latency scatter plot

#### Export Results
- **Export JSON**: Full results with all details
- **Export CSV**: Spreadsheet-compatible format
- **Copy Best IP**: Quick copy for immediate use

### 5. Diagnostics & Testing

Switch to the **"Diagnostics"** tab:

#### System Check
- Click "Run System Diagnostics"
- Verifies:
  - xray-core binary exists
  - Configuration is valid
  - Port is available
  - Internet connectivity
  - DNS resolution

#### Test Single IP
- Enter any CloudFlare IP
- Click "Test IP"
- See immediate results without a full scan

#### Configuration Validator
- Click "Validate VLESS Configuration"
- Ensures all required fields are present
- Checks for common configuration errors

## Troubleshooting

### "xray-core binary not found"

**Solution:**
1. Download xray-core from: https://github.com/XTLS/Xray-core/releases
2. Extract `xray.exe` to `converters/xray-core/xray.exe`
3. Restart the application

### ⚠️ "Port 1080 in use"

**Solution:**
- The app will try to free the port automatically
- Or change the SOCKS port in configuration (sidebar)
- Or manually close applications using port 1080

### ❌ "All IPs failed"

**Possible Causes:**
- Incorrect VLESS configuration (UUID, server name, etc.)
- CloudFlare IPs blocked by your ISP
- VLESS server is down or unreachable

**Solutions:**
1. Test with the known good IP (173.245.49.235) first
2. Run "System Diagnostics" to check configuration
3. Verify your VLESS server is accessible
4. Try "Slow Internet" preset for better reliability

### 🛡️ Windows Firewall Warning

**Solution:**
- Click "Allow Access" when Windows Firewall prompts
- xray.exe needs network access to function

### Scan is Very Slow

**Solution:**
- Use "Slow Internet" preset (already optimised)
- Reduce "Number of IPs to Test" to 5-10
- Increase timeouts in Advanced Controls

## 📊 Understanding Results

### ISP Operator Codes

- **MCI**: Mobile Communication Company of Iran (Hamrah Aval)
- **MTN**: MTN Irancell  
- **MKH**: Mokhaberat (TCI)
- **TEST**: Test IP you specified
- Others: Regional ISPs (HWB, AST, SHT, etc.)

### Interpreting Results

- **Download Speed**: Higher is better (aim for >5 MB/s)
- **Latency**: Lower is better (aim for <100 ms)
- **Operator**: Shows which ISP works best with that IP

### Using Results

1. **Best IP**: The top result is usually the best choice
2. **Operator Match**: IPs matching your ISP often work better
3. **Backup IPs**: Save top 3-5 IPs for alternates
4. **Re-test**: Performance can change daily, scan regularly

## Security & Privacy

- **Local Operation**: All testing runs on your computer
- **No Data Collection**: No data sent to external servers
- **Config Privacy**: Your VLESS config stays on your machine
- **Export Control**: You control what to export and share

## File Structure

```
NahaanCFScanner/
├── streamlit_app.py              # Main interface
├── streamlit_helpers.py          # Helper functions
├── main.py                       # Core scanner engine
├── config/
│   ├── config.yaml               # Your VLESS configuration
│   └── template_config_vless.json # VLESS template
├── converters/
│   └── xray-core/
│       └── xray.exe              # xray-core binary
├── results/
│   ├── list.json                 # Collected IPs
│   ├── sorted_list.txt           # Ping-sorted IPs
│   └── vless_tested_list.json    # Speed test results
├── cf_editor/
│   ├── cf_ip_rev2.py             # DNS resolver
│   ├── providers.json            # DNS providers
│   └── list.json                 # IP database
└── requirements_streamlit.txt     # Dependencies
```

## Tips for Best Results

1. **Use Slow Internet Preset**: Most reliable for Iran
2. **Test During Off-Peak Hours**: Better results at night
3. **Regular Scanning**: IP performance changes daily
4. **Save Multiple IPs**: Keep 3-5 good IPs as backups
5. **Operator Matching**: Prefer IPs matching your ISP
6. **Test First**: Use "Quick Test" before full scan

## Common Questions

### Q: Why are some IPs faster than others?

**A:** Different CloudFlare IPs have different routing to Iran. Some routes are throttled or congested, others work better.

### Q: How often should I scan?

**A:** Weekly or when you notice speed degradation. IP performance changes over time.

### Q: Can I use this on Linux?

**A:** Yes! The app works on Windows, Linux, and macOS. Just use the appropriate xray binary.

### Q: Is this safe to use?

**A:** Yes. The tool only tests publicly available CloudFlare IPs. However, always ensure your VLESS server configuration is secure.

### Q: Why does scanning take so long?

**A:** Each IP needs:
1. TCP connection test (~2 seconds)
2. VLESS connection setup (~3 seconds)
3. Speed test (~5-10 seconds)

With 20 IPs, this takes 3-5 minutes.

### Q: Can I run multiple scans simultaneously?

**A:** No. Only one scan at a time to avoid port conflicts.

## Support

If you encounter issues:

1. Check the "🛠️ Diagnostics" tab
2. Review scan logs in the "🔍 Scanner" tab
3. Try "Test Single IP" first with the known good IP
4. Verify your VLESS server is accessible independently

## Version History

- **v2.0** (2026-01-30): Streamlit interface release
  - User-friendly web interface
  - Real-time progress tracking
  - Interactive charts and visualizations
  - Built-in diagnostics

- **v1.0**: Command-line interface
  - Original Python script version

## Credits

- **Original VMESS Scanner**: Farid Vahid (https://github.com/vfarid)
- **VLESS Migration & Streamlit UI**: Nahaangard
- **xray-core**: XTLS Project (https://github.com/XTLS/Xray-core)

## Licence

For personal use. Help improve internet connectivity for users in restricted environments.

---

**Version:** 2.0  
**Last Updated:** 2026-01-30  
**Built with:** Python, Streamlit, xray-core
