from flask import Flask, jsonify, request, make_response, redirect, url_for, flash, render_template_string
import mysql.connector
from flask_cors import CORS
import pandas as pd
from datetime import datetime, timedelta
import uuid
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

db_config = {'host': 'localhost', 'user': 'root', 'password': '1234', 'database': 'dbms_proj'}

def get_db_connection():
    return mysql.connector.connect(**db_config)

class User(UserMixin):
    def __init__(self, id, email, first_name):
        self.id = id
        self.email = email
        self.first_name = first_name

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT User_ID, Email_ID, First_Name FROM User WHERE User_ID = %s", (user_id,))
    db_user = cursor.fetchone()
    cursor.close()
    conn.close()
    if db_user:
        return User(id=db_user['User_ID'], email=db_user['Email_ID'], first_name=db_user['First_Name'])
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT User_ID, Email_ID, First_Name, Password_Hash FROM User WHERE Email_ID = %s", (email,))
        db_user = cursor.fetchone()
        cursor.close()
        conn.close()

        if db_user and check_password_hash(db_user['Password_Hash'], password):
            user_obj = User(id=db_user['User_ID'], email=db_user['Email_ID'], first_name=db_user['First_Name'])
            login_user(user_obj)
            return redirect('/')
        else:
            flash('Invalid email or password', 'error')

    login_html = """
    <!DOCTYPE html><html><head><title>Login</title><style>body{font-family:sans-serif;background:#1a1c23;color:white;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;} form{background:#252831;padding:40px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.2);} h1{text-align:center;margin-bottom:20px;} div{margin-bottom:15px;} label{display:block;margin-bottom:5px;} input{width:100%;padding:10px;background:#1a1c23;border:1px solid #3b3e47;color:white;border-radius:4px;box-sizing:border-box;} button{width:100%;padding:10px;background:#3b82f6;border:none;color:white;border-radius:4px;cursor:pointer;margin-top:10px;} button:hover{background:#2563eb;} .flash{color:#ef4444;text-align:center;margin-bottom:15px;}</style></head><body>
    <form method="post"><h1>LinkSphere Login</h1>{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="flash">{{ message }}</div>{% endfor %}{% endif %}{% endwith %}<div><label for="email">Email:</label><input type="email" id="email" name="email" required></div><div><label for="password">Password:</label><input type="password" id="password" name="password" required></div><button type="submit">Login</button></form></body></html>
    """
    return render_template_string(login_html)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            content = f.read()
        return render_template_string(content)
    except FileNotFoundError:
        return "Error: index.html not found.", 404

@app.route('/api/device/<string:device_id>', methods=['GET'])
@login_required
def get_device_details(device_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        details_query = "SELECT d.Device_Name, d.Device_Type, d.MAC_Address, u.First_Name, u.Second_Name FROM Device d JOIN User u ON d.User_ID = u.User_ID WHERE d.Device_ID = %s"
        cursor.execute(details_query, (device_id,))
        device_details = cursor.fetchone()
        if not device_details:
            return jsonify({"error": "Device not found"}), 404
        
        usage_query = "SELECT cl.Timestamp, (du.Data_Downloaded + du.Data_Uploaded) as total_usage FROM Data_Usage du JOIN Connection_Log cl ON du.Log_ID = cl.Log_ID WHERE cl.Device_ID = %s ORDER BY cl.Timestamp;"
        df = pd.read_sql(usage_query, conn, params=(device_id,))
        usage_graph_data = {"labels": [], "data": []}
        if not df.empty:
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            usage_resampled = df.set_index('Timestamp').resample('5min')['total_usage'].sum().cumsum() / 1024
            usage_graph_data = {"labels": usage_resampled.index.strftime('%H:%M').tolist(), "data": usage_resampled.values.round(2).tolist()}
        
        log_query = "SELECT cl.Timestamp, cl.IP_Address, n.SSID, du.Data_Downloaded, du.Data_Uploaded FROM Connection_Log cl JOIN Network n ON cl.Network_ID = n.Network_ID JOIN Data_Usage du ON cl.Log_ID = du.Log_ID WHERE cl.Device_ID = %s ORDER BY cl.Timestamp DESC LIMIT 20;"
        cursor.execute(log_query, (device_id,))
        connection_logs = cursor.fetchall()
        formatted_logs = [{'Timestamp': log['Timestamp'].strftime('%Y-%m-%d %H:%M:%S'), 'IP_Address': log['IP_Address'], 'Network_SSID': log['SSID'], 'Data_Downloaded_MB': round(log['Data_Downloaded'], 2), 'Data_Uploaded_MB': round(log['Data_Uploaded'], 2)} for log in connection_logs]
        cursor.close()
        conn.close()
        response_data = {"details": device_details, "usage_graph": usage_graph_data, "logs": formatted_logs}
        return jsonify(response_data)
    except Exception as e:
        print(f"Error in /api/device/<device_id>: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/devices/export', methods=['GET'])
@login_required
def export_devices():
    try:
        conn = get_db_connection()
        query = """SELECT d.Device_ID, d.Device_Name, d.Device_Type, d.MAC_Address, CONCAT(u.First_Name, ' ', u.Second_Name) as Owner, COALESCE(SUM(du.Data_Downloaded + du.Data_Uploaded) / 1024, 0) as totalGB, MAX(cl.Timestamp) as lastSeen FROM Device d JOIN User u ON d.User_ID = u.User_ID LEFT JOIN Connection_Log cl ON d.Device_ID = cl.Device_ID LEFT JOIN Data_Usage du ON cl.Log_ID = du.Log_ID GROUP BY d.Device_ID, d.Device_Name, d.Device_Type, d.MAC_Address, Owner ORDER BY totalGB DESC;"""
        df = pd.read_sql(query, conn)
        conn.close()
        csv_data = df.to_csv(index=False, encoding='utf-8')
        response = make_response(csv_data)
        response.headers["Content-Disposition"] = "attachment; filename=devices_export.csv"
        response.headers["Content-Type"] = "text/csv"
        return response
    except Exception as e:
        print(f"Error in /api/devices/export: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/export', methods=['GET'])
@login_required
def export_users():
    try:
        conn = get_db_connection()
        query = "SELECT User_ID, First_Name, Second_Name, Email_ID, Phone_No FROM User"
        df = pd.read_sql(query, conn)
        conn.close()
        csv_data = df.to_csv(index=False, encoding='utf-8')
        response = make_response(csv_data)
        response.headers["Content-Disposition"] = "attachment; filename=users_export.csv"
        response.headers["Content-Type"] = "text/csv"
        return response
    except Exception as e:
        print(f"Error in /api/users/export: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/device/update/<string:device_id>', methods=['POST'])
@login_required
def update_device(device_id):
    try:
        data = request.json
        new_name = data.get('Device_Name')
        new_user_id = data.get('User_ID')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        update_query = "UPDATE Device SET Device_Name = %s, User_ID = %s WHERE Device_ID = %s"
        cursor.execute(update_query, (new_name, new_user_id, device_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"success": True, "message": "Device updated successfully"})
    except Exception as e:
        print(f"Error updating device: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/device/delete/<string:device_id>', methods=['DELETE'])
@login_required
def delete_device(device_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        delete_query = "DELETE FROM Device WHERE Device_ID = %s"
        cursor.execute(delete_query, (device_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"success": True, "message": "Device deleted successfully"})
    except Exception as e:
        print(f"Error deleting device: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/devices', methods=['GET'])
@login_required
def get_all_devices():
    try:
        conn = get_db_connection()
        query = """
        SELECT 
            d.Device_ID, 
            d.Device_Name, 
            d.Device_Type, 
            d.MAC_Address, 
            d.User_ID,
            COALESCE(SUM(du.Data_Downloaded + du.Data_Uploaded) / 1024, 0) as totalGB,
            MAX(cl.Timestamp) as lastSeen
        FROM Device d
        LEFT JOIN Connection_Log cl ON d.Device_ID = cl.Device_ID
        LEFT JOIN Data_Usage du ON cl.Log_ID = du.Log_ID
        GROUP BY d.Device_ID, d.Device_Name, d.Device_Type, d.MAC_Address, d.User_ID
        ORDER BY totalGB DESC
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
        df['lastSeen'] = df['lastSeen'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(x) else 'Never')
        
        return jsonify(df.to_dict('records'))
    except Exception as e:
        print(f"Error in /api/devices: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/users', methods=['GET'])
@login_required
def get_all_users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT User_ID, First_Name, Second_Name, Email_ID, Phone_No FROM User"
        cursor.execute(query)
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(users)
    except Exception as e:
        print(f"Error in /api/users: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/add', methods=['POST'])
@login_required
def add_user():
    try:
        data = request.json
        user_id = f'U{str(int(datetime.now().timestamp() * 1000))[-8:]}'
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Generate default password hash for new users
        default_password_hash = generate_password_hash('password', method='pbkdf2:sha256')
        
        insert_query = """
        INSERT INTO User (User_ID, First_Name, Second_Name, Email_ID, Phone_No, Password_Hash)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (
            user_id,
            data.get('first_name'),
            data.get('second_name'),
            data.get('email'),
            data.get('phone'),
            default_password_hash
        ))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"success": True, "message": "User added successfully", "user_id": user_id})
    except Exception as e:
        print(f"Error adding user: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/dashboard-stats', methods=['GET'])
@login_required
def get_dashboard_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(DISTINCT Device_ID) as count FROM Device")
        connected_devices = cursor.fetchone()['count']
        
        cursor.execute("SELECT COALESCE(SUM(Data_Downloaded + Data_Uploaded) / 1024, 0) as total FROM Data_Usage")
        total_usage = cursor.fetchone()['total']
        
        top_device_query = """
        SELECT d.Device_Name, COALESCE(SUM(du.Data_Downloaded + du.Data_Uploaded) / 1024, 0) as totalGB
        FROM Device d
        LEFT JOIN Connection_Log cl ON d.Device_ID = cl.Device_ID
        LEFT JOIN Data_Usage du ON cl.Log_ID = du.Log_ID
        GROUP BY d.Device_ID, d.Device_Name
        ORDER BY totalGB DESC
        LIMIT 1
        """
        cursor.execute(top_device_query)
        top_device = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "connectedDevices": connected_devices,
            "totalUsageGB": round(total_usage, 2),
            "topDevice": {
                "name": top_device['Device_Name'] if top_device else 'N/A',
                "usageGB": round(top_device['totalGB'], 2) if top_device else 0
            }
        })
    except Exception as e:
        print(f"Error in /api/dashboard-stats: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/usage-over-time', methods=['GET'])
@login_required
def get_usage_over_time():
    try:
        conn = get_db_connection()
        query = """
        SELECT cl.Timestamp, (du.Data_Downloaded + du.Data_Uploaded) as total_usage
        FROM Data_Usage du
        JOIN Connection_Log cl ON du.Log_ID = cl.Log_ID
        ORDER BY cl.Timestamp
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
        if df.empty:
            return jsonify({"labels": [], "data": []})
        
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        usage_resampled = df.set_index('Timestamp').resample('1H')['total_usage'].sum().cumsum() / 1024
        
        return jsonify({
            "labels": usage_resampled.index.strftime('%m-%d %H:%M').tolist(),
            "data": usage_resampled.values.round(2).tolist()
        })
    except Exception as e:
        print(f"Error in /api/usage-over-time: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/top-devices-today', methods=['GET'])
@login_required
def get_top_devices_today():
    try:
        conn = get_db_connection()
        today = datetime.now().date()
        query = """
        SELECT d.Device_Name, COALESCE(SUM(du.Data_Downloaded + du.Data_Uploaded) / 1024, 0) as totalGB
        FROM Device d
        LEFT JOIN Connection_Log cl ON d.Device_ID = cl.Device_ID
        LEFT JOIN Data_Usage du ON cl.Log_ID = du.Log_ID
        WHERE DATE(cl.Timestamp) = %s
        GROUP BY d.Device_ID, d.Device_Name
        ORDER BY totalGB DESC
        LIMIT 5
        """
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, (today,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({
            "labels": [r['Device_Name'] for r in results],
            "data": [round(r['totalGB'], 2) for r in results]
        })
    except Exception as e:
        print(f"Error in /api/top-devices-today: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/network-overview', methods=['GET'])
@login_required
def get_network_overview():
    try:
        conn = get_db_connection()
        query = """
        SELECT 
            n.SSID,
            COALESCE(SUM(du.Data_Downloaded + du.Data_Uploaded) / 1024, 0) as totalGB,
            COUNT(DISTINCT cl.Device_ID) as deviceCount
        FROM Network n
        LEFT JOIN Connection_Log cl ON n.Network_ID = cl.Network_ID
        LEFT JOIN Data_Usage du ON cl.Log_ID = du.Log_ID
        GROUP BY n.Network_ID, n.SSID
        ORDER BY totalGB DESC
        """
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({
            "tableData": [{"ssid": r['SSID'], "totalGB": float(r['totalGB']), "deviceCount": r['deviceCount']} for r in results],
            "chartData": {
                "labels": [r['SSID'] for r in results],
                "data": [round(float(r['totalGB']), 2) for r in results]
            }
        })
    except Exception as e:
        print(f"Error in /api/network-overview: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)