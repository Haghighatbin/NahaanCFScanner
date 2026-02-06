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
import statistics
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console

console = Console()
# _is_streamlit = 'streamlit' in sys.modules
# console = Console(quiet=_is_streamlit)

def tcp_ping(host: str, port: int = 443, timeout: float = 2) -> float:
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

        # Experiment: Avoid TIME_WAIT accumulation
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, 
                       bytes([0, 0, 0, 0, 0, 0, 0, 0]))  # Immediate close
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        sock.settimeout(timeout)
        sock.connect((host, port))
        # sock.close()
        return time.time() - start_time
    
    except KeyboardInterrupt:
        raise
    except (socket.timeout, socket.error, OSError, ConnectionRefusedError):
        return None
    finally:
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except:
                pass
            sock.close()
            del sock  # Force garbage collection

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

    def ping_handler(self,
                    collected_ips: list,
                    batch_size: int = 500,
                    max_workers: int = 30,
                    tcp_timeout: float = 2.0, 
                    ping_attempts: int = 3
                    ) -> list:
        """
        Tests IPs using multiple TCP pings with batching and concurrency.
        Prevents socket exhaustion when testing 50,000+ IPs.
        
        Args:
            collected_ips: List of IPs to test
            batch_size: Process IPs in batches (default 500)
            max_workers: Concurrent connections per batch (default 30)
            tcp_timeout: Timeout per ping attempt
            ping_attempts: Number of pings per IP (default 3 for reliability)
        """        
        valid_ip_list, invalid_ip_list, shared_ip_list = [], [], []
        total_ips = len(collected_ips['ipv4'])
        
        console.print(f'\n[Testing {total_ips} IPs in batches of {batch_size} with {max_workers} concurrent threads]', 
                    style='cyan')
        console.print(f'[{ping_attempts} ping attempts per IP for stability measurement]', style='blue')
        
        def test_ip_stability(item):
            """Test a single IP with multiple ping attempts"""
            try:
                ping_results = []
                
                for attempt in range(ping_attempts):
                    result = tcp_ping(item['ip'], port=443, timeout=tcp_timeout)
                    if result is not None:
                        ping_results.append(result)
                    time.sleep(0.05)  # Small delay between attempts
                
                # Require at least 50% success rate
                min_required = max(1, ping_attempts // 2)
                
                if len(ping_results) >= min_required:
                    median_latency = statistics.median(ping_results)
                    jitter = statistics.stdev(ping_results) if len(ping_results) > 1 else 0.0
                    
                    return {
                        'ip': item['ip'],
                        'operator': item['operator'],
                        'median_latency': median_latency,
                        'jitter': jitter,
                        'success_count': len(ping_results),
                        'status': 'valid'
                    }
                else:
                    return {
                        'ip': item['ip'],
                        'operator': item['operator'],
                        'status': 'invalid'
                    }
                    
            except KeyboardInterrupt:
                raise
            except Exception as e:
                return {
                    'ip': item['ip'],
                    'operator': item['operator'],
                    'status': 'error',
                    'error': str(e)
                }

        live_results_path = './results/results_live.txt'
        
        # Initialise live file with header
        with open(live_results_path, 'w', encoding='utf-8') as live_file:
            live_file.write(f"CloudFlare IP Scanner - Live Results\n")
            live_file.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            live_file.write(f"Total IPs to test: {total_ips}\n")
            live_file.write(f"Batch size: {batch_size} | Workers: {max_workers} | Ping attempts: {ping_attempts}\n")
            live_file.write("="*100 + "\n\n")

        try:
            with console.status('[bold green] Checking collected IPV4s with stability test...') as status:
                # Process in batches to avoid socket exhaustion
                for batch_num, batch_start in enumerate(range(0, total_ips, batch_size), 1):
                    batch_end = min(batch_start + batch_size, total_ips)
                    batch = collected_ips['ipv4'][batch_start:batch_end]
                    
                    console.print(f'\n[Batch {batch_num}: Testing IPs {batch_start+1}-{batch_end}]', 
                                style='blue')
                    
                    batch_valid_results = []

                    # Use ThreadPoolExecutor for concurrent testing within batch
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        future_to_item = {
                            executor.submit(test_ip_stability, item): item 
                            for item in batch
                        }
                        
                        completed = 0
                        for future in as_completed(future_to_item):
                            completed += 1
                            result = future.result()
                            
                            if result['status'] == 'valid':
                                # Check for duplicate IPs
                                if result['ip'] in [ip[0] for ip in valid_ip_list]:
                                    shared_ip_list.append((
                                        result['ip'],
                                        result['median_latency'],
                                        result['operator'],
                                        result['jitter'],
                                        result['success_count']
                                    ))
                                else:
                                    valid_ip_list.append((
                                        result['ip'],
                                        result['median_latency'],
                                        result['operator'],
                                        result['jitter'],
                                        result['success_count']
                                    ))
                                    batch_valid_results.append((result['ip'], result['median_latency'], 
                                        result['operator'], result['jitter'], 
                                        result['success_count']))
                                    
                                # Log unstable connections
                                if result['jitter'] > 0.1:
                                    console.print(
                                        f"  ⚠️ {result['ip']} - Unstable ({int(result['jitter']*1000)}ms jitter)",
                                        style='yellow'
                                    )
                            
                            elif result['status'] == 'invalid':
                                invalid_ip_list.append((result['ip'], result['operator']))
                            
                            # Progress indicator within batch
                            if completed % 50 == 0:
                                console.print(f"  [{completed}/{len(batch)} in batch]", style='dim')
                    
                    # Progress update after batch
                    progress_pct = int((batch_end / total_ips) * 100)
                    console.print(
                        f'[Progress: {progress_pct}% | Valid: {len(valid_ip_list)} | '
                        f'Invalid: {len(invalid_ip_list)} | Shared: {len(shared_ip_list)}]',
                        style='green'
                    )
                    # Write THIS batch's results to live file immediately
                    with open(live_results_path, 'a', encoding='utf-8') as live_file:
                        live_file.write(f"\n--- Batch {batch_num} (IPs {batch_start+1}-{batch_end}) ---\n")
                        live_file.write(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}\n")
                        live_file.write(f"Found {len(batch_valid_results)} valid IPs in this batch\n\n")
                        
                        for ip_data in batch_valid_results:
                            latency_ms = round(float(ip_data[1] * 1000), 1)
                            jitter_ms = round(float(ip_data[3] * 1000), 1)
                            success_rate = f"{ip_data[4]}/{ping_attempts}"
                            
                            # Use ASCII for file compatibility
                            if ip_data[3] < 0.05:
                                stability = "[OK]"
                            elif ip_data[3] < 0.15:
                                stability = "[!!]"
                            else:
                                stability = "[XX]"
                            
                            line = (f"  IP: {ip_data[0]:>16}  Latency: {latency_ms:>6}ms  "
                                f"Jitter: ±{jitter_ms:>5}ms  {stability}  Success: {success_rate}  OP: {ip_data[2]}\n")
                            live_file.write(line)
                        
                        live_file.flush()  # Force write to disk immediately
                    
                    # Critical: Pause between batches to let TIME_WAIT sockets clear
                    if batch_end < total_ips:
                        console.print('[Pausing 3s between batches to free socket resources...]', 
                                    style='dim')
                        time.sleep(3)
        
        except KeyboardInterrupt:
            # Write interruption notice to live file
            with open(live_results_path, 'a', encoding='utf-8') as live_file:
                live_file.write(f"\n\n!!! SCAN INTERRUPTED BY USER at {datetime.now().strftime('%H:%M:%S')} !!!\n")
                live_file.write(f"Processed {batch_num} batches before interruption\n")
                live_file.flush()

            console.print('\n[Aborted by user]', style='bold red')
            raise

        # Write final summary to live file
        with open(live_results_path, 'a', encoding='utf-8') as live_file:
            live_file.write(f"\n{'='*100}\n")
            live_file.write(f"SCAN COMPLETE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            live_file.write(f"Total Valid: {len(valid_ip_list)} | Invalid: {len(invalid_ip_list)} | Shared: {len(shared_ip_list)}\n")
            live_file.write(f"\nSee sorted_list.txt for final sorted results\n")
            # Sort by median latency (lower is better)

        console.print(f'\n✓ Live results saved to: ./results/results_live.txt', style='cyan')

        sorted_list = sorted(valid_ip_list, key=lambda x: x[1], reverse=True)
        
        console.print(f'\nFound {len(sorted_list)} accessible IPs [Sorted by median latency + stability]', 
                    style='green')
        
        with open('./results/sorted_list.txt', 'w', encoding='utf-8') as output_file:
            output_file.write(f"Total Tested: {total_ips} | Valid: {len(sorted_list)} | "
                            f"Invalid: {len(invalid_ip_list)} | Shared: {len(shared_ip_list)}\n")
            output_file.write("="*100 + "\n\n")
            
            for idx, ip in enumerate(sorted_list):
                latency_ms = round(float(ip[1] * 1000), 1)
                jitter_ms = round(float(ip[3] * 1000), 1)
                success_rate = f"{ip[4]}/{ping_attempts}"
                
                # Stability indicator
                if ip[3] < 0.05:  # <50ms jitter
                    stability = "[OK]"
                elif ip[3] < 0.15:  # <150ms jitter
                    stability = "[!!]"
                else:
                    stability = "[XX]"
                
                output = (f"[{idx+1:>3}]  IP:{ip[0]:>16}  Latency:{latency_ms:>6}ms  "
                        f"Jitter:±{jitter_ms:>5}ms  {stability}  Success:{success_rate}  OP:{ip[2]}")
                console.print(output, style='green')
                output_file.write(output + '\n')
                time.sleep(0.01)
        
        console.print(f'\n✓ Results saved with stability metrics to ./results/sorted_list.txt', 
                    style='cyan')
        
        if invalid_ip_list:
            console.print(f'\n{len(invalid_ip_list)} IPs failed reliability test', style='yellow')
        
        if shared_ip_list:
            console.print(f'{len(shared_ip_list)} IPs valid on multiple operators', style='cyan')
        
        return sorted_list

