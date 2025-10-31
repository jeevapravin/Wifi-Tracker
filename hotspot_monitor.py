#!/usr/bin/env python3
"""
Real-Time Mobile Hotspot Monitor with Scapy
Monitors devices connected to your mobile hotspot and tracks data usage.
(Version 4: Fixes rounding bug for small data packets)
"""
import mysql.connector 
import time
import threading
from datetime import datetime
from scapy.all import sniff, IP, ARP
from collections import defaultdict
import psutil
import socket

# --- CONFIGURATION: YOU MUST CHANGE THESE ---
YOUR_INTERFACE_NAME = "Wi-Fi"  # This is correct
YOUR_NETWORK_ID = "N001"       # This is fine
# --- END CONFIGURATION ---

# --- DATABASE CONFIG (same as app.py) ---
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '1234',  
    'database': 'dbms_proj'
}

# --- GLOBAL DATA STORES ---
device_data_usage = defaultdict(lambda: {"uploaded": 0, "downloaded": 0})
device_ip_map = {}
data_lock = threading.Lock()

# --- Get IP/MAC using psutil (which we know works) ---
MY_IP = None
MY_MAC = None
MY_SUBNET = None
try:
    all_addrs = psutil.net_if_addrs()
    if YOUR_INTERFACE_NAME not in all_addrs:
        raise Exception(f"Interface '{YOUR_INTERFACE_NAME}' not found by psutil. Is it connected?")
        
    for addr in all_addrs[YOUR_INTERFACE_NAME]:
        if addr.family == socket.AF_INET: # IPv4
            MY_IP = addr.address
        elif addr.family == psutil.AF_LINK: # MAC Address
            MY_MAC = addr.address.replace('-', ':').lower()

    if not MY_IP or not MY_MAC:
        raise Exception("Could not find both IP and MAC for interface.")
    
    MY_SUBNET = ".".join(MY_IP.split('.')[:3]) + "."

except Exception as e:
    print(f"Error: Could not get IP/MAC for interface '{YOUR_INTERFACE_NAME}'.")
    print(f"Error details: {e}")
    exit(1)
# --- END IP/MAC BLOCK ---


print("--- Live Hotspot Monitor Started ---")
print(f"Monitoring interface: {YOUR_INTERFACE_NAME} ({MY_IP} / {MY_MAC})")
print(f"Logging data to Network ID: {YOUR_NETWORK_ID} (Subnet: {MY_SUBNET})")
print("Press CTRL+C to stop.")

def get_db_connection():
    return mysql.connector.connect(**db_config)

def get_or_create_device(mac, ip):
    """Finds a device by MAC. If it doesn't exist, creates it."""
    
    if mac.startswith("01:00:5e") or mac == "ff:ff:ff:ff:ff:ff":
        return None 
    if ip.startswith("224.") or ip.startswith("239.") or ip == "255.255.255.255":
        return None

    conn = get_db_connection()
    # --- FIX 1: Added buffered=True ---
    cursor = conn.cursor(dictionary=True, buffered=True)
    
    cursor.execute("SELECT Device_ID FROM Device WHERE MAC_Address = %s", (mac,))
    device = cursor.fetchone()
    
    if device:
        conn.close()
        return device['Device_ID']
    
    print(f"New device detected! MAC: {mac}, IP: {ip}. Adding to database...")
    
    device_id = f'D{str(int(time.time() * 1000))[-8:]}' 
    
    cursor.execute("SELECT User_ID FROM User WHERE First_Name = 'Jeeva'") 
    default_user = cursor.fetchone()
    user_id = default_user['User_ID'] if default_user else 'U001'
    
    device_name = f"New Device ({ip})"
    device_type = "Unknown"
    
    insert_sql = """
        INSERT INTO Device (Device_ID, User_ID, MAC_Address, Device_Name, Device_Type)
        VALUES (%s, %s, %s, %s, %s)
    """
    try:
        cursor.execute(insert_sql, (device_id, user_id, mac, device_name, device_type))
        conn.commit()
        print(f"Successfully added new device: {device_id} ({mac})")
        return device_id
    except mysql.connector.Error as err:
        print(f"Error adding new device: {err}")
        conn.rollback()
        return None
    finally:
        conn.close()

def log_data_to_db():
    """
    This function runs in a separate thread, logging data to the DB
    every 30 seconds and then clearing the in-memory cache.
    """
    while True:
        time.sleep(30) 
        
        with data_lock:
            current_data_usage = dict(device_data_usage)
            device_data_usage.clear()
        
        if not current_data_usage:
            continue

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Logging data for {len(current_data_usage)} devices...")
        conn = get_db_connection()
        # --- FIX 2: Added buffered=True ---
        cursor = conn.cursor(buffered=True)
        
        for mac, usage in current_data_usage.items():
            ip = device_ip_map.get(mac, 'N/A')
            
            device_id = get_or_create_device(mac, ip)
            
            if not device_id:
                continue 
            
            # --- THIS IS THE FIX ---
            # Check raw byte count first
            raw_down = usage['downloaded']
            raw_up = usage['uploaded']
            
            # If no data at all, skip
            if raw_down == 0 and raw_up == 0:
                continue
                
            # Now convert to MB, but round to 4 decimal places
            data_down_mb = round(raw_down / (1024*1024), 4)
            data_up_mb = round(raw_up / (1024*1024), 4)

            # Secondary check: if it's still 0.0 after rounding, skip
            # This prevents logging 0.0000 MB entries
            if data_down_mb == 0 and data_up_mb == 0:
                continue
            # --- END OF FIX ---

            unique_id_stamp = str(int(time.time() * 1000000))
            log_id = f'L{unique_id_stamp[-10:]}' 
            usage_id = f'U{unique_id_stamp[-10:]}'
            current_time = datetime.now()
            
            try:
                log_sql = """
                    INSERT INTO Connection_Log (Log_ID, Network_ID, Device_ID, Timestamp, IP_Address)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(log_sql, (log_id, YOUR_NETWORK_ID, device_id, current_time, ip))
                
                usage_sql = """
                    INSERT INTO Data_Usage (Usage_ID, Log_ID, Data_Downloaded, Data_Uploaded)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(usage_sql, (usage_id, log_id, data_down_mb, data_up_mb))
                
                conn.commit()
                # --- THIS LINE SHOULD NOW PRINT ---
                print(f"  - Logged: {device_id} ({mac}) | Down: {data_down_mb} MB, Up: {data_up_mb} MB")

            except mysql.connector.Error as err:
                print(f"Error logging to DB: {err}")
                conn.rollback()
        
        conn.close()


def packet_callback(packet):
    """
    This function is called by Scapy for every packet it sniffs.
    """
    if not packet.haslayer(IP):
        return
    
    src_mac = packet.src.lower()
    dst_mac = packet.dst.lower()
    src_ip = packet[IP].src
    dst_ip = packet[IP].dst  # <-- SYNTAX ERROR FIX
    packet_size = len(packet)

    if src_mac == MY_MAC or dst_mac == MY_MAC:
        return

    # UPLOAD: Packet is from our subnet to the outside world
    if src_ip.startswith(MY_SUBNET) and not dst_ip.startswith(MY_SUBNET):
        device_mac = src_mac
        device_ip_map[device_mac] = src_ip 
        with data_lock:
            device_data_usage[device_mac]["uploaded"] += packet_size

    # DOWNLOAD: Packet is from the outside world to our subnet
    elif not src_ip.startswith(MY_SUBNET) and dst_ip.startswith(MY_SUBNET):
        device_mac = dst_mac
        device_ip_map[device_mac] = dst_ip 
        with data_lock:
            device_data_usage[device_mac]["downloaded"] += packet_size

try:
    log_thread = threading.Thread(target=log_data_to_db, daemon=True)
    log_thread.start()
    
    sniff(iface=YOUR_INTERFACE_NAME, prn=packet_callback, filter="ip", store=False)

except KeyboardInterrupt:
    print("\n--- Monitor Stopping. Waiting for final log... ---")
    time.sleep(2)
    print("--- Monitor Stopped ---")
except Exception as e:
    print(f"\nAn error occurred: {e}")