import mysql.connector 
import time
import random
from datetime import datetime

# --- SAME DATABASE CONFIG AS YOUR APP.PY ---
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '1234',  # Make sure this matches your password
    'database': 'dbms_proj'
}

print("--- Router Simulator Started ---")
print("Press CTRL+C to stop.")

def get_random_device_id():
    # Fetches a random device from your Device table
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT Device_ID FROM Device")
    devices = cursor.fetchall()
    conn.close()
    if devices:
        return random.choice(devices)['Device_ID']
    return None

def get_random_network_id():
    # Fetches a random network from your Network table
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT Network_ID FROM Network")
    networks = cursor.fetchall()
    conn.close()
    if networks:
        return random.choice(networks)['Network_ID']
    return None

try:
    # --- CHANGE: We no longer need counters ---
    # log_id_counter = 100 
    # usage_id_counter = 100

    while True:
        # 1. Pick a random device and network to simulate
        device_id = get_random_device_id()
        network_id = get_random_network_id()
        
        if not device_id or not network_id:
            print("Error: No devices or networks in database. Stopping.")
            break

        # --- CHANGE: Generate UNIQUE IDs using the time ---
        # We use microseconds to make sure it's always unique
        unique_id_stamp = str(int(time.time() * 1000000))
        log_id = f'L{unique_id_stamp}'
        usage_id = f'U{unique_id_stamp}'
        # --- END CHANGE ---

        # 2. Create a new Connection_Log entry
        new_ip = f'192.168.1.{random.randint(10, 200)}'
        current_time = datetime.now()
        
        log_sql = """
            INSERT INTO Connection_Log (Log_ID, Network_ID, Device_ID, Timestamp, IP_Address)
            VALUES (%s, %s, %s, %s, %s)
        """
        log_values = (log_id, network_id, device_id, current_time, new_ip)
        
        # 3. Create a new Data_Usage entry for that connection
        data_down = round(random.uniform(5.0, 500.0), 2) # Random data (5-500 MB)
        data_up = round(random.uniform(1.0, 100.0), 2)
        
        usage_sql = """
            INSERT INTO Data_Usage (Usage_ID, Log_ID, Data_Downloaded, Data_Uploaded)
            VALUES (%s, %s, %s, %s)
        """
        usage_values = (usage_id, log_id, data_down, data_up)

        # 4. Execute the queries
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(log_sql, log_values)
        cursor.execute(usage_sql, usage_values)
        conn.commit() # Save the changes to the database
        conn.close()

        print(f"[{current_time.strftime('%H:%M:%S')}] Logged new connection: Device {device_id} used {data_down} MB")

        # --- CHANGE: Remove the old counters ---
        # log_id_counter += 1
        # usage_id_counter += 1
        
        # 5. Wait for a random time (e.g., 3-8 seconds)
        time.sleep(random.randint(3, 8))

except KeyboardInterrupt:
    print("\n--- Simulator Stopped ---")
except Exception as e:
    print(f"An error occurred: {e}")