from flask import Flask, jsonify
import mysql.connector
from flask_cors import CORS
import pandas as pd
from datetime import datetime, timedelta

# Initialize the Flask application
app = Flask(__name__)
CORS(app) 

# --- DATABASE CONFIGURATION ---
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '1234', 
    'database': 'dbms_proj'
}

def get_db_connection():
    """Function to create and return a database connection."""
    return mysql.connector.connect(**db_config)

# --- NEW: API ENDPOINT FOR DASHBOARD STATS ---
# (IN app.py)
# REPLACE your entire 'get_dashboard_stats' function with this:

@app.route('/api/dashboard-stats', methods=['GET'])
def get_dashboard_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Query for Total Usage (in MB)
        cursor.execute("SELECT SUM(Data_Downloaded + Data_Uploaded) as totalUsage FROM Data_Usage")
        total_usage_mb = (cursor.fetchone()['totalUsage'] or 0) # This line is safer
        total_usage_gb = round(float(total_usage_mb) / 1024, 2) # Use float() to be extra safe

        # Query for Connected Devices Count
        cursor.execute("SELECT COUNT(DISTINCT Device_ID) as deviceCount FROM Connection_Log")
        device_count = cursor.fetchone()['deviceCount'] or 0

        # Query for Top Device by Usage
        top_device_query = """
            SELECT d.Device_Name, SUM(du.Data_Downloaded + du.Data_Uploaded) as totalData
            FROM Data_Usage du
            JOIN Connection_Log cl ON du.Log_ID = cl.Log_ID
            JOIN Device d ON cl.Device_ID = d.Device_ID
            GROUP BY d.Device_Name
            ORDER BY totalData DESC
            LIMIT 1;
        """
        cursor.execute(top_device_query)
        top_device = cursor.fetchone() or {"Device_Name": "N/A", "totalData": 0}
        
        # This is the safest way to get the data, handling None
        top_device_name = top_device.get('Device_Name', 'N/A')
        top_device_data = top_device.get('totalData') or 0
        top_device_gb = round(float(top_device_data) / 1024, 2)
        
        stats = {
            "connectedDevices": device_count,
            "totalUsageGB": total_usage_gb,
            "topDevice": {
                "name": top_device_name,
                "usageGB": top_device_gb
            }
        }
        
        cursor.close()
        conn.close()
        return jsonify(stats)
    except Exception as e:
        print(f"Error in /api/dashboard-stats: {e}") # Add a print statement
        return jsonify({"error": str(e)}), 500

# --- NEW: API ENDPOINT FOR USAGE OVER TIME (for line chart) ---
@app.route('/api/usage-over-time', methods=['GET'])
def get_usage_over_time():
    try:
        conn = get_db_connection()
        # Fetch raw data
        query = """
            SELECT cl.Timestamp, (du.Data_Downloaded + du.Data_Uploaded) as total_usage
            FROM Data_Usage du
            JOIN Connection_Log cl ON du.Log_ID = cl.Log_ID
            ORDER BY cl.Timestamp;
        """
        df = pd.read_sql(query, conn)
        conn.close()

        if not df.empty:
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            # Resample data by hour and sum up the usage
            usage_by_hour = df.set_index('Timestamp').resample('H')['total_usage'].sum().cumsum() / 1024 # Cumulative GB
            
            chart_data = {
                "labels": usage_by_hour.index.strftime('%H:%M').tolist(),
                "data": usage_by_hour.values.round(2).tolist()
            }
        else: # Provide dummy data if database is empty
            chart_data = {
                "labels": ['08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00'],
                "data": [0, 2, 3.5, 4, 6, 8.1, 9]
            }
            
        return jsonify(chart_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- NEW: API ENDPOINT FOR TOP 5 DEVICES (for bar chart) ---
@app.route('/api/top-devices-today', methods=['GET'])
def get_top_devices_today():
    try:
        conn = get_db_connection()
        query = """
            SELECT d.Device_Name, SUM(du.Data_Downloaded + du.Data_Uploaded) / 1024 as totalGB
            FROM Data_Usage du
            JOIN Connection_Log cl ON du.Log_ID = cl.Log_ID
            JOIN Device d ON cl.Device_ID = d.Device_ID
            GROUP BY d.Device_Name
            ORDER BY totalGB DESC
            LIMIT 5;
        """
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        devices = cursor.fetchall()
        
        chart_data = {
            "labels": [device['Device_Name'] for device in devices],
            "data": [round(device['totalGB'], 2) for device in devices]
        }

        cursor.close()
        conn.close()
        return jsonify(chart_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- EXISTING ENDPOINTS (can be used for 'Users' and 'Devices' pages) ---
@app.route('/api/users', methods=['GET'])
def get_all_users():
    # ... (code is unchanged, but can be used for a dedicated 'Users' view)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM User")
    users = cursor.fetchall()
    conn.close()
    return jsonify(users)

@app.route('/api/devices', methods=['GET'])
def get_all_devices():
    # ... (code is unchanged, but can be used for a dedicated 'Devices' view)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Device")
    devices = cursor.fetchall()
    conn.close()
    return jsonify(devices)

if __name__ == '__main__':
    app.run(debug=True)

