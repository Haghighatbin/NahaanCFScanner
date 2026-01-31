#!/usr/bin/env python3
"""
Standalone test to verify xray-core and VLESS config work properly
Run this BEFORE running the full scanner
"""
import json
import subprocess
import time
import socket
import requests
import yaml
import os

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def kill_process_on_port(port: int) -> bool:
    """
    Kills any process using the specified port
    
    Args:
        port: Port number to free up
    
    Returns:
        True if a process was killed, False if port was already free
    """
    try:
        if os.name == 'nt':  # Windows
            # Find PID using netstat
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True
            )
            
            # Parse output to find PID
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    # Extract PID (last column)
                    parts = line.split()
                    if parts:
                        pid = parts[-1]
                        try:
                            # Kill the process
                            subprocess.run(
                                ['taskkill', '/PID', pid, '/F'],
                                capture_output=True
                            )
                            print(f'[Killed process {pid} using port {port}]')
                            time.sleep(0.5)  # Wait for port to be freed
                            return True
                        except:
                            pass
        else:  # Linux/Mac
            # Find PID using lsof
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True,
                text=True
            )
            
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        subprocess.run(['kill', '-9', pid])
                        print(f'{bColours.YELLOW}[Killed process {pid} using port {port}]{bColours.ENDC}')
                        time.sleep(0.5)
                        return True
                    except:
                        pass
        
        return False
        
    except Exception as e:
        print(f'[Warning] Could not check/kill processes on port {port}: {e}')
        return False


def is_port_available(port: int) -> bool:
    """
    Check if a port is available for binding
    
    Args:
        port: Port number to check
    
    Returns:
        True if port is free, False if in use
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.bind(('127.0.0.1', port))
        sock.close()
        return True
    except (OSError, socket.error):
        return False

def test_xray_binary():
    """Test if xray-core binary exists and is executable"""
    print(f"\n{Colors.BLUE}[TEST 1] Checking xray-core binary...{Colors.END}")
    
    xray_path = os.path.join('.', 'converters', 'xray-core', 
                            'xray.exe' if os.name == 'nt' else 'xray')    

    if not os.path.exists(xray_path):
        print(f"{Colors.RED}✗ FAIL: xray binary not found at {xray_path}{Colors.END}")
        return False
    
    # Try to get version
    try:
        result = subprocess.run([xray_path, '-version'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"{Colors.GREEN}✓ PASS: {version}{Colors.END}")
            return True
        else:
            print(f"{Colors.RED}✗ FAIL: xray returned error: {result.stderr}{Colors.END}")
            return False
    except Exception as e:
        print(f"{Colors.RED}✗ FAIL: Cannot execute xray: {e}{Colors.END}")
        return False

def test_config_generation():
    """Test if we can generate a valid VLESS config"""
    print(f"\n{Colors.BLUE}[TEST 2] Testing config generation...{Colors.END}")
    
    try:
        # Load config.yaml
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Load template
        with open('config/template_config_vless.json', 'r') as f:
            template = json.load(f)
        
        # Replace placeholders with a known good CloudFlare IP (1.1.1.1 for testing)
        test_ip = "173.245.49.235"  # CloudFlare's own IP
        template['outbounds'][0]['settings']['vnext'][0]['address'] = test_ip
        template['outbounds'][0]['settings']['vnext'][0]['port'] = int(config.get('vless_port'))
        template['outbounds'][0]['settings']['vnext'][0]['users'][0]['id'] = config.get('vless_uuid')
        template['outbounds'][0]['streamSettings']['tlsSettings']['serverName'] = config.get('server_name')
        template['outbounds'][0]['streamSettings']['wsSettings']['path'] = config.get('ws_path')
        template['outbounds'][0]['streamSettings']['wsSettings']['headers']['Host'] = config.get('host_header')
        template['inbounds'][0]['port'] = int(config.get('local_socks_port'))
        
        # Write test config
        with open('config/test_vless_config.json', 'w') as f:
            json.dump(template, f, indent=2)
        
        print(f"{Colors.GREEN}✓ PASS: Config generated successfully{Colors.END}")
        print(f"  UUID: {config.get('vless_uuid')[:8]}...")
        print(f"  Server: {config.get('server_name')}")
        print(f"  Test IP: {test_ip}")
        return True
        
    except Exception as e:
        print(f"{Colors.RED}✗ FAIL: Config generation error: {e}{Colors.END}")
        return False

def test_xray_startup():
    """Test if xray-core can start with the generated config"""
    print(f"\n{Colors.BLUE}[TEST 3] Testing xray-core startup...{Colors.END}")
    
    xray_path = 'converters/xray-core/xray.exe'
    config_file = 'config/test_vless_config.json'
    
    try:
        # Start xray
        process = subprocess.Popen(
            [xray_path, '-config', config_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print(process)
        
        # Wait a bit for startup
        time.sleep(2)
        
        # Check if it's still running
        poll = process.poll()
        if poll is not None:
            stdout, stderr = process.communicate(timeout=1)
            print(f"{Colors.RED}✗ FAIL: xray-core died immediately{Colors.END}")
            print(f"{Colors.YELLOW}Exit code: {poll}{Colors.END}")
            print(f"{Colors.YELLOW}STDERR:{Colors.END}")
            print(stderr[:1000])
            return False
        
        # Check if SOCKS proxy is listening
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(('127.0.0.1', 1080))
            sock.close()
            print(f"{Colors.GREEN}✓ PASS: xray-core started, SOCKS proxy listening on port 1080{Colors.END}")
            
            # Clean up
            process.terminate()
            process.wait(timeout=3)
            return True
            
        except Exception as e:
            print(f"{Colors.RED}✗ FAIL: SOCKS proxy not listening: {e}{Colors.END}")
            process.terminate()
            return False
            
    except Exception as e:
        print(f"{Colors.RED}✗ FAIL: Cannot start xray-core: {e}{Colors.END}")
        return False

def test_vless_connection():
    """Test actual connection through the VLESS proxy"""
    print(f"\n{Colors.BLUE}[TEST 4] Testing VLESS connection...{Colors.END}")
    
    xray_path = 'converters/xray-core/xray.exe'
    config_file = 'config/test_vless_config.json'
    
    # ADD THESE LINES HERE:
    print(f"\n  {Colors.YELLOW}[DEBUG] Generated config:{Colors.END}")
    with open(config_file, 'r') as f:
        config_content = json.load(f)
        print(json.dumps(config_content, indent=2))
    print()
    
    process = None
    try:
        # Start xray
        process = subprocess.Popen(
            [xray_path, '-config', config_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        time.sleep(3)
        
        # Try to connect through proxy
        proxies = {
            'http': 'socks5h://127.0.0.1:1080',
            'https': 'socks5h://127.0.0.1:1080'
        }
        
        print(f"  Attempting connection through proxy...")
        response = requests.get(
            'http://www.gstatic.com/generate_204',
            proxies=proxies,
            timeout=20
        )
        
        if response.status_code == 204:
            print(f"{Colors.GREEN}✓ PASS: Successfully connected through VLESS proxy!{Colors.END}")
            print(f"  Your VLESS server is working correctly")
            return True
        else:
            print(f"{Colors.YELLOW}⚠ WARNING: Connection succeeded but unexpected status: {response.status_code}{Colors.END}")
            return False
            
    except requests.exceptions.ProxyError as e:
        print(f"{Colors.RED}✗ FAIL: Proxy connection error{Colors.END}")
        print(f"{Colors.YELLOW}This usually means:{Colors.END}")
        print(f"  • Your VLESS UUID is incorrect")
        print(f"  • Your serverName (SNI) is wrong")
        print(f"  • Your Host header doesn't match")
        print(f"  • Your VLESS server is down/unreachable")
        return False
        
    except requests.exceptions.Timeout:
        print(f"{Colors.RED}✗ FAIL: Connection timeout{Colors.END}")
        print(f"  VLESS server took too long to respond")
        return False
        
    except Exception as e:
        print(f"{Colors.RED}✗ FAIL: {type(e).__name__}: {e}{Colors.END}")
        return False
        
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=3)
            except:
                process.kill()

def main():
    print(f"\n{Colors.BLUE}═══════════════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.BLUE}  VLESS Scanner Diagnostic Test{Colors.END}")
    print(f"{Colors.BLUE}═══════════════════════════════════════════════════════{Colors.END}")
    
    tests = [
        ("xray-core binary", test_xray_binary),
        ("Config generation", test_config_generation),
        ("xray-core startup", test_xray_startup),
        ("VLESS connection", test_vless_connection),
    ]
    
    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
        
        if not result:
            print(f"\n{Colors.RED}════════════════════════════════════════════════════════{Colors.END}")
            print(f"{Colors.RED}Test failed at: {name}{Colors.END}")
            print(f"{Colors.RED}Fix this issue before running the full scanner{Colors.END}")
            print(f"{Colors.RED}════════════════════════════════════════════════════════{Colors.END}")
            return
    
    # All tests passed
    print(f"\n{Colors.GREEN}════════════════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.GREEN}✓ ALL TESTS PASSED!{Colors.END}")
    print(f"{Colors.GREEN}════════════════════════════════════════════════════════{Colors.END}")
    print(f"\n{Colors.GREEN}Your setup is working correctly.{Colors.END}")
    print(f"{Colors.GREEN}You can now run: python main.py{Colors.END}\n")

if __name__ == "__main__":
    main()