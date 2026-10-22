def lan_inventory_script() -> str:
    """Return a ready‑to‑run Python script that scans the local subnet for IP/MAC pairs using Scapy.
    The returned script is a full, self‑contained file that can be saved and executed.
    """
    script = '''#!/usr/bin/env python3
"""
LAN Inventory Scanner
=====================

This script discovers all hosts on a local subnet and prints their IP and MAC addresses.
It works on Linux, Windows and macOS.

Usage:
  python3 lan_inventory.py [--iface IFACE] [--subnet SUBNET]

Options:
  --iface IFACE   Specify the network interface to use (default: detected default interface).
  --subnet SUBNET Specify the subnet to scan in CIDR notation (default: detected subnet).

Dependencies:
  - scapy
  - netifaces

If dependencies are missing, install them with:
  pip install scapy netifaces
"""

import argparse
import sys
import os

try:
    from scapy.all import ARP, Ether, srp, conf
except Exception as e:
    print("Error importing scapy: {}. Install with 'pip install scapy'".format(e))
    sys.exit(1)

try:
    import netifaces
except Exception as e:
    print("Error importing netifaces: {}. Install with 'pip install netifaces'".format(e))
    sys.exit(1)


def get_default_interface():
    """Return the system's default network interface."""
    gateways = netifaces.gateways()
    default = gateways.get('default')
    if not default:
        return None
    return default.get(netifaces.AF_INET)[0]


def get_interface_info(iface):
    """Return (ip, netmask) for the given interface."""
    addrs = netifaces.ifaddresses(iface)
    inet = addrs.get(netifaces.AF_INET)
    if not inet:
        return None, None
    return inet[0]['addr'], inet[0]['netmask']


def cidr_from_ip_mask(ip, mask):
    """Convert IP and netmask to CIDR notation."""
    import ipaddress
    net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
    return str(net)


def scan_network(cidr):
    """Perform an ARP ping sweep on the given CIDR and return a list of (ip, mac)."""
    conf.verb = 0
    ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=cidr), timeout=2, retry=1)
    return [(r.psrc, r.hwsrc) for s, r in ans]


def main():
    parser = argparse.ArgumentParser(description="Scan local subnet for IP/MAC pairs.")
    parser.add_argument("--iface", help="Network interface to use.")
    parser.add_argument("--subnet", help="Subnet to scan in CIDR notation.")
    args = parser.parse_args()

    iface = args.iface or get_default_interface()
    if not iface:
        print("Could not determine default interface. Use --iface to specify one.")
        sys.exit(1)

    ip, mask = get_interface_info(iface)
    if not ip or not mask:
        print(f"Could not get IP/netmask for interface {iface}.")
        sys.exit(1)

    subnet = args.subnet or cidr_from_ip_mask(ip, mask)
    print(f"Scanning subnet {subnet} on interface {iface}...")

    hosts = scan_network(subnet)
    if not hosts:
        print("No hosts found. Try increasing timeout or checking firewall settings.")
        sys.exit(0)

    print("IP Address\tMAC Address")
    for ip_addr, mac in hosts:
        print(f"{ip_addr}\t{mac}")

if __name__ == "__main__":
    main()
'''
    return script

# Test code
if __name__ == "__main__":
    print(lan_inventory_script()[:200])
