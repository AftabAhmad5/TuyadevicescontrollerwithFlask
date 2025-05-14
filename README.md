# Smart Home Dashboard (Flask + Tuya + SQLite)

## Features
- Register Tuya smart devices with local key and type
- Dashboard displaying:
  - Weather info (placeholder for API)
  - Tuya device controls with on/off timers
  - Radio station UI
  - Thermometer widget
  - Registered device inventory
- Flask backend with SQLite database
- `tinytuya` integration for device control

## Setup Instructions

### 1. Extract ZIP & Open Terminal

```bash
cd path/to/smart_home_dashboard
```

### 2. (Optional) Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate         # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the App

```bash
python app.py
```

Access the dashboard at `http://127.0.0.1:5000/`

---

## Tuya Device Control Notes

- Replace `'192.168.1.100'` in `app.py` with your device's local IP address.
- Devices must be local network-compatible with `tinytuya`.
- Tested with version `3.3` protocol; update `set_version()` if needed.

---

## Weather API Placeholder

In `index.html`, locate the comment:

```js
// Weather API placeholder - you'll replace this with your own API call
```

Add your weather API logic there using OpenWeatherMap, WeatherAPI, etc.

Example:
```js
fetch('https://api.openweathermap.org/data/2.5/weather?q=London&appid=YOUR_API_KEY')
```

---

## SQLite

The DB file `devices.db` is created automatically on first run.
You can browse it using tools like [DB Browser for SQLite](https://sqlitebrowser.org/).
