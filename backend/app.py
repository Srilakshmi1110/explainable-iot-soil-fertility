import os
import sys
import json
import sqlite3
import threading
import time
import hashlib
import secrets
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import joblib
import serial
import rasterio
from rasterio.warp import transform as warp_transform
from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = BASE_DIR / "backend"
MODEL_DIR = BACKEND_DIR / "models"
DATA_DIR = BACKEND_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
DB_FILE = DATA_DIR / "predictions.db"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
    import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import config

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.secret_key = getattr(config, "SECRET_KEY", "change-this-local-secret")
CORS(app, supports_credentials=True)

FEATURES = ["latitude", "longitude", "ph", "moisture", "nitrogen", "cec"]
RASTER_FILES = {
    "ph": DATA_DIR / "ph.tif",
    "moisture": DATA_DIR / "moisture.tif",
    "nitrogen": DATA_DIR / "nitrogen.tif",
    "cec": DATA_DIR / "cec.tif",
}

print("=" * 70)
print("EXPLAINABLE IoT FRAMEWORK FOR SOIL FERTILITY PREDICTION")
print("=" * 70)

# ---------------- Models ----------------
print("Loading trained models...")
lgb_model = joblib.load(MODEL_DIR / "lgb_model.joblib")
cat_model = joblib.load(MODEL_DIR / "cat_model.joblib")
background_data = joblib.load(MODEL_DIR / "background_data.joblib")
class_names = list(joblib.load(MODEL_DIR / "class_names.joblib"))
feature_names = list(joblib.load(MODEL_DIR / "feature_names.joblib"))
if feature_names != FEATURES:
    raise RuntimeError(f"Model features are {feature_names}; expected {FEATURES}")
print("Models loaded:", feature_names)

# Explainability is loaded lazily so the server can still start if a package is unavailable.
try:
    import shap
except Exception:
    shap = None
try:
    from lime.lime_tabular import LimeTabularExplainer
except Exception:
    LimeTabularExplainer = None

shap_explainer = None
lime_explainer = None
if shap is not None:
    try:
        shap_explainer = shap.TreeExplainer(lgb_model)
    except Exception as e:
        print("SHAP initialization warning:", e)
if LimeTabularExplainer is not None:
    try:
        lime_explainer = LimeTabularExplainer(
            np.asarray(background_data),
            feature_names=FEATURES,
            class_names=class_names,
            mode="classification",
            discretize_continuous=True,
            random_state=42,
        )
    except Exception as e:
        print("LIME initialization warning:", e)

# ---------------- Database ----------------
DB_LOCK = threading.Lock()

def db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DB_LOCK:
        conn = db()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(predictions)")
        old_cols = [r[1] for r in cur.fetchall()]
        required = {"timestamp", "ph", "moisture", "nitrogen", "cec"}
        if old_cols and not required.issubset(old_cols):
            legacy = f"predictions_legacy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            cur.execute(f"ALTER TABLE predictions RENAME TO {legacy}")
            print("Renamed incompatible predictions table to", legacy)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id INTEGER,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                ph REAL NOT NULL,
                moisture REAL NOT NULL,
                nitrogen REAL NOT NULL,
                cec REAL NOT NULL,
                fertility TEXT NOT NULL,
                confidence REAL NOT NULL,
                lgb_prediction TEXT NOT NULL,
                cat_prediction TEXT NOT NULL,
                lgb_confidence REAL NOT NULL,
                cat_confidence REAL NOT NULL,
                model_agreement INTEGER NOT NULL,
                shap_data TEXT,
                lime_data TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
        conn.close()
    print("Database initialized")

init_database()

# ---------------- Runtime state ----------------
state_lock = threading.Lock()
current = {
    "connected": False,
    "reading": None,
    "prediction": None,
    "explanation": None,
    "timestamp": None,
    "location_source": None,
    "error": "Waiting for real Arduino data."
}
arduino = None

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return salt.hex() + ":" + digest.hex()

def verify_password(password, stored):
    try:
        salt_hex, digest_hex = stored.split(":")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000)
        return secrets.compare_digest(candidate.hex(), digest_hex)
    except Exception:
        return False

# ---------------- Raster lookup ----------------
def raster_value(path, lat, lon):
    if not path.exists():
        raise FileNotFoundError(f"Missing raster: {path.name}")
    with rasterio.open(path) as src:
        xs, ys = warp_transform("EPSG:4326", src.crs, [lon], [lat])
        row, col = src.index(xs[0], ys[0])
        if row < 0 or col < 0 or row >= src.height or col >= src.width:
            raise ValueError(f"Location is outside {path.name}")
        value = src.read(1, window=((row, row + 1), (col, col + 1)))[0, 0]
        nodata = src.nodata
        if nodata is not None and np.isclose(value, nodata):
            raise ValueError(f"No valid value at this location in {path.name}")
        if not np.isfinite(value):
            raise ValueError(f"No valid value at this location in {path.name}")
        return float(value)

def enrich_sensor_reading(ph, moisture, lat, lon):
    return {
        "latitude": float(lat),
        "longitude": float(lon),
        "ph": float(ph),
        "moisture": float(moisture),
        "nitrogen": raster_value(RASTER_FILES["nitrogen"], lat, lon),
        "cec": raster_value(RASTER_FILES["cec"], lat, lon),
    }

# ---------------- ML ----------------
def predict_soil(values):
    X = pd.DataFrame([[values[f] for f in FEATURES]], columns=FEATURES)
    lgb_probs = np.asarray(lgb_model.predict_proba(X))[0]
    cat_probs = np.asarray(cat_model.predict_proba(X))[0]
    lgb_idx = int(np.argmax(lgb_probs))
    cat_idx = int(np.argmax(cat_probs))
    # CatBoost can expose class order; use its classes when available.
    lgb_pred = str(lgb_model.classes_[lgb_idx]) if hasattr(lgb_model, "classes_") else str(lgb_model.predict(X)[0])
    cat_classes = list(getattr(cat_model, "classes_", class_names))
    cat_pred = str(cat_classes[cat_idx]) if cat_idx < len(cat_classes) else str(cat_model.predict(X)[0])
    lgb_conf = float(lgb_probs[lgb_idx])
    cat_conf = float(cat_probs[cat_idx])
    agreement = lgb_pred == cat_pred
    fertility = lgb_pred if agreement else (lgb_pred if lgb_conf >= cat_conf else cat_pred)
    confidence = (lgb_conf + cat_conf) / 2 if agreement else max(lgb_conf, cat_conf)
    return {
        **values,
        "fertility": fertility,
        "confidence": float(confidence),
        "lgb_prediction": lgb_pred,
        "cat_prediction": cat_pred,
        "lgb_confidence": lgb_conf,
        "cat_confidence": cat_conf,
        "model_agreement": agreement,
        "timestamp": utc_now(),
    }, X

def explain(X, result):
    shap_items = []
    lime_items = []
    if shap_explainer is not None:
        try:
            sv = shap_explainer(X)
            vals = np.asarray(sv.values)
            if vals.ndim == 3:
                # class dimension
                class_idx = list(lgb_model.classes_).index(result["lgb_prediction"])
                vals = vals[0, :, class_idx]
            else:
                vals = vals[0]
            for f, v in zip(FEATURES, vals):
                shap_items.append({"feature": f, "value": float(v)})
        except Exception as e:
            print("SHAP warning:", e)
    if lime_explainer is not None:
        try:
            exp = lime_explainer.explain_instance(
                X.iloc[0].values,
                lambda a: lgb_model.predict_proba(pd.DataFrame(a, columns=FEATURES)),
                num_features=len(FEATURES),
            )
            for feature, weight in exp.as_list():
                lime_items.append({"feature": feature, "weight": float(weight)})
        except Exception as e:
            print("LIME warning:", e)
    return {"shap": shap_items, "lime": lime_items}

def save_prediction(result, explanation):
    with DB_LOCK:
        conn = db()
        conn.execute("""
            INSERT INTO predictions (
                timestamp,user_id,latitude,longitude,ph,moisture,nitrogen,cec,
                fertility,confidence,lgb_prediction,cat_prediction,
                lgb_confidence,cat_confidence,model_agreement,shap_data,lime_data
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            result["timestamp"], session.get("user_id"),
            result["latitude"], result["longitude"], result["ph"], result["moisture"],
            result["nitrogen"], result["cec"], result["fertility"], result["confidence"],
            result["lgb_prediction"], result["cat_prediction"],
            result["lgb_confidence"], result["cat_confidence"],
            int(result["model_agreement"]),
            json.dumps(explanation.get("shap", [])),
            json.dumps(explanation.get("lime", [])),
        ))
        conn.commit()
        conn.close()

# ---------------- Arduino ----------------
def connect_arduino():
    global arduino
    port = getattr(config, "SERIAL_PORT", "COM3")
    baud = int(getattr(config, "SERIAL_BAUD", 9600))
    try:
        arduino = serial.Serial(port, baud, timeout=1)
        time.sleep(2)
        print(f"Arduino connected on {port}")
    except Exception as e:
        arduino = None
        print("Arduino offline:", e)

def read_arduino():
    if arduino is None:
        return None
    try:
        line = arduino.readline().decode("utf-8", errors="ignore").strip()
        if not line or line.startswith("-") or not line[0].isdigit():
            return None
        parts = line.split(",")
        if len(parts) != 2:
            return None
        ph, moisture = map(float, parts)
        if not (0 <= ph <= 14 and 0 <= moisture <= 100):
            return None
        return ph, moisture
    except Exception:
        return None

def get_location():
    with DB_LOCK:
        conn = db()
        row = conn.execute("SELECT value FROM app_state WHERE key='location'").fetchone()
        conn.close()
    if not row:
        return None
    try:
        return json.loads(row["value"])
    except Exception:
        return None

def sensor_loop():
    global current
    while True:
        reading = read_arduino()
        if reading:
            location = get_location()
            if location:
                try:
                    values = enrich_sensor_reading(reading[0], reading[1], location["latitude"], location["longitude"])
                    result, X = predict_soil(values)
                    explanation = explain(X, result)
                    with state_lock:
                        current = {
                            "connected": True,
                            "reading": values,
                            "prediction": result,
                            "explanation": explanation,
                            "timestamp": result["timestamp"],
                            "location_source": location.get("source", "browser"),
                            "error": None,
                        }
                    save_prediction(result, explanation)
                except Exception as e:
                    with state_lock:
                        current["connected"] = True
                        current["error"] = str(e)
            else:
                with state_lock:
                    current["connected"] = True
                    current["error"] = "Arduino is connected. Set your field location to read nitrogen and CEC."
        else:
            with state_lock:
                current["connected"] = arduino is not None
                if arduino is None:
                    current["error"] = "Arduino disconnected. No simulated values are used."
        time.sleep(2)

connect_arduino()
threading.Thread(target=sensor_loop, daemon=True).start()

# ---------------- API helpers ----------------
def auth_required():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Login required"}), 401
    return None

@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    name, email, password = data.get("name", "").strip(), data.get("email", "").strip().lower(), data.get("password", "")
    if not name or not email or len(password) < 6:
        return jsonify({"success": False, "error": "Name, email and a password of at least 6 characters are required."}), 400
    try:
        with DB_LOCK:
            conn = db()
            cur = conn.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)", (name,email,hash_password(password)))
            conn.commit()
            uid = cur.lastrowid
            conn.close()
        session["user_id"], session["user_name"] = uid, name
        return jsonify({"success": True, "user": {"id": uid, "name": name, "email": email}})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "An account with that email already exists."}), 409

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email, password = data.get("email", "").strip().lower(), data.get("password", "")
    with DB_LOCK:
        conn = db()
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
    if not row or not verify_password(password, row["password_hash"]):
        return jsonify({"success": False, "error": "Invalid email or password."}), 401
    session["user_id"], session["user_name"] = row["id"], row["name"]
    return jsonify({"success": True, "user": {"id": row["id"], "name": row["name"], "email": row["email"]}})

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/auth/me")
def me():
    if "user_id" not in session:
        return jsonify({"authenticated": False})
    with DB_LOCK:
        conn = db()
        row = conn.execute("SELECT id,name,email FROM users WHERE id=?", (session["user_id"],)).fetchone()
        conn.close()
    return jsonify({"authenticated": bool(row), "user": dict(row) if row else None})

@app.route("/api/location", methods=["GET","POST"])
def location():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        try:
            lat, lon = float(data["latitude"]), float(data["longitude"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
            payload = {"latitude": lat, "longitude": lon, "source": data.get("source","browser")}
            with DB_LOCK:
                conn = db()
                conn.execute("INSERT OR REPLACE INTO app_state(key,value) VALUES('location',?)", (json.dumps(payload),))
                conn.commit(); conn.close()
            return jsonify({"success": True, "location": payload})
        except Exception:
            return jsonify({"success": False, "error": "Invalid latitude/longitude."}), 400
    return jsonify({"location": get_location()})

@app.route("/api/latest")
def latest():
    with state_lock:
        return jsonify(current)

@app.route("/api/status")
def status():
    return jsonify({
        "models_loaded": True,
        "arduino_connected": arduino is not None,
        "features": FEATURES,
        "shap_available": shap_explainer is not None,
        "lime_available": lime_explainer is not None,
        "real_data_only": True,
    })

@app.route("/api/analytics")
def analytics():
    with DB_LOCK:
        conn = db()
        row = conn.execute("""
            SELECT COUNT(*) total,
                   AVG(ph) avg_ph, AVG(moisture) avg_moisture,
                   AVG(nitrogen) avg_nitrogen, AVG(cec) avg_cec,
                   AVG(confidence) avg_confidence,
                   AVG(model_agreement) agreement
            FROM predictions
        """).fetchone()
        dist = conn.execute("SELECT fertility, COUNT(*) count FROM predictions GROUP BY fertility").fetchall()
        conn.close()
    return jsonify({
        "total_predictions": row["total"] or 0,
        "avg_ph": row["avg_ph"],
        "avg_moisture": row["avg_moisture"],
        "avg_nitrogen": row["avg_nitrogen"],
        "avg_cec": row["avg_cec"],
        "average_confidence": row["avg_confidence"],
        "model_agreement_rate": (row["agreement"] * 100) if row["agreement"] is not None else None,
        "fertility_distribution": [dict(x) for x in dist],
    })

@app.route("/api/history")
def history():
    with DB_LOCK:
        conn = db()
        rows = conn.execute("""
            SELECT timestamp,latitude,longitude,ph,moisture,nitrogen,cec,
                   fertility,confidence,lgb_prediction,cat_prediction
            FROM predictions ORDER BY id DESC LIMIT 100
        """).fetchall()
        conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/weather")
def weather():
    loc = get_location()
    if not loc:
        return jsonify({"success": False, "error": "Set a field location first."}), 400
    params = urlencode({
        "latitude": loc["latitude"], "longitude": loc["longitude"],
        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "timezone": "auto"
    })
    try:
        with urlopen("https://api.open-meteo.com/v1/forecast?" + params, timeout=8) as r:
            data = json.loads(r.read().decode())
        return jsonify({"success": True, "location": loc, "current": data.get("current", {})})
    except Exception as e:
        return jsonify({"success": False, "error": f"Weather service unavailable: {e}"}), 503

@app.route("/api/crop-recommendations")
def crop_recommendations():
    with state_lock:
        reading = current.get("reading")
    if not reading:
        return jsonify({"success": False, "error": "Waiting for real soil data."}), 409
    p, m, n, c = reading["ph"], reading["moisture"], reading["nitrogen"], reading["cec"]
    # Agronomic screening rules; recommendations are explicitly marked as guidance, not a diagnosis.
    candidates = [
        ("Rice", 6.0 <= p <= 7.5 and m >= 55 and n >= 100, "Prefers moist soil and moderate nitrogen."),
        ("Wheat", 6.0 <= p <= 7.5 and 35 <= m <= 65 and n >= 100, "Fits near-neutral pH with moderate moisture."),
        ("Maize", 5.8 <= p <= 7.2 and 35 <= m <= 70 and n >= 120, "Benefits from adequate nitrogen and moderate moisture."),
        ("Groundnut", 5.5 <= p <= 7.0 and 25 <= m <= 60 and n < 500, "Tolerates moderately acidic soil and moderate moisture."),
        ("Millet", 5.5 <= p <= 7.5 and 20 <= m <= 55, "Generally suited to lower moisture conditions."),
    ]
    scored = []
    for crop, ok, reason in candidates:
        score = 0
        if ok: score += 2
        if 6.0 <= p <= 7.5: score += 1
        if 100 <= n <= 600: score += 1
        if c >= 100: score += 1
        scored.append({"crop": crop, "score": score, "reason": reason})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"success": True, "recommendations": scored[:3], "basis": reading})

@app.route("/api/health")
def health():
    return jsonify({"status": "online", "real_data_only": True, "arduino_connected": arduino is not None})

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/<path:path>")
def files(path):
    fp = FRONTEND_DIR / path
    if fp.is_file():
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, "index.html")

if __name__ == "__main__":
    host = getattr(config, "FLASK_HOST", "127.0.0.1")
    port = int(getattr(config, "FLASK_PORT", 5000))
    print(f"Open http://localhost:{port}")
    app.run(host=host, port=port, debug=True, use_reloader=False)
