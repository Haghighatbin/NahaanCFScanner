#!/bin/bash
# CloudFlare IP Scanner - Streamlit Launcher
# Run this script to start the web interface

echo ""
echo "========================================"
echo "  CloudFlare IP Scanner"
echo "  Starting Streamlit Interface..."
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo ""
    echo "Please install Python 3:"
    echo "  - Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "  - macOS: brew install python3"
    echo ""
    exit 1
fi

# Check if Streamlit is installed
if ! python3 -c "import streamlit" &> /dev/null; then
    echo "Streamlit is not installed. Installing dependencies..."
    echo ""
    pip3 install -r requirements_streamlit.txt
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies"
        echo ""
        exit 1
    fi
fi

# Check if xray binary exists
if [ ! -f "converters/xray-core/xray" ]; then
    echo "WARNING: xray binary not found!"
    echo ""
    echo "Please download xray-core from:"
    echo "https://github.com/XTLS/Xray-core/releases"
    echo ""
    echo "Extract the 'xray' binary to: converters/xray-core/xray"
    echo "Then run: chmod +x converters/xray-core/xray"
    echo ""
    exit 1
fi

# Make xray executable if not already
chmod +x converters/xray-core/xray 2>/dev/null

echo "Starting Streamlit..."
echo ""
echo "The app will open in your browser automatically."
echo "Press Ctrl+C to stop the server."
echo ""

# Start Streamlit
streamlit run streamlit_app.py --server.headless true
