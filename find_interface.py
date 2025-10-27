#!/usr/bin/env python3
"""
Find your network interface name (Version 2).
This version is more robust for Windows systems that report
interfaces using GUIDs.
"""
import psutil
import socket
import platform

try:
    from scapy.all import conf, get_working_ifaces
except ImportError:
    print("Scapy not found. Please ensure it is installed: pip install scapy")
    exit()

print("=" * 60)
print("DETECTED NETWORK INTERFACES (v2)")
print("=" * 60)
print("The previous script failed because your system uses complex GUIDs.")
print("This new script tries a more robust method.\n")

print("--- Method 1: Using 'psutil' (Recommended) ---")
print("This method lists human-readable names.\n")
try:
    # Get stats first (to check 'isup')
    stats = psutil.net_if_stats()
    # Get addresses
    addrs = psutil.net_if_addrs()

    # Iterate over the human-readable names from psutil
    for iface_name in addrs:
        ip_addr = "N/A"
        mac_addr = "N/A"
        is_up = "DOWN"
        
        # Check status
        if iface_name in stats:
            is_up = "UP" if stats[iface_name].isup else "DOWN"

        # Find IP and MAC
        for addr in addrs[iface_name]:
            if addr.family == socket.AF_INET: # IPv4
                ip_addr = addr.address
            elif addr.family == psutil.AF_LINK: # MAC Address
                mac_addr = addr.address
        
        print(f"Interface: {iface_name}")
        print(f"  Status:    {is_up}")
        print(f"  IP Address: {ip_addr}")
        print(f"  MAC Address: {mac_addr}")
        print("-" * 20)

except Exception as e:
    print(f"Error with psutil method: {e}\n")


print("\n--- Method 2: Using 'Scapy' (Backup) ---")
print("This list shows all interfaces Scapy can *directly* use.\n")
try:
    # Get a list of *working* interfaces from Scapy
    working_ifaces = get_working_ifaces()
    
    if not working_ifaces:
        print("Scapy could not find any working interfaces.")
    
    for iface in working_ifaces:
        # 'iface' object has 'name', 'ip', 'mac'
        print(f"Interface: {iface.name}")
        print(f"  IP Address: {iface.ip}")
        print(f"  MAC Address: {iface.mac}")
        print("-" * 20)

except Exception as e:
    print(f"Error with Scapy method: {e}")


print("\n" + "=" * 60)
print("HOW TO CHOOSE:")
print("1. Make sure you are connected to your mobile hotspot.")
print("2. Look at the 'psutil' list (Method 1) first.")
print("3. Find the interface that is 'UP' and has an IP address")
print("   from your hotspot (e.g., 192.168.43.x or similar).")
print("4. This is your interface name (e.g., 'Wi-Fi', 'Ethernet 2').")
print("5. Use this exact name in 'hotspot_monitor.py'.")
print("=" * 60)


'''
Interface: Wi-Fi
  Status:    UP
  IP Address: 172.20.10.7
  MAC Address: 14-D4-24-62-6F-75
  
  '''
  