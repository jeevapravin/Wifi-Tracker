from flask import Flask, jsonify, request
import mysql.connector
from flask_cors import CORS
import pandas as pd
from datetime import datetime, timedelta

# Initialize the Flask application
app = Flask(__name__)
# Allow all origins, but also specify support for credentials and methods
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

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

# --- Pre-flight OPTIONS request handler for UPDATE ---
@app.route('/api/device/update/<string:device_id>', methods=['OPTIONS'])
def handle_update_options(device_id):
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    }
    return ('', 204, headers)

# --- Pre-flight OPTIONS request handler for DELETE ---
@app.route('/api/device/delete/<string:device_id>', methods=['OPTIONS'])
def handle_delete_options(device_id):
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    }
    return ('', 204, headers)


# --- DEVICE UPDATE ENDPOINT (Unchanged) ---
@app.route('/api/device/update/<string:device_id>', methods=['POST'])
def update_device(device_id):
    try:
        data = request.get_json()
        new_name = data.get('Device_Name')
        new_user_id = data.get('User_ID')

        if not new_name and not new_user_id:
            return jsonify({"error": "No data provided to update"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        query_parts = []
        values = []

        if new_name:
            query_parts.append("Device_Name = %s")
            values.append(new_name)
        if new_user_id:
            query_parts.append("User_ID = %s")
            values.append(new_user_id)

        values.append(device_id) # For the WHERE clause
        
        query = f"""
            UPDATE Device
            SET {', '.join(query_parts)}
            WHERE Device_ID = %s;
        """
        
        cursor.execute(query, tuple(values))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({"success": True, "message": f"Device {device_id} updated."})

    except Exception as e:
        print(f"Error in /api/device/update: {e}")
        return jsonify({"error": str(e)}), 500

# --- DEVICE DELETE ENDPOINT (Unchanged) ---
@app.route('/api/device/delete/<string:device_id>', methods=['DELETE'])
def delete_device(device_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "DELETE FROM Device WHERE Device_ID = %s"
        
        cursor.execute(query, (device_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({"success": True, "message": "Device deleted."})

    except Exception as e:
        print(f"Error in /api/device/delete: {e}")
        return jsonify({"error": str(e)}), 500

# --- DEVICES PAGE ENDPOINT (Unchanged) ---
@app.route('/api/devices', methods=['GET'])
def get_all_devices():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                d.Device_ID, d.Device_Name, d.Device_Type, d.MAC_Address,
                d.User_ID, 
                u.First_Name, u.Second_Name,
                COALESCE(SUM(du.Data_Downloaded + du.Data_Uploaded) / 1024, 0) as totalGB,
                MAX(cl.Timestamp) as lastSeen
            FROM Device d
            JOIN User u ON d.User_ID = u.User_ID
            LEFT JOIN Connection_Log cl ON d.Device_ID = cl.Device_ID
            LEFT JOIN Data_Usage du ON cl.Log_ID = du.Log_ID
            GROUP BY d.Device_ID, d.Device_Name, d.Device_Type, d.MAC_Address, 
                     u.First_Name, u.Second_Name, d.User_ID
            ORDER BY totalGB DESC;
        """
        cursor.execute(query)
        devices = cursor.fetchall()
        conn.close()
        
        for device in devices:
            if device['lastSeen']:
                device['lastSeen'] = device['lastSeen'].strftime('%Y-%m-%d %H:%M:%S')
            else:
                device['lastSeen'] = 'Never'
                
        return jsonify(devices)
    except Exception as e:
        print(f"Error in /api/devices: {e}")
        return jsonify({"error": str(e)}), 500

# --- *** UPDATED: USERS PAGE *** ---
@app.route('/api/users', methods=['GET'])
def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # This query now selects all columns, which will fix the "undefined" bug
    cursor.execute("SELECT * FROM User") 
    users = cursor.fetchall()
    conn.close()
    return jsonify(users)

# --- DASHBOARD STATS (Unchanged) ---
@app.route('/api/dashboard-stats', methods=['GET'])
def get_dashboard_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT SUM(Data_Downloaded + Data_Uploaded) as totalUsage FROM Data_Usage")
        total_usage_mb = (cursor.fetchone()['totalUsage'] or 0) 
        total_usage_gb = round(float(total_usage_mb) / 1024, 2) 

        cursor.execute("SELECT COUNT(DISTINCT Device_ID) as deviceCount FROM Connection_Log")
        device_count = cursor.fetchone()['deviceCount'] or 0

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
        print(f"Error in /api/dashboard-stats: {e}")
        return jsonify({"error": str(e)}), 500

# --- USAGE OVER TIME (Unchanged) ---
@app.route('/api/usage-over-time', methods=['GET'])
def get_usage_over_time():
    try:
        conn = get_db_connection()
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
            usage_by_hour = df.set_index('Timestamp').resample('H')['total_usage'].sum().cumsum() / 1024
            
            chart_data = {
                "labels": usage_by_hour.index.strftime('%H:%M').tolist(),
                "data": usage_by_hour.values.round(2).tolist()
            }
        else: 
            chart_data = {
                "labels": ['08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00'],
                "data": [0, 0, 0, 0, 0, 0, 0]
            }
            
        return jsonify(chart_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- TOP 5 DEVICES (Unchanged) ---
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

# --- NETWORK OVERVIEW (Unchanged) ---
@app.route('/api/network-overview', methods=['GET'])
def get_network_overview():
    try:
        conn = get_db_connection()
        query = """
            SELECT 
                n.SSID,
                -- Use COALESCE to ensure NULL sums become 0
                COALESCE(SUM(du.Data_Downloaded + du.Data_Uploaded) / 1024, 0) as totalGB,
                COUNT(DISTINCT cl.Device_ID) as deviceCount
            FROM Network n
            LEFT JOIN Connection_Log cl ON n.Network_ID = cl.Network_ID
            LEFT JOIN Data_Usage du ON cl.Log_ID = du.Log_ID
            GROUP BY n.Network_ID, n.SSID
            ORDER BY totalGB DESC;
        """
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        networks = cursor.fetchall()
        
        chart_data = {
            "labels": [n['SSID'] for n in networks],
            "data": [round(n['totalGB'], 2) for n in networks] # No 'or 0' needed here
        }
        
        table_data = [
            {
                "ssid": n['SSID'],
                "totalGB": round(n['totalGB'], 2), # No 'or 0' needed here
                "deviceCount": n['deviceCount']
            } for n in networks
        ]

        cursor.close()
        conn.close()
        return jsonify({"chartData": chart_data, "tableData": table_data})
    except Exception as e:
        print(f"Error in /api/network-overview: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)