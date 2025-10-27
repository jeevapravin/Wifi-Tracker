from flask import Flask, jsonify, request, make_response, redirect, url_for, flash, render_template_string
import mysql.connector
from flask_cors import CORS
import pandas as pd
from datetime import datetime, timedelta
import uuid
# --- NEW: Imports for Authentication ---
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os # For secret key

app = Flask(__name__)
# --- NEW: Secret Key is required for session management ---
app.secret_key = os.urandom(24) # Generates a random secret key
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# --- NEW: Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirect to 'login' route if not logged in

# --- DATABASE CONFIGURATION (Unchanged) ---
db_config = { 'host': 'localhost', 'user': 'root', 'password': '1234', 'database': 'dbms_proj' }

def get_db_connection():
    return mysql.connector.connect(**db_config)

# --- NEW: User Class for Flask-Login ---
class User(UserMixin):
    def __init__(self, id, email, first_name):
        self.id = id
        self.email = email
        self.first_name = first_name

# --- NEW: User Loader for Flask-Login ---
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

# --- *** NEW: LOGIN ROUTE *** ---
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
            login_user(user_obj) # Log the user in
            return redirect('/') # Redirect to the main app page
        else:
            flash('Invalid email or password', 'error') # Show error message

    # Simple HTML form for login
    login_html = """
    <!DOCTYPE html><html><head><title>Login</title><style>body{font-family:sans-serif;background:#1a1c23;color:white;display:flex;justify-content:center;align-items:center;height:100vh;} form{background:#252831;padding:40px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.2);} h1{text-align:center;margin-bottom:20px;} div{margin-bottom:15px;} label{display:block;margin-bottom:5px;} input{width:100%;padding:10px;background:#1a1c23;border:1px solid #3b3e47;color:white;border-radius:4px;} button{width:100%;padding:10px;background:#3b82f6;border:none;color:white;border-radius:4px;cursor:pointer;} .flash{color:#ef4444;text-align:center;margin-bottom:15px;}</style></head><body>
    <form method="post"><h1>LinkSphere Login</h1>{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="flash">{{ message }}</div>{% endfor %}{% endif %}{% endwith %}<div><label for="email">Email:</label><input type="email" id="email" name="email" required></div><div><label for="password">Password:</label><input type="password" id="password" name="password" required></div><button type="submit">Login</button></form></body></html>
    """
    return render_template_string(login_html)

# --- *** NEW: LOGOUT ROUTE *** ---
@app.route('/logout')
@login_required # Must be logged in to log out
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- *** NEW: MAIN APP ROUTE *** ---
# Serves the index.html file, but only if logged in
@app.route('/')
@login_required
def index():
    # Since we are using Flask now, we might need to serve index.html differently
    # For simplicity, let's keep opening index.html directly for now.
    # A better way would be: return app.send_static_file('index.html')
    # if index.html is in a 'static' folder.
    # For now, just redirecting - user needs to open index.html manually after login.
    # OR, we could serve it directly:
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            content = f.read()
        return render_template_string(content)
    except FileNotFoundError:
        return "Error: index.html not found.", 404


# --- PROTECTED API ENDPOINTS ---
# Now add @login_required to all your existing API endpoints
@app.route('/api/device/<string:device_id>', methods=['GET'])
@login_required
def get_device_details(device_id):
    # ... (function body unchanged) ...
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        details_query = "SELECT d.Device_Name, d.Device_Type, d.MAC_Address, u.First_Name, u.Second_Name FROM Device d JOIN User u ON d.User_ID = u.User_ID WHERE d.Device_ID = %s"
        cursor.execute(details_query, (device_id,))
        device_details = cursor.fetchone()
        if not device_details: return jsonify({"error": "Device not found"}), 404
        usage_query = "SELECT cl.Timestamp, (du.Data_Downloaded + du.Data_Uploaded) as total_usage FROM Data_Usage du JOIN Connection_Log cl ON du.Log_ID = cl.Log_ID WHERE cl.Device_ID = %s ORDER BY cl.Timestamp;"
        df = pd.read_sql(usage_query, conn, params=(device_id,))
        usage_graph_data = {"labels": [], "data": []}
        if not df.empty:
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            usage_resampled = df.set_index('Timestamp').resample('5min')['total_usage'].sum().cumsum() / 1024
            usage_graph_data = {"labels": usage_resampled.index.strftime('%H:%M').tolist(),"data": usage_resampled.values.round(2).tolist()}
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
    # ... (function body unchanged) ...
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
    # ... (function body unchanged) ...
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
def update_device_api(device_id): # Renamed slightly to avoid conflict with decorator
    return update_device(device_id)

@app.route('/api/device/delete/<string:device_id>', methods=['DELETE'])
@login_required
def delete_device_api(device_id): # Renamed slightly
    return delete_device(device_id)

@app.route('/api/devices', methods=['GET'])
@login_required
def get_all_devices_api(): # Renamed slightly
     return get_all_devices()

@app.route('/api/users', methods=['GET'])
@login_required
def get_all_users_api(): # Renamed slightly
    return get_all_users()

@app.route('/api/users/add', methods=['POST'])
@login_required
def add_user_api(): # Renamed slightly
    return add_user()

@app.route('/api/dashboard-stats', methods=['GET'])
@login_required
def get_dashboard_stats_api(): # Renamed slightly
    return get_dashboard_stats()

@app.route('/api/usage-over-time', methods=['GET'])
@login_required
def get_usage_over_time_api(): # Renamed slightly
    return get_usage_over_time()

@app.route('/api/top-devices-today', methods=['GET'])
@login_required
def get_top_devices_today_api(): # Renamed slightly
    return get_top_devices_today()

@app.route('/api/network-overview', methods=['GET'])
@login_required
def get_network_overview_api(): # Renamed slightly
    return get_network_overview()


if __name__ == '__main__':
    # Important: Run on 0.0.0.0 to be accessible on your network if needed
    # debug=False is safer for production, but True is ok for development
    app.run(host='0.0.0.0', port=5000, debug=True)