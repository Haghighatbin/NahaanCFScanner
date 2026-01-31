#!/usr/bin/env python3
import logging
import json
import os
import requests
import socket
import subprocess
import sys
import tempfile
import yaml

from prettytable import PrettyTable
from time import sleep, time

from rich.console import Console
from cf_editor.cf_ip_rev2 import DNSResolver


console = Console()


# Enable ANSI colours on Windows
if sys.platform == 'win32':
    import os
    os.system('')  # Enables ANSI escape codes in Windows 10+

__version__ = 2.01
__author__ = 'Nahaangard'


# Defining Paths
CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
VLESS_CONFIG_DIR = os.path.join(CURRENT_DIR, 'config')
VLESS_TEMPLATE_FILE = os.path.join(VLESS_CONFIG_DIR, "template_config_vless.json")
SCRIPT_ROOT = os.path.dirname(os.path.realpath(__file__))
SCANNER_CONFIG = os.path.join(SCRIPT_ROOT, 'config.yaml')
XRAY_BINARY = os.path.join(
    CURRENT_DIR,
    'converters',
    'xray-core',
    'xray.exe' if os.name == 'nt' else 'xray'
    )

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
                            console.console.print(f'[Killed process {pid} using port {port}]', style='bold yellow')
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
                        console.console.print(f'[Killed process {pid} using port {port}]', style='bold yellow')
                        time.sleep(0.5)
                        return True
                    except:
                        pass
        
        return False
        
    except Exception as e:
        console.console.print(f'[Warning] Could not check/kill processes on port {port}: {e}', style='bold yellow')
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

def generate_vless_config(template_path: str, config: dict, ip_address: str) -> str:
    """
    Generates a VLESS config file for a specific IP address
    
    Args:
        template_path: Path to the template config file
        config: Configuration dictionary from config.yaml
        ip_address: IP address to test
    
    Returns:
        Path to the generated config file
    """
    with open(template_path, 'r') as f:
        vless_config = json.load(f)
    
    # Replace placeholders
    vless_config['outbounds'][0]['settings']['vnext'][0]['address'] = ip_address
    vless_config['outbounds'][0]['settings']['vnext'][0]['port'] = int(config.get('vless_port'))
    vless_config['outbounds'][0]['settings']['vnext'][0]['users'][0]['id'] = config.get('vless_uuid')
    
    vless_config['outbounds'][0]['streamSettings']['tlsSettings']['serverName'] = config.get('server_name')
    vless_config['outbounds'][0]['streamSettings']['wsSettings']['path'] = config.get('ws_path')
    vless_config['outbounds'][0]['streamSettings']['wsSettings']['headers']['Host'] = config.get('host_header')
    
    vless_config['inbounds'][0]['port'] = int(config.get('local_socks_port'))
    
    # Write to temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    temp_file.write(json.dumps(vless_config, indent=2))
    # json.dump(vless_config, temp_file, indent=2)
    temp_file.close()
    
    return temp_file.name

def test_vless_connection(config_file: str, test_url: str = "http://www.gstatic.com/generate_204", timeout: int = 20, debug: bool = False) -> dict:
    """
    Tests a VLESS connection by starting xray-core and measuring download speed
    
    Args:
        config_file: Path to the xray-core config file
        test_url: URL to test download speed
        timeout: Connection timeout in seconds
    
    Returns:
        Dictionary with download_rate, upload_rate, latency_rate, or None if failed
    """
    xray_process = None
    try:
        # Start xray-core with the config
        xray_process = subprocess.Popen(
            [XRAY_BINARY, '-config', config_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Wait for xray to initialise
        sleep(3)

        if debug:
            # Show the config being used
            with open(config_file, 'r') as f:
                console.console.print(f"\n[DEBUG] Config file:", style='bold yellow')
                console.console.print(json.dumps(json.load(f), indent=2)[:2000])
            
            # Check if xray died
            poll_result = xray_process.poll()
            if poll_result is not None:
                stdout, stderr = xray_process.communicate(timeout=20)
                console.console.print(f"[DEBUG] xray died! Exit: {poll_result}", style='bold red')
                console.console.print(f"STDERR: {stderr[:500]}", style='bold yellow')
                return None
        # Test connection through SOCKS proxy
        proxies = {
            'http': 'socks5h://127.0.0.1:1080',
            'https': 'socks5h://127.0.0.1:1080'
        }
        
        # Latency test
        start_time = time()
        response = requests.get(test_url, proxies=proxies, timeout=timeout)
        latency = (time() - start_time) * 1000  # Convert to ms
        
        if response.status_code != 204:
            return None
        
        # Download speed test (10MB file from CloudFlare)
        download_url = "https://speed.cloudflare.com/__down?bytes=10000000"
        start_time = time()
        response = requests.get(download_url, proxies=proxies, timeout=timeout, stream=True)
        
        downloaded = 0
        for chunk in response.iter_content(chunk_size=8192):
            downloaded += len(chunk)
            if time() - start_time > 5:  # 5 second test
                break
        
        elapsed = time() - start_time
        download_speed = (downloaded / 1024 / 1024) / elapsed  # MB/s
        
        return {
            'download_rate': f"{download_speed:.2f} MB/s",
            'upload_rate': "N/A",  # Upload test not implemented yet
            'latency_rate': f"{latency:.0f} ms"
        }
        
    except Exception as e:
        return None
    
    finally:
        if xray_process:
            try:
                if os.name == 'nt':
                    xray_process.kill()
                else:
                    xray_process.terminate()
                
                xray_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                xray_process.kill()
                xray_process.wait()
            except:
                pass

def main():
    logger = logging.getLogger(__name__)
    
    console.print(f'[Verifying the scanner CONFIG.YAML file]', style='bold blue')
    if not os.path.isfile(SCANNER_CONFIG):
        logger.exception('Unable to find config.yaml file!')
        raise Exception('Unable to find config.yaml file!')

    with open(SCANNER_CONFIG, 'r') as f:
        config = yaml.safe_load(f)
    console.print(f'[Settings extracted from CONFIG.YAML]', style='green')

    # Check and free up the SOCKS port
    socks_port = int(config.get('local_socks_port', 1080))
    console.print(f'[Checking port {socks_port} availability]', style='bold blue')
    
    if not is_port_available(socks_port):
        console.print(f'[Port {socks_port} is in use, attempting to free it]', style='bold yellow')
        kill_process_on_port(socks_port)
        
        # Verify port is now free
        time.sleep(1)
        if not is_port_available(socks_port):
            console.print(f'[ERROR] Could not free port {socks_port}', style='bold red')
            console.print(f'[TIP] Manually close applications using port {socks_port} or change config.yaml', style='bold yellow')
            exit(1)
        else:
            console.print(f'[✓ Port {socks_port} is now available]', style='bold green')
    else:
        console.print(f'[✓ Port {socks_port} is available]', style='bold green')


    console.print(f"[VLESS Configuration Loaded]", style='blue')
    console.print(f"UUID: {config.get('vless_uuid')[:8]}...", style='cyan')
    console.print(f"Server: {config.get('server_name')}", style='cyan')
    console.print(f"Port: {config.get('vless_port')}", style='cyan')
    
    # Check if xray binary exists
    if not os.path.exists(XRAY_BINARY):
        console.print(f"[ERROR] xray-core binary not found at: {XRAY_BINARY}", style='red')
        console.print(f"[TIP] Download xray-core from: https://github.com/XTLS/Xray-core/releases", style='bold yellow')
        exit(1)
    
    ip_num = int(config.get('ip_num', 10))
    
    try:
        # Calling DNS resolver
        console.print(f'\n[Starting DNS Resolution and Ping Tests]', style='blue')
        resolver = DNSResolver()
        collected_ips = resolver.collect(use_cloudflare_ranges=True)
        resolver.export_handler(collected_ips)

        # Sorting out IPs based on their ping results
        sorted_by_ping = resolver.ping_handler(collected_ips)
        console.print(f'[Adding known-good test IP: 173.245.49.235]', style='cyan')
        sorted_by_ping.append(('173.245.49.235', 0.005, 'TEST'))
        _resp = input(f'\nWould you like to test the top {ip_num} ping-sorted IPs with actual VLESS connections?\n(y: proceed with VLESS speedtest | n: exit) [y/n] ')
        if _resp.lower() != 'y':
            console.print('\nExiting without speedtest.')
            exit()

        console.print(f'\n[Initialising speedtest on top {ip_num} IPs via VLESS configs]', style='cyan')
        console.print(f'[This will take several minutes, please be patient]', style='cyan')

        init_time = time()
        result_list = []

        # Test top N IPs with actual VLESS configs
        test_ips = list(reversed(sorted_by_ping[-ip_num:]))
        
        with console.status("[bold green]Testing VLESS Connections...") as status:
            for idx, ip_tuple in enumerate(test_ips, 1):
                ip = ip_tuple[0]
                ping_ms = round(float(ip_tuple[1] * 1000), 1)
                
                console.print(f'[{idx}/{ip_num}] Testing connection -> {ip} (ping: {ping_ms}ms)', style='blue')
                
                # Generate config for this IP
                config_file = generate_vless_config(VLESS_TEMPLATE_FILE, config, ip)
                
                # Test the connection
                is_test_ip = (ip == '173.245.49.235')
                # result = test_vless_connection(config_file, debug=is_test_ip) #True
                result = test_vless_connection(config_file, debug=False)
                
                # Clean up config file
                try:
                    os.unlink(config_file)
                except:
                    pass
                
                if result is None:
                    console.print(f'✗ IP [{ip}] failed - unresponsive or connection error', style='bold red')
                else:
                    console.print(f'✓ IP [{ip}] - {result["download_rate"]} - {result["latency_rate"]}', style='bold green')
                    result['address_str'] = ip
                    result['port_str'] = config.get('vless_port')
                    result['uuid_str'] = config.get('vless_uuid')
                    result_list.append(result)
                
                sleep(1)

        if result_list:
            console.print(f'\n[Processing Results]', style='blue')
            
            # Parse numeric values for sorting
            for r in result_list:
                try:
                    r['download_numeric'] = float(r['download_rate'].replace(' MB/s', ''))
                except:
                    r['download_numeric'] = 0
                try:
                    r['latency_numeric'] = float(r['latency_rate'].replace(' ms', ''))
                except:
                    r['latency_numeric'] = 999999

            table = PrettyTable()
            sorted_by = config.get('sorted_by', 'download')
            
            console.print(f'[Sorting results by {sorted_by.upper()}]', style='blue')
            
            if sorted_by.lower() == 'download':
                sorted_list = sorted(result_list, key=lambda d: d['download_numeric'], reverse=True)
            elif sorted_by.lower() == 'latency':
                sorted_list = sorted(result_list, key=lambda d: d['latency_numeric'])
            else:
                sorted_list = sorted(result_list, key=lambda d: d['download_numeric'], reverse=True)

            table.field_names = ["Rank", "IP Address", "Download", "Latency", "Port"]

            with open('./results/vless_tested_list.json', 'w') as json_file:
                json_file.write(json.dumps(sorted_list, indent=4))

            for idx, dct in enumerate(sorted_list, 1):
                table.add_row([
                    idx,
                    dct['address_str'],
                    dct['download_rate'],
                    dct['latency_rate'],
                    dct['port_str']
                ])

            console.print(f'\n╔═══════════════════════════════════════════════════════╗', style='bold green')
            console.print(f' ║           VLESS IP SPEEDTEST RESULTS                  ║', style='bold green')
            console.print(f' ╚═══════════════════════════════════════════════════════╝\n', style='bold green')
            console.print(table)
            console.print(f'\n⏱  Total elapsed time: {round((time() - init_time), 1)}s', style='cyan')
            console.print(f'📊 Results saved to: ./results/vless_tested_list.json', style='cyan')
            
            # console.print best IP info
            best_ip = sorted_list[0]
            console.print(f'\n🏆 BEST IP: {best_ip["address_str"]} ({best_ip["download_rate"]})\n', style='green')
            
            console.print('Done.')

        else:
            console.print(f"\nERROR] No responsive IPs found. Possible issues:", style='bold red')
            console.print(f"• Your VLESS server configuration might be incorrect", style='bold yellow')
            console.print(f"• CloudFlare IPs might be blocked by your ISP", style='bold yellow')
            console.print(f"• xray-core might not be running correctly", style='bold yellow')
            console.print('Aborted.')
            exit(1)

    except KeyboardInterrupt:
        logger.exception(f'Exception raised: aborted by user.')
        console.print('\n\nAborted by user.', style='bold red')
        exit()

    except Exception as e:
        logger.exception(f'Exception raised: {e}')
        console.print(f'\n[ERROR] {e}', style='bold yellow')
        exit(1)


if __name__ == "__main__":
    main()