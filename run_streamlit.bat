@echo off
REM CloudFlare IP Scanner - Streamlit Launcher
REM Double-click this file to start the web interface

echo.
echo ========================================
echo   CloudFlare IP Scanner
echo   Starting Streamlit Interface...
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo.
    echo Please install Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

REM Check if Streamlit is installed
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo Streamlit is not installed. Installing dependencies...
    echo.
    pip install -r requirements_streamlit.txt
    echo.
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        echo.
        pause
        exit /b 1
    )
)

REM Check if xray.exe exists
if not exist "converters\xray-core\xray.exe" (
    echo WARNING: xray.exe not found!
    echo.
    echo Please download xray-core from:
    echo https://github.com/XTLS/Xray-core/releases
    echo.
    echo Extract xray.exe to: converters\xray-core\xray.exe
    echo.
    pause
    exit /b 1
)

echo Starting Streamlit...
echo.
echo The app will open in your browser automatically.
echo Press Ctrl+C to stop the server.
echo.

REM Start Streamlit
streamlit run streamlit_app.py --server.headless true

pause
