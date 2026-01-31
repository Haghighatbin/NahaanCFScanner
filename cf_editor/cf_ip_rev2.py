#!/usr/bin/env python3
"""
The following has been heavily borrowed from the code written by Farid Vahid:
https://github.com/vfarid
his efforts are much appreciated.

MODIFIED: TCP ping instead of ICMP (no root required)
ENHANCED: Support for CloudFlare IP ranges from file
"""
import os
import sys
import time
import json
import dns
import dns.resolver
from datetime import datetime
import socket
from rich.console import Console

console = Console()
# _is_streamlit = 'streamlit' in sys.modules
# console = Console(quiet=_is_streamlit)

def tcp_ping(host: str, port: int = 443, timeout: float = 1) -> float:
    """
    TCP ping that doesn't require root privileges.
    Measures time to establish TCP connection to port 443.
    
    Args:
        host: IP address to ping
        port: Port to connect to (default: 443 for CloudFlare)
        timeout: Connection timeout in seconds
    
    Returns:
        Connection time in seconds, or None if failed
    """
    try:
        start_time = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return time.time() - start_time
    except KeyboardInterrupt:
        raise
    except (socket.timeout, socket.error, OSError):
        return None

class DNSResolver():
    """The class identifies non-disrupted CloudFlare IPs"""
    def __init__(self) -> None:
        self.last_update = 0
        console.print(f'\n[Initialising the DNS resolver]'.__str__(), style='cyan')
        console.print(f'[Ctrl - C to abort]'.__str__(), style='blue')
    
    def load_cloudflare_ranges(self, ranges_file: str = './cf_editor/cloudflare_ranges.txt') -> list:
        """
        Load CloudFlare IP ranges from a text file
        
        Args:
            ranges_file: Path to file containing CloudFlare IP ranges (CIDR notation)
        
        Returns:
            List of individual IPs extracted from CIDR ranges
        """
        import ipaddress
        ips = []
        
        if not os.path.exists(ranges_file):
            console.print(f'[No CloudFlare ranges file found at {ranges_file}]'.__str__(), style='yellow')
            return ips
        
        console.print(f'[Loading CloudFlare IP ranges from file]'.__str__(), style='cyan')
        
        try:
            with open(ranges_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    try:
                        # Parse CIDR notation (e.g., 104.16.0.0/13)
                        network = ipaddress.ip_network(line, strict=False)
                        hosts = list(network.hosts())
                        
                        # Sample strategy to avoid testing too many IPs:
                        # - Small ranges (<256 IPs): Use all
                        # - Medium ranges (256-4096): Sample every 4th IP
                        # - Large ranges (>4096): Sample every 64th IP
                        if len(hosts) <= 256:
                            sampled = hosts
                        elif len(hosts) <= 4096:
                            sampled = hosts[::4]
                        else:
                            sampled = hosts[::64]
                        
                        ips.extend([str(ip) for ip in sampled])
                        console.print(f'  Range {line}: {len(sampled)} IPs sampled', style='blue')
                        
                    except Exception as e:
                        console.print(f'[Warning] Invalid range: {line} - {e}', style='yellow')
            
            console.print(f'[Loaded {len(ips)} IPs from CloudFlare ranges]'.__str__(), style='green')
            
        except Exception as e:
            console.print(f'[Warning] Failed to load ranges file: {e}', style='yellow')
        
        return ips

    def collect(self, use_cloudflare_ranges: bool = False) -> dict:
        """
        Extracts data from providers.json, list.json, and optionally CloudFlare ranges
        
        Args:
            use_cloudflare_ranges: If True, also load IPs from cloudflare_ranges.txt
        
        Returns:
            Dictionary containing collected IPs
        """
        console.print(f'[Collecting IPs from providers.json]'.__str__(), style='green')
        result = {
            "last_update": "",
            "last_timestamp": 0,
            "ipv4": [],
            "ipv6": []
        }
        
        # Load from DNS providers
        providers = json.load(open('./cf_editor/providers.json'))
        existing_ips = json.load(open('./cf_editor/list.json'))
        _resolver = dns.resolver.Resolver()

        for provider in providers:
            try:
                ipv4_result = _resolver.resolve(provider, "A")
                for ipv4 in ipv4_result:
                    ip = ipv4.to_text()
                    prev = next((el for el in existing_ips["ipv4"] if el["ip"] == ip), None)
                    created_at = prev["created_at"] if prev else int(time.time())
                    self.last_update = created_at if created_at > self.last_update else self.last_update
                    result["ipv4"].append({
                        "ip": ip,
                        "operator": providers[provider],
                        "provider": '.'.join(provider.split('.')[1:]),
                        "created_at": created_at
                    })
            except Exception as e:
                console.print(f"{repr(e):>76}{'':>4}->{'':>4}Exception ignored")
        
        # Optionally load from CloudFlare ranges file
        if use_cloudflare_ranges:
            cf_ranges_ips = self.load_cloudflare_ranges()
            current_time = int(time.time())
            
            for ip in cf_ranges_ips:
                # Check if IP already exists
                if not any(item['ip'] == ip for item in result["ipv4"]):
                    result["ipv4"].append({
                        "ip": ip,
                        "operator": "CF_RANGE",
                        "provider": "cloudflare_ranges",
                        "created_at": current_time
                    })
            
            console.print(f'[Total IPs after adding CF ranges: {len(result["ipv4"])}]', style='green')

        result["last_update"] = datetime.fromtimestamp(self.last_update).__str__()
        result["last_timestamp"] = self.last_update

        result["ipv4"].sort(key=lambda el: el["created_at"], reverse=True)
        result["ipv4"].sort(key=lambda el: el["operator"])            
        return result

    def export_handler(self, result: list) -> None:
        """Generates the list.json and list.txt files"""
        console.print(f'[Exporting the collected IPs to list.json]'.__str__(), style='green')
        try:
            with open('./results/list.json', 'w') as json_file:
                json_file.write(json.dumps(result, indent=4))

            with open('./results/list.txt', 'w') as text_file:
                text_file.write(f"Last Update: {result['last_update']}\n\nIPv4:\n")
                for el in result["ipv4"]:
                    text_file.write(f"  - {el['ip']:15s}    {el['operator']:10s}    {el['provider']}    {el['created_at']}\n")

            console.print(f'[Checking the collected IP connectivity (TCP port 443), please be patient]'.__str__(), style='blue')

        except Exception as e:
            console.print(repr(e))
    
    def ping_handler(self, collected_ips: list) -> list:
        """
        Tests IPs using TCP connection to port 443 (no root required).
        Sorts validated IPs ascendingly (fastest IP comes last).
        
        TCP ping is more reliable than ICMP for CloudFlare IPs since:
        1. Doesn't require root/sudo privileges
        2. Tests actual HTTPS port availability
        3. More representative of actual connection quality
        """
        sign = 0
        valid_ip_list, invalid_ip_list, shared_ip_list = [], [], []
        
        try:
            with console.status('[bold green] Checking collected IPV4s...') as status:
                for item in collected_ips['ipv4']:
                    if 'streamlit' in sys.modules:
                        import streamlit as st
                        if st.session_state.get('stop_requested', False):
                            console.print("\n[!] Stop requested. Aborting ping loop...", style="bold red")
                            break
                    try:
                        # Use TCP ping instead of ICMP
                        pinged_ip = tcp_ping(item['ip'], port=443, timeout=2)
                        
                        if pinged_ip is None:
                            invalid_ip_list.append((item['ip'], item['operator']))
                        else:
                            if item['ip'] in [ip[0] for ip in valid_ip_list]:
                                shared_ip_list.append((item['ip'], pinged_ip, item['operator']))
                            else:
                                valid_ip_list.append((item['ip'], pinged_ip, item['operator']))

                        sign += 1
                        time.sleep(0.2)
                    except KeyboardInterrupt:
                        console.print('Aborted by user.', style='bold red')
                        raise
                    except Exception as e:
                        print(e)

        except KeyboardInterrupt:
            console.print('aborted by user.', style='bold red')
            raise
        except Exception as e:
            console.print(e)
        
        
        sorted_list = sorted(valid_ip_list, key=lambda x: x[1], reverse=True)
        console.print(f'\nFound {len(sorted_list)} accessible IPs [Sorted by connection time]'.__str__(), style='green')
        
        with open('./results/sorted_list.txt', 'w') as output_file:
            for idx, ip in enumerate(sorted_list):
                console.print(f"[{idx+1:>3}]  IP:{ip[0]:>16}     TCP: {round(float(ip[1] * 1000),1)}ms     OPERATOR: {ip[2]}".__str__(), style='green')
                output_file.write(f"[{idx+1:>3}]  IP:{ip[0]:>16}     TCP: {round(float(ip[1] * 1000),1)}ms     OPERATOR: {ip[2]}\n")
                time.sleep(0.01)
        
        console.print(f'✓ Results saved to: ./results/sorted_list.txt', style='cyan')
        
        if invalid_ip_list:
            console.print(f'\nFound {len(invalid_ip_list)} unresponsive IPs (port 443 closed)', style='yellow')
        
        if shared_ip_list:
            console.print(f'\nFound {len(shared_ip_list)} IPs valid on multiple operators:', style='cyan')
            for ip in shared_ip_list:
                console.print(f'IP:{ip[0]:>16}     TCP: {round(float(ip[1] * 1000),1)}ms      OPERATOR: {ip[2]}'.__str__(), style='cyan')  
        
        return sorted_list