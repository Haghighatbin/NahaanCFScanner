#!/usr/bin/env python3
"""
Streamlit Helper Functions
Supporting utilities for the CloudFlare IP Scanner Streamlit interface
"""
import os
import yaml
import json
import socket
import subprocess
import pandas as pd
from typing import Dict, List, Any, Optional
import requests
from io import StringIO


def load_config_yaml(filepath: str) -> Dict[str, Any]:
    """
    Load configuration from a YAML file
    
    Args:
        filepath: Path to the config.yaml file
    
    Returns:
        Dictionary containing configuration
    """
    try:
        with open(filepath, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise Exception(f"Failed to load config: {e}")


def save_config_yaml(config: Dict[str, Any], filepath: str) -> bool:
    """
    Save configuration to a YAML file
    
    Args:
        config: Configuration dictionary
        filepath: Path to save the config.yaml file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        return True
    except Exception as e:
        print(f"Failed to save config: {e}")
        return False


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate VLESS configuration
    
    Args:
        config: Configuration dictionary
    
    Returns:
        Dictionary with 'valid' boolean and optional 'error' message
    """
    required_fields = [
        'vless_uuid',
        'vless_port',
        'server_name',
        'host_header',
        'ws_path',
        'local_socks_port'
    ]
    
    for field in required_fields:
        if field not in config or not config[field]:
            return {
                'valid': False,
                'error': f"Missing required field: {field}"
            }
    
    # Validate UUID format (basic check)
    uuid = config.get('vless_uuid', '')
    if len(uuid) < 30:
        return {
            'valid': False,
            'error': "VLESS UUID appears invalid (too short)"
        }
    
    # Validate port is numeric
    try:
        port = int(config.get('vless_port', 0))
        if port < 1 or port > 65535:
            return {
                'valid': False,
                'error': f"Invalid port number: {port}"
            }
    except ValueError:
        return {
            'valid': False,
            'error': "Port must be a number"
        }
    
    # Validate local SOCKS port
    try:
        socks_port = int(config.get('local_socks_port', 0))
        if socks_port < 1024 or socks_port > 65535:
            return {
                'valid': False,
                'error': f"Invalid SOCKS port: {socks_port} (use 1024-65535)"
            }
    except ValueError:
        return {
            'valid': False,
            'error': "SOCKS port must be a number"
        }
    
    return {'valid': True}


def check_xray_binary(binary_path: str) -> bool:
    """
    Check if xray-core binary exists and is executable
    
    Args:
        binary_path: Path to xray binary
    
    Returns:
        True if binary is available, False otherwise
    """
    if not os.path.exists(binary_path):
        return False
    
    # Try to run version check
    try:
        result = subprocess.run(
            [binary_path, '-version'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False


def check_port_availability(port: int) -> bool:
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


def test_single_ip_connection(
    ip: str,
    config: Dict[str, Any],
    timeout: int = 20
) -> Optional[Dict[str, str]]:
    """
    Test a single IP with VLESS connection
    
    Args:
        ip: IP address to test
        config: Configuration dictionary
        timeout: Connection timeout in seconds
    
    Returns:
        Dictionary with results or None if failed
    """
    try:
        from main import test_vless_connection, generate_vless_config
        
        # Generate config
        template_file = os.path.join(
            os.path.dirname(__file__),
            'config',
            'template_config_vless.json'
        )
        
        config_file = generate_vless_config(template_file, config, ip)
        
        # Test connection
        result = test_vless_connection(config_file, timeout=timeout)
        
        # Clean up
        try:
            os.unlink(config_file)
        except:
            pass
        
        return result
        
    except Exception as e:
        print(f"Error testing IP {ip}: {e}")
        return None


def run_system_diagnostics(binary_path: str, config: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Run comprehensive system diagnostics
    
    Args:
        binary_path: Path to xray binary
        config: Configuration dictionary
    
    Returns:
        List of diagnostic check results
    """
    diagnostics = []
    
    # Check 1: xray-core binary
    if check_xray_binary(binary_path):
        try:
            result = subprocess.run(
                [binary_path, '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            version = result.stdout.split('\n')[0] if result.stdout else "Unknown"
            diagnostics.append({
                'name': 'xray-core Binary',
                'status': 'pass',
                'message': f'Found: {version}'
            })
        except:
            diagnostics.append({
                'name': 'xray-core Binary',
                'status': 'pass',
                'message': 'Binary exists but version check failed'
            })
    else:
        diagnostics.append({
            'name': 'xray-core Binary',
            'status': 'fail',
            'message': f'Not found at {binary_path}'
        })
    
    # Check 2: Port availability
    port = int(config.get('local_socks_port', 1080))
    if check_port_availability(port):
        diagnostics.append({
            'name': f'Port {port} Availability',
            'status': 'pass',
            'message': 'Port is available'
        })
    else:
        diagnostics.append({
            'name': f'Port {port} Availability',
            'status': 'warning',
            'message': 'Port is in use (will attempt to free during scan)'
        })
    
    # Check 3: Config validation
    validation = validate_config(config)
    if validation['valid']:
        diagnostics.append({
            'name': 'Configuration',
            'status': 'pass',
            'message': 'All required fields present'
        })
    else:
        diagnostics.append({
            'name': 'Configuration',
            'status': 'fail',
            'message': validation['error']
        })
    
    # Check 4: Internet connectivity
    try:
        response = requests.get('http://www.gstatic.com/generate_204', timeout=5)
        if response.status_code == 204:
            diagnostics.append({
                'name': 'Internet Connectivity',
                'status': 'pass',
                'message': 'Direct internet connection works'
            })
        else:
            diagnostics.append({
                'name': 'Internet Connectivity',
                'status': 'warning',
                'message': f'Unexpected response: {response.status_code}'
            })
    except:
        diagnostics.append({
            'name': 'Internet Connectivity',
            'status': 'fail',
            'message': 'Cannot reach test server'
        })
    
    # Check 5: DNS resolution
    try:
        import dns.resolver
        resolver = dns.resolver.Resolver()
        server_name = config.get('server_name', '')
        if server_name:
            answers = resolver.resolve(server_name, 'A')
            diagnostics.append({
                'name': 'DNS Resolution',
                'status': 'pass',
                'message': f'Server name resolves: {server_name}'
            })
        else:
            diagnostics.append({
                'name': 'DNS Resolution',
                'status': 'warning',
                'message': 'No server name configured'
            })
    except Exception as e:
        diagnostics.append({
            'name': 'DNS Resolution',
            'status': 'fail',
            'message': f'Failed to resolve server name: {str(e)[:50]}'
        })
    
    # Check 6: Template config file
    template_path = os.path.join(
        os.path.dirname(__file__),
        'config',
        'template_config_vless.json'
    )
    if os.path.exists(template_path):
        try:
            with open(template_path, 'r') as f:
                json.load(f)
            diagnostics.append({
                'name': 'Template Config',
                'status': 'pass',
                'message': 'Template file valid'
            })
        except:
            diagnostics.append({
                'name': 'Template Config',
                'status': 'fail',
                'message': 'Template file corrupted'
            })
    else:
        diagnostics.append({
            'name': 'Template Config',
            'status': 'fail',
            'message': 'Template file not found'
        })
    
    # Check 7: Results directory
    results_dir = os.path.join(os.path.dirname(__file__), 'results')
    if os.path.exists(results_dir) and os.path.isdir(results_dir):
        diagnostics.append({
            'name': 'Results Directory',
            'status': 'pass',
            'message': 'Directory exists and writable'
        })
    else:
        try:
            os.makedirs(results_dir, exist_ok=True)
            diagnostics.append({
                'name': 'Results Directory',
                'status': 'pass',
                'message': 'Created successfully'
            })
        except:
            diagnostics.append({
                'name': 'Results Directory',
                'status': 'fail',
                'message': 'Cannot create results directory'
            })
    
    return diagnostics


def format_speed(speed_str: str) -> float:
    """
    Convert speed string to numeric value
    
    Args:
        speed_str: Speed string like "5.2 MB/s"
    
    Returns:
        Numeric speed value
    """
    try:
        return float(speed_str.replace(' MB/s', '').replace('MB/s', ''))
    except:
        return 0.0


def format_latency(latency_str: str) -> float:
    """
    Convert latency string to numeric value
    
    Args:
        latency_str: Latency string like "45 ms"
    
    Returns:
        Numeric latency value
    """
    try:
        return float(latency_str.replace(' ms', '').replace('ms', ''))
    except:
        return 999999.0


def export_results_csv(results: List[Dict[str, Any]]) -> str:
    """
    Export results to CSV format
    
    Args:
        results: List of result dictionaries
    
    Returns:
        CSV string
    """
    try:
        df = pd.DataFrame([{
            'Rank': idx + 1,
            'IP Address': r['address_str'],
            'Download Speed': r['download_rate'],
            'Latency': r['latency_rate'],
            'Operator': r.get('operator', 'Unknown'),
            'Port': r.get('port_str', '443'),
            'UUID': r.get('uuid_str', '')[:8] + '...'
        } for idx, r in enumerate(results)])
        
        return df.to_csv(index=False)
    except Exception as e:
        return f"Error exporting CSV: {e}"


def export_results_json(results: List[Dict[str, Any]]) -> str:
    """
    Export results to JSON format
    
    Args:
        results: List of result dictionaries
    
    Returns:
        JSON string
    """
    try:
        return json.dumps(results, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e)})


def generate_vless_link(ip: str, config: Dict[str, Any]) -> str:
    """
    Generate a VLESS connection link
    
    Args:
        ip: IP address
        config: Configuration dictionary
    
    Returns:
        VLESS link string
    """
    uuid = config.get('vless_uuid', '')
    port = config.get('vless_port', '443')
    server_name = config.get('server_name', '')
    host_header = config.get('host_header', '')
    ws_path = config.get('ws_path', '/')
    
    # Basic VLESS link format
    link = f"vless://{uuid}@{ip}:{port}"
    params = []
    
    if server_name:
        params.append(f"sni={server_name}")
    if host_header:
        params.append(f"host={host_header}")
    if ws_path != '/':
        params.append(f"path={ws_path}")
    
    params.append("type=ws")
    params.append("security=tls")
    
    if params:
        link += "?" + "&".join(params)
    
    link += f"#{ip}"
    
    return link


def calculate_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate statistics from scan results
    
    Args:
        results: List of result dictionaries
    
    Returns:
        Dictionary containing statistics
    """
    if not results:
        return {
            'total': 0,
            'avg_speed': 0,
            'max_speed': 0,
            'min_speed': 0,
            'avg_latency': 0,
            'max_latency': 0,
            'min_latency': 0
        }
    
    speeds = [r.get('download_numeric', 0) for r in results]
    latencies = [r.get('latency_numeric', 0) for r in results]
    
    return {
        'total': len(results),
        'avg_speed': sum(speeds) / len(speeds),
        'max_speed': max(speeds),
        'min_speed': min(speeds),
        'avg_latency': sum(latencies) / len(latencies),
        'max_latency': max(latencies),
        'min_latency': min(latencies)
    }


def get_operator_statistics(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """
    Calculate per-operator statistics
    
    Args:
        results: List of result dictionaries
    
    Returns:
        Dictionary mapping operators to their statistics
    """
    operator_stats = {}
    
    for result in results:
        operator = result.get('operator', 'Unknown')
        
        if operator not in operator_stats:
            operator_stats[operator] = {
                'count': 0,
                'total_speed': 0,
                'total_latency': 0,
                'speeds': [],
                'latencies': []
            }
        
        operator_stats[operator]['count'] += 1
        operator_stats[operator]['total_speed'] += result.get('download_numeric', 0)
        operator_stats[operator]['total_latency'] += result.get('latency_numeric', 0)
        operator_stats[operator]['speeds'].append(result.get('download_numeric', 0))
        operator_stats[operator]['latencies'].append(result.get('latency_numeric', 0))
    
    # Calculate averages
    for operator in operator_stats:
        count = operator_stats[operator]['count']
        if count > 0:
            operator_stats[operator]['avg_speed'] = operator_stats[operator]['total_speed'] / count
            operator_stats[operator]['avg_latency'] = operator_stats[operator]['total_latency'] / count
    
    return operator_stats
