from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import tinytuya
import requests
import datetime
from datetime import datetime as dt
import schedule
import time
import threading
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DB_PATH = 'devices.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS devices (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT,
                            type TEXT,
                            device_id TEXT,
                            local_key TEXT,
                            location TEXT,
                            config TEXT,
                            status INTEGER DEFAULT 0,
                            timer TEXT
                        )''')
        conn.commit()

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(devices)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]

        if 'status' not in column_names:
            cursor.execute("ALTER TABLE devices ADD COLUMN status INTEGER DEFAULT 0")
            conn.commit()
        
        if 'timer' not in column_names:
            cursor.execute("ALTER TABLE devices ADD COLUMN timer TEXT")
            conn.commit()

        conn.execute('''CREATE TABLE IF NOT EXISTS daylight_config (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            sunrise_time TEXT,
                            sunset_time TEXT,
                            target_length INTEGER,
                            days_to_reach INTEGER,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                        )''')
        conn.commit()

init_db()

def get_weather():
    API_KEY = '80929de7dd9a4b60b28195216251205'
    LOCATION = 'London'
    url = f'https://api.weatherapi.com/v1/current.json?key={API_KEY}&q={LOCATION}'
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        try:
            return {
                'temp': f"{data['current']['temp_c']}°C",
                'desc': data['current']['condition']['text'],
                'location': data['location']['name'] if 'location' in data else 'Unknown',
                'wind': f"{data['current']['wind_kph']} kph",
                'humidity': f"{data['current']['humidity']}%",
                'pressure': f"{data['current']['pressure_mb']} hPa",
                'icon': data['current']['condition']['icon']
            }
        except KeyError as e:
            print(f"Weather data missing key: {e}")
            return None
    else:
        print(f"Weather API request failed with status code: {response.status_code}")
        return None

def calculate_lighting_state():
    config = get_daylight_config()
    
    if not config:
        return None
    
    now = dt.now()
    current_time = now.hour * 60 + now.minute
    
    try:
        sunrise_min = int(config['sunrise_time'].split(':')[0]) * 60 + int(config['sunrise_time'].split(':')[1])
        sunset_min = int(config['sunset_time'].split(':')[0]) * 60 + int(config['sunset_time'].split(':')[1])
    except:
        return None
    
    daylight_duration = sunset_min - sunrise_min
    
    if current_time < sunrise_min:
        return {'state': 'night', 'brightness': 0}
    
    elif current_time < sunrise_min + 30:  
        elapsed = current_time - sunrise_min
        brightness = int(elapsed / 30 * 100)
        return {'state': 'sunrise', 'brightness': brightness}
    
    elif current_time < sunset_min:
        return {'state': 'day', 'brightness': 100}
    
    elif current_time < sunset_min + 30:  
        elapsed = current_time - sunset_min
        brightness = 100 - int(elapsed / 30 * 100)
        return {'state': 'sunset', 'brightness': brightness}
    
    else:
        return {'state': 'night', 'brightness': 0}

def get_daylight_config():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        config = conn.execute("SELECT * FROM daylight_config ORDER BY created_at DESC LIMIT 1").fetchone()
    return config if config else None

def control_lights():
    lighting_state = calculate_lighting_state()
    if not lighting_state:
        return
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        devices = conn.execute("SELECT * FROM devices WHERE type IN ('bulb', 'plug')").fetchall()
        
        for device in devices:
            try:
                if device['type'] == 'bulb':
                    client = tinytuya.BulbDevice(device['device_id'], None, device['local_key'])
                    client.set_version(3.3)
                    
                    if lighting_state['state'] == 'night':
                        client.turn_off()
                    else:
                        client.set_brightness(lighting_state['brightness'])
                
                elif device['type'] == 'plug':
                    client = tinytuya.OutletDevice(device['device_id'], None, device['local_key'])
                    client.set_version(3.3)
                    
                    if lighting_state['state'] == 'day':
                        client.turn_on()
                    else:
                        client.turn_off()
            except Exception as e:
                print(f"Error controlling device {device['name']}: {str(e)}")

@app.route('/')
def dashboard():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        devices = conn.execute("SELECT * FROM devices").fetchall()
    
    weather = get_weather()
    lighting_state = calculate_lighting_state()
    
    return render_template('index.html', 
                          devices=devices, 
                          weather=weather,
                          lighting_state=lighting_state)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        config = {
            "supportsDimming": data.get('supportsDimming', 'false'),
            "supportsColorTemp": data.get('supportsColorTemp', 'false'),
            "maxPower": data.get('maxPower', '0'),
            "sensorType": data.get('sensorType', '')
        }
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''INSERT INTO devices 
                            (name, type, device_id, local_key, location, config) 
                            VALUES (?, ?, ?, ?, ?, ?)''',
                         (data['deviceName'], data['deviceType'], data['deviceID'],
                          data['localKey'], data['location'], str(config)))
        return redirect(url_for('dashboard'))
    return render_template('deviceregistrationpage.html')

@app.route('/daylight_config', methods=['GET', 'POST'])
def daylight_config():
    if request.method == 'POST':
        config = {
            'sunrise_time': request.form.get('sunrise_time'),
            'sunset_time': request.form.get('sunset_time'),
            'target_length': request.form.get('target_length'),
            'days_to_reach': request.form.get('days_to_reach')
        }
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''INSERT INTO daylight_config 
                           (sunrise_time, sunset_time, target_length, days_to_reach)
                           VALUES (?, ?, ?, ?)''',
                        (config['sunrise_time'], config['sunset_time'], 
                         config['target_length'], config['days_to_reach']))
            conn.commit()
        return redirect(url_for('dashboard'))
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        config = conn.execute("SELECT * FROM daylight_config ORDER BY created_at DESC LIMIT 1").fetchone()
    
    return render_template('daylight_config.html', config=config)

@app.route('/delete_device/<int:device_id>', methods=['POST'])
def delete_device(device_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        conn.commit()
    return redirect(url_for('dashboard'))

@app.route('/toggle_device/<int:device_id>', methods=['POST'])
def toggle_device(device_id):
    new_status = 1 if request.form.get('status') == 'true' else 0
    
    with sqlite3.connect(DB_PATH) as conn:
        try:
            device = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
            
            if new_status == 1:
                # Get daylight configuration
                config = get_daylight_config()
                target_length = int(config['target_length']) if config else 6
                
                timer_end = (datetime.datetime.now() + datetime.timedelta(hours=target_length)).strftime('%Y-%m-%d %H:%M:%S')
                conn.execute("UPDATE devices SET status = ?, timer = ? WHERE id = ?", (new_status, timer_end, device_id))
            else:
                conn.execute("UPDATE devices SET status = ?, timer = NULL WHERE id = ?", (new_status, device_id))
            
            conn.commit()
        except sqlite3.OperationalError as e:
            print(f"Database error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    return jsonify({"status": "success"})

@app.route('/get_devices')
def get_devices():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        devices = conn.execute("SELECT * FROM devices").fetchall()
    devices_list = [dict(row) for row in devices]
    return jsonify(devices_list)

@app.route('/get_lighting_status')
def get_lighting_status():
    lighting_state = calculate_lighting_state()
    config = get_daylight_config()
    if config:
        lighting_state['target_length'] = config['target_length']
    return jsonify(lighting_state)

@app.route('/get_lighting_config')
def get_lighting_config():
    config = get_daylight_config()
    if config:
        return jsonify({
            'sunrise_time': config['sunrise_time'],
            'sunset_time': config['sunset_time'],
            'target_length': config['target_length'],
            'days_to_reach': config['days_to_reach']
        })
    else:
        return jsonify({
            'sunrise_time': '08:00',
            'sunset_time': '20:00',
            'target_length': 6,
            'days_to_reach': 30
        })

def run_scheduler():
    schedule.every().minute.do(control_lights)
    while True:
        schedule.run_pending()
        time.sleep(1)

# threading.Thread(target=run_scheduler).start()
threading.Thread(target=run_scheduler, daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True, host='0.000.0')