import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import requests
import rasterio
from pyproj import Transformer
from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import sys
import os
from pathlib import Path

# =========================================================
# PROJECT PATH SETUP
# =========================================================

# Absolute path of backend/
BASE_DIR = Path(__file__).resolve().parent

# Absolute path of project root/
ROOT_DIR = BASE_DIR.parent

# Make project root importable
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Make backend importable too
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config

try:
    from advice_engine import crop_advice as advice_crop_advice
except Exception:
    advice_crop_advice = None

try:
    from advice_engine import get_crop_recommendations
except Exception:
    get_crop_recommendations = None

try:
    import shap
except Exception:
    shap = None

try:
    from lime.lime_tabular import LimeTabularExplainer
except Exception:
    LimeTabularExplainer = None


# ============================================================
# PATHS / APP
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

# Keep the existing database location so old project data is not
# silently moved to another database.
DB_FILE = DATA_DIR / "predictions.db"

app = Flask(
    __name__,
    static_folder=str(ROOT_DIR / "frontend"),
    static_url_path=""
)

app.secret_key = getattr(
    config,
    "SECRET_KEY",
    "change-this-local-secret"
)

CORS(
    app,
    supports_credentials=True
)


# ============================================================
# 7-FEATURE TEMPERATURE MODEL
# ============================================================

FEATURES = [
    "latitude",
    "longitude",
    "ph",
    "moisture",
    "temperature",
    "nitrogen",
    "cec",
]

LGB_PATH = MODELS_DIR / "lgb_model_temperature.joblib"
CAT_PATH = MODELS_DIR / "cat_model_temperature.joblib"
FEATURE_PATH = MODELS_DIR / "feature_names_temperature.joblib"
BACKGROUND_PATH = MODELS_DIR / "background_data_temperature.joblib"
CLASSES_PATH = MODELS_DIR / "class_names_temperature.joblib"

print("=" * 70)
print("EXPLAINABLE IoT FRAMEWORK FOR SOIL FERTILITY PREDICTION")
print("=" * 70)
print("Loading temperature-augmented models...")

lgb_model = joblib.load(LGB_PATH)
cat_model = joblib.load(CAT_PATH)
feature_names = list(joblib.load(FEATURE_PATH))
background_data = joblib.load(BACKGROUND_PATH)
class_names = list(joblib.load(CLASSES_PATH))

if feature_names != FEATURES:
    raise RuntimeError(
        f"Model features are {feature_names}; expected {FEATURES}"
    )

print("Models loaded:", feature_names)


# ============================================================
# EXPLAINABILITY
# ============================================================

shap_explainer = None
lime_explainer = None

if shap is not None:
    try:
        shap_explainer = shap.TreeExplainer(lgb_model)
    except Exception as exc:
        print("SHAP initialization warning:", exc)

if LimeTabularExplainer is not None:
    try:
        lime_explainer = LimeTabularExplainer(
            np.asarray(background_data),
            feature_names=FEATURES,
            class_names=[str(x) for x in class_names],
            mode="classification",
            discretize_continuous=True,
            random_state=42,
        )
    except Exception as exc:
        print("LIME initialization warning:", exc)


# ============================================================
# RASTERS
# ============================================================

RASTER_FILES = {
    "ph": DATA_DIR / "ph.tif",
    "nitrogen": DATA_DIR / "nitrogen.tif",
    "cec": DATA_DIR / "cec.tif",
}

RASTER_CRS = "ESRI:54052"

raster_transformer = Transformer.from_crs(
    "EPSG:4326",
    RASTER_CRS,
    always_xy=True
)


# ============================================================
# DATABASE
# ============================================================

DB_LOCK = threading.Lock()


def db():
    conn = sqlite3.connect(
        DB_FILE,
        timeout=30
    )
    conn.row_factory = sqlite3.Row
    return conn


def add_column_if_missing(cur, table, column, definition):
    columns = {
        row[1]
        for row in cur.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }

    if column not in columns:
        cur.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def init_database():
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with DB_LOCK:
        conn = db()
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id INTEGER,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                input_mode TEXT DEFAULT 'iot',
                ph REAL NOT NULL,
                moisture REAL NOT NULL,
                temperature REAL,
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
                crop_recommendation TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                timestamp TEXT NOT NULL,
                moisture REAL,
                temperature REAL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )

        # Upgrade an older predictions table without destroying it.
        add_column_if_missing(
            cur, "predictions", "input_mode",
            "TEXT DEFAULT 'iot'"
        )
        add_column_if_missing(
            cur, "predictions", "temperature",
            "REAL"
        )
        add_column_if_missing(
            cur, "predictions", "crop_recommendation",
            "TEXT"
        )

        add_column_if_missing(
            cur, "users", "username",
            "TEXT"
        )
        add_column_if_missing(
            cur, "users", "mobile",
            "TEXT"
        )
        add_column_if_missing(
            cur, "sensor_readings", "ph",
            "REAL"
        )

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username) WHERE username IS NOT NULL AND username != ''"
        )

        conn.commit()
        conn.close()

    print("Database initialized:", DB_FILE)


init_database()


# ============================================================
# HELPERS
# ============================================================

def utc_now():
    return datetime.utcnow().isoformat() + "Z"


def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    with DB_LOCK:
        conn = db()
        row = conn.execute(
            "SELECT id, name, username, email, mobile FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        conn.close()

    return row


def login_required():
    user = current_user()

    if user is None:
        return None, (
            jsonify({
                "success": False,
                "error": "Login required"
            }),
            401
        )

    return user, None


def number(data, key, minimum=None, maximum=None):
    value = data.get(key)

    if value is None or value == "":
        raise ValueError(f"{key} is required")

    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be numeric")

    if minimum is not None and value < minimum:
        raise ValueError(f"{key} is below the allowed range")

    if maximum is not None and value > maximum:
        raise ValueError(f"{key} is above the allowed range")

    return value


# ============================================================
# LOCATION / RASTER
# ============================================================

def save_location(latitude, longitude, source="browser"):
    payload = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "source": source
    }

    with DB_LOCK:
        conn = db()
        conn.execute(
            """
            INSERT OR REPLACE INTO app_state(key, value)
            VALUES ('location', ?)
            """,
            (json.dumps(payload),)
        )
        conn.commit()
        conn.close()

    return payload


def get_location():
    with DB_LOCK:
        conn = db()
        row = conn.execute(
            "SELECT value FROM app_state WHERE key = 'location'"
        ).fetchone()
        conn.close()

    if not row:
        return None

    try:
        return json.loads(row["value"])
    except Exception:
        return None
    RASTER_CRS = "ESRI:54052"

raster_transformer = Transformer.from_crs(
    "EPSG:4326",
    RASTER_CRS,
    always_xy=True
)


def raster_value(path, latitude, longitude):
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Missing raster: {path.name}"
        )

    x, y = raster_transformer.transform(
        float(longitude),
        float(latitude)
    )

    with rasterio.open(path) as src:

        row, col = src.index(x, y)

        if (
            row < 0
            or col < 0
            or row >= src.height
            or col >= src.width
        ):
            raise ValueError(
                f"Location is outside {path.name}"
            )

        nodata = src.nodata

        # Read only the required pixel
        pixel = src.read(
            1,
            window=rasterio.windows.Window(
                col,
                row,
                1,
                1
            )
        )

        value = float(pixel[0, 0])

        if (
            np.isfinite(value)
            and (
                nodata is None
                or not np.isclose(value, nodata)
            )
        ):
            return value

        # Search nearby pixels when exact pixel is NoData
        for radius in [1, 2, 4, 8, 16]:

            r0 = max(0, row - radius)
            c0 = max(0, col - radius)

            r1 = min(
                src.height,
                row + radius + 1
            )

            c1 = min(
                src.width,
                col + radius + 1
            )

            window = rasterio.windows.Window(
                c0,
                r0,
                c1 - c0,
                r1 - r0
            )

            values = src.read(
                1,
                window=window
            ).astype(float)

            values = values[
                np.isfinite(values)
            ]

            if nodata is not None:
                values = values[
                    ~np.isclose(
                        values,
                        nodata
                    )
                ]

            if values.size:
                return float(
                    np.median(values)
                )

    raise ValueError(
        f"No valid value found in {path.name} "
        f"at {latitude}, {longitude}"
    )

    return value


# ============================================================
# MODEL / EXPLAINABILITY
# ============================================================

def predict_soil(values):
    X = pd.DataFrame(
        [[values[f] for f in FEATURES]],
        columns=FEATURES
    )

    lgb_probs = np.asarray(
        lgb_model.predict_proba(X)
    )[0]

    cat_probs = np.asarray(
        cat_model.predict_proba(X)
    )[0]

    lgb_idx = int(np.argmax(lgb_probs))
    cat_idx = int(np.argmax(cat_probs))

    lgb_classes = list(
        getattr(lgb_model, "classes_", class_names)
    )

    cat_classes = list(
        getattr(cat_model, "classes_", class_names)
    )

    lgb_prediction = str(
        lgb_classes[lgb_idx]
    )

    cat_prediction = str(
        cat_classes[cat_idx]
    )

    lgb_confidence = float(
        lgb_probs[lgb_idx]
    )

    cat_confidence = float(
        cat_probs[cat_idx]
    )

    agreement = (
        lgb_prediction == cat_prediction
    )

    if agreement:
        fertility = lgb_prediction
        confidence = (
            lgb_confidence +
            cat_confidence
        ) / 2
    else:
        fertility = (
            lgb_prediction
            if lgb_confidence >= cat_confidence
            else cat_prediction
        )
        confidence = min(
            lgb_confidence,
            cat_confidence
        )

    result = {
        **values,
        "fertility": fertility,
        "confidence": float(confidence),
        "lgb_prediction": lgb_prediction,
        "cat_prediction": cat_prediction,
        "lgb_confidence": lgb_confidence,
        "cat_confidence": cat_confidence,
        "model_agreement": agreement,
        "timestamp": utc_now(),
    }

    return result, X


def explain(X, result):
    shap_items = []
    lime_items = []

    if shap_explainer is not None:
        try:
            sv = shap_explainer(X)
            vals = np.asarray(sv.values)

            if vals.ndim == 3:
                class_index = list(
                    lgb_model.classes_
                ).index(
                    result["lgb_prediction"]
                )
                vals = vals[0, :, class_index]
            else:
                vals = vals[0]

            for feature, value in zip(
                FEATURES,
                vals
            ):
                shap_items.append({
                    "feature": feature,
                    "value": float(value)
                })

            shap_items.sort(
                key=lambda x: abs(x["value"]),
                reverse=True
            )

        except Exception as exc:
            print("SHAP warning:", exc)

    if lime_explainer is not None:
        try:
            exp = lime_explainer.explain_instance(
                X.iloc[0].values,
                lambda array: lgb_model.predict_proba(
                    pd.DataFrame(
                        array,
                        columns=FEATURES
                    )
                ),
                num_features=len(FEATURES)
            )

            for feature, weight in exp.as_list():
                lime_items.append({
                    "feature": feature,
                    "weight": float(weight)
                })

        except Exception as exc:
            print("LIME warning:", exc)

    return {
        "shap": shap_items,
        "lime": lime_items
    }


# ============================================================
# CROP RECOMMENDATION
# ============================================================

def crop_advice(values, fertility):
    """Return a consistent crop recommendation object for the frontend."""

    # Prefer the project's advice_engine implementation when available.
    if advice_crop_advice is not None:
        try:
            result = advice_crop_advice(values, fertility)
            if isinstance(result, dict):
                return result
            if isinstance(result, list):
                return {
                    "fertility": str(fertility),
                    "summary": "Crop suitability is generated from the current soil and environmental conditions.",
                    "inputs": {k: values[k] for k in ("ph", "moisture", "temperature", "nitrogen", "cec")},
                    "recommendations": result,
                }
        except Exception as exc:
            print("Crop recommendation warning:", exc)

    if get_crop_recommendations is not None:
        try:
            result = get_crop_recommendations(
                ph=values["ph"],
                moisture=values["moisture"],
                nitrogen=values["nitrogen"],
                cec=values["cec"],
                temperature=values["temperature"],
                fertility=fertility
            )
            if isinstance(result, dict):
                return result
            if isinstance(result, list):
                return {
                    "fertility": str(fertility),
                    "summary": "Crop suitability is generated from the current soil and environmental conditions.",
                    "inputs": {k: values[k] for k in ("ph", "moisture", "temperature", "nitrogen", "cec")},
                    "recommendations": result,
                }
        except Exception as exc:
            print("Crop recommendation warning:", exc)

    rules = {
        "Rice": ((5.5, 7.5), (60, 90), (20, 35), "Rice generally suits warm conditions with relatively high soil moisture."),
        "Wheat": ((6.0, 7.5), (40, 70), (15, 25), "Wheat generally suits moderate moisture and cooler growing temperatures."),
        "Maize": ((5.8, 7.2), (45, 75), (18, 32), "Maize generally suits moderately moist soil and warm temperatures."),
        "Groundnut": ((5.5, 7.0), (35, 65), (20, 30), "Groundnut generally suits moderately moist soil and warm conditions."),
        "Millet": ((5.5, 7.5), (30, 60), (20, 35), "Millet can tolerate comparatively lower moisture conditions and warm temperatures."),
    }

    recommendations = []
    for crop, (ph_range, moisture_range, temp_range, reason) in rules.items():
        checks = {
            "pH": ph_range[0] <= values["ph"] <= ph_range[1],
            "Moisture": moisture_range[0] <= values["moisture"] <= moisture_range[1],
            "Temperature": temp_range[0] <= values["temperature"] <= temp_range[1],
        }
        matched = sum(checks.values())
        suitability = (
            "Suitable" if matched == 3 else
            "Moderately Suitable" if matched == 2 else
            "Less Suitable"
        )
        passed = [k for k, v in checks.items() if v]
        failed = [k for k, v in checks.items() if not v]
        explanation = reason
        if passed:
            explanation += " " + ", ".join(passed) + " conditions match the defined range."
        if failed:
            explanation += " " + ", ".join(failed) + " conditions are outside the defined range."
        explanation += (
            f" The ML fertility prediction is {fertility}. "
            f"Nitrogen={values['nitrogen']:.2f} and CEC={values['cec']:.2f} are also included in the soil assessment."
        )
        recommendations.append({
            "crop": crop,
            "suitability": suitability,
            "reason": explanation,
            "matched_conditions": matched,
            "total_conditions": 3,
            "conditions": checks,
        })

    priority = {"Suitable": 0, "Moderately Suitable": 1, "Less Suitable": 2}
    recommendations.sort(key=lambda item: (priority[item["suitability"]], -item["matched_conditions"]))

    return {
        "fertility": str(fertility),
        "summary": "Crop suitability is generated by a rule-based decision-support engine using the ML fertility prediction and soil/environment conditions.",
        "inputs": {k: values[k] for k in ("ph", "moisture", "temperature", "nitrogen", "cec")},
        "recommendations": recommendations,
    }


# ============================================================
# SAVE PREDICTION
# ============================================================

def save_prediction(result, explanation, crops, user_id):
    with DB_LOCK:
        conn = db()

        conn.execute(
            """
            INSERT INTO predictions (
                timestamp,
                user_id,
                latitude,
                longitude,
                input_mode,
                ph,
                moisture,
                temperature,
                nitrogen,
                cec,
                fertility,
                confidence,
                lgb_prediction,
                cat_prediction,
                lgb_confidence,
                cat_confidence,
                model_agreement,
                shap_data,
                lime_data,
                crop_recommendation
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["timestamp"],
                user_id,
                result["latitude"],
                result["longitude"],
                result.get("input_mode", "manual"),
                result["ph"],
                result["moisture"],
                result["temperature"],
                result["nitrogen"],
                result["cec"],
                result["fertility"],
                result["confidence"],
                result["lgb_prediction"],
                result["cat_prediction"],
                result["lgb_confidence"],
                result["cat_confidence"],
                int(result["model_agreement"]),
                json.dumps(
                    explanation.get("shap", [])
                ),
                json.dumps(
                    explanation.get("lime", [])
                ),
                json.dumps(crops)
            )
        )

        conn.commit()
        prediction_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()

    return prediction_id


# ============================================================
# AUTHENTICATION
# ============================================================

@app.route("/api/signup", methods=["POST"])
@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}

    name = str(data.get("farmer_name", data.get("name", ""))).strip()
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", data.get("contact", ""))).strip().lower()
    mobile = str(data.get("mobile", "")).strip()
    password = str(data.get("password", ""))

    if not name or not email or len(password) < 6:
        return jsonify({
            "success": False,
            "error": "Name, email and a password of at least 6 characters are required."
        }), 400

    with DB_LOCK:
        conn = db()
        try:
            if username:
                existing = conn.execute(
                    "SELECT id FROM users WHERE lower(email)=lower(?) OR username=?",
                    (email, username)
                ).fetchone()
            else:
                existing = conn.execute(
                    "SELECT id FROM users WHERE lower(email)=lower(?)",
                    (email,)
                ).fetchone()

            if existing is not None:
                return jsonify({
                    "success": False,
                    "error": "An account with this email or username already exists."
                }), 409

            cur = conn.execute(
                """
                INSERT INTO users (name, username, email, mobile, password_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, username or None, email, mobile or None, generate_password_hash(password))
            )
            user_id = cur.lastrowid
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            return jsonify({
                "success": False,
                "error": f"Could not create account: {exc}"
            }), 409
        finally:
            conn.close()

    session["user_id"] = user_id
    session["user_name"] = name
    session["username"] = username
    session["mobile"] = mobile

    return jsonify({
        "success": True,
        "message": "Farmer account created.",
        "user": {
            "id": user_id,
            "name": name,
            "farmer_name": name,
            "username": username,
            "email": email,
            "mobile": mobile
        }
    })


@app.route("/api/login", methods=["POST"])
@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    login_value = str(
        data.get("username") or data.get("email") or data.get("mobile") or data.get("contact") or ""
    ).strip()
    password = str(data.get("password", ""))

    if not login_value or not password:
        return jsonify({"success": False, "error": "Username/email/mobile and password are required."}), 400

    with DB_LOCK:
        conn = db()
        row = conn.execute(
            """
            SELECT id, name, username, email, mobile, password_hash
            FROM users
            WHERE lower(email)=lower(?) OR lower(username)=lower(?) OR mobile=?
            LIMIT 1
            """,
            (login_value, login_value, login_value)
        ).fetchone()
        conn.close()

    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({
            "success": False,
            "error": "Invalid username/email/mobile or password."
        }), 401

    session["user_id"] = row["id"]
    session["user_name"] = row["name"]
    session["username"] = row["username"] or ""
    session["mobile"] = row["mobile"] or ""

    user_payload = {
        "id": row["id"],
        "name": row["name"],
        "farmer_name": row["name"],
        "username": row["username"] or "",
        "email": row["email"],
        "mobile": row["mobile"] or ""
    }

    return jsonify({
        "success": True,
        "message": "Login successful.",
        "user": user_payload,
        "farmer": user_payload
    })


@app.route("/api/logout", methods=["POST"])
@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out."
    })


@app.route("/api/me")
@app.route("/api/auth/me")
def me():
    user = current_user()

    if user is None:
        return jsonify({
            "authenticated": False,
            "logged_in": False
        })

    return jsonify({
        "authenticated": True,
        "logged_in": True,
        "user": dict(user),
        "farmer": {
            "id": user["id"],
            "farmer_name": user["name"],
            "email": user["email"]
        }
    })


# ============================================================
# LOCATION
# ============================================================

@app.route("/api/location", methods=["GET", "POST"])
def location():
    if request.method == "GET":
        return jsonify({
            "success": True,
            "location": get_location()
        })

    data = request.get_json(
        silent=True
    ) or {}

    try:
        latitude = number(
            data,
            "latitude",
            -90,
            90
        )

        longitude = number(
            data,
            "longitude",
            -180,
            180
        )

        saved = save_location(
            latitude,
            longitude,
            data.get("source", "browser")
        )

        return jsonify({
            "success": True,
            "location": saved
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400


# ============================================================
# BACKGROUND EXPLANATION
# ============================================================

def finish_explanation(prediction_id, X, result):
    """Compute SHAP/LIME after the fast prediction response is sent."""
    try:
        explanation = explain(X, result)
        with DB_LOCK:
            conn = db()
            conn.execute(
                """
                UPDATE predictions
                SET shap_data = ?, lime_data = ?
                WHERE id = ?
                """,
                (
                    json.dumps(explanation.get("shap", [])),
                    json.dumps(explanation.get("lime", [])),
                    prediction_id,
                )
            )
            conn.commit()
            conn.close()
        print(f"XAI explanation ready for prediction {prediction_id}")
    except Exception as exc:
        print(f"Background XAI warning for prediction {prediction_id}: {exc}")


# ============================================================
# PREDICTION
# ============================================================

@app.route("/api/predict", methods=["POST"])
def predict():
    user, error = login_required()

    if error:
        return error

    data = request.get_json(
        silent=True
    ) or {}

    try:
        input_mode = str(
            data.get(
                "input_mode",
                "manual"
            )
        ).lower()

        latitude = number(
            data,
            "latitude",
            -90,
            90
        )

        longitude = number(
            data,
            "longitude",
            -180,
            180
        )

        # Live IoT mode uses the latest Arduino pH, moisture and temperature.
        if input_mode in {"iot", "sensor", "live"}:
            with sensor_lock:
                live = dict(sensor_data)

            if not live.get("connected"):
                raise ValueError("Arduino sensor is not connected.")

            ph = number(live, "ph", 0, 14)
            moisture = number(live, "moisture", 0, 100)
            temperature = number(live, "temperature", -50, 70)
        else:
            ph = number(data, "ph", 0, 14)
            moisture = number(data, "moisture", 0, 100)
            temperature = number(data, "temperature", -50, 70)

        # Nitrogen and CEC remain location-derived.
        nitrogen = raster_value(
            RASTER_FILES["nitrogen"],
            latitude,
            longitude
        )

        cec = raster_value(
            RASTER_FILES["cec"],
            latitude,
            longitude
        )

        values = {
            "latitude": latitude,
            "longitude": longitude,
            "ph": ph,
            "moisture": moisture,
            "temperature": temperature,
            "nitrogen": nitrogen,
            "cec": cec,
            "input_mode": input_mode
        }

        # Fast path: run the two ML models first.
        result, X = predict_soil(values)

        # Crop rules are lightweight, so keep them in the immediate response.
        crops = crop_advice(
            values,
            result["fertility"]
        )

        # Save immediately; SHAP/LIME are calculated in the background.
        prediction_id = save_prediction(
            result,
            {"shap": [], "lime": []},
            crops,
            user["id"]
        )

        threading.Thread(
            target=finish_explanation,
            args=(prediction_id, X, result),
            daemon=True
        ).start()

        return jsonify({
            "success": True,
            "prediction_id": prediction_id,
            "fertility": result["fertility"],
            "confidence": result["confidence"],
            "input_mode": input_mode,
            "soil": {
                "latitude": latitude,
                "longitude": longitude,
                "ph": ph,
                "moisture": moisture,
                "temperature": temperature,
                "nitrogen": nitrogen,
                "cec": cec
            },
            "models": {
                "lightgbm": {
                    "prediction": result["lgb_prediction"],
                    "confidence": result["lgb_confidence"]
                },
                "catboost": {
                    "prediction": result["cat_prediction"],
                    "confidence": result["cat_confidence"]
                },
                "agreement": result["model_agreement"]
            },
            "shap": [],
            "lime": [],
            "crops": crops,
            "timestamp": result["timestamp"]
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400

    except Exception as exc:
        print("Prediction error:", exc)

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500


# ============================================================
# ARDUINO SENSOR
# ============================================================

sensor_data = {
    "connected": False,
    "ph": None,
    "moisture": None,
    "temperature": None,
    "timestamp": None,
    "error": "Waiting for Arduino."
}

sensor_lock = threading.Lock()

def sensor_reader():
    try:
        import serial
    except ImportError:
        with sensor_lock:
            sensor_data["error"] = "pyserial is not installed."
        return

    port = getattr(config, "SERIAL_PORT", "COM3")
    baud = int(getattr(config, "SERIAL_BAUD", 9600))

    while True:
        ser = None
        try:
            ser = serial.Serial(port, baud, timeout=2)
            time.sleep(2)
            print(f"Arduino connected on {port} at {baud} baud")

            with sensor_lock:
                sensor_data["connected"] = True
                sensor_data["error"] = None

            while True:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                if line.startswith("SOIL_SENSOR_READY") or line.startswith("DEBUG"):
                    print("[ARDUINO]", line)
                    continue

                parts = [item.strip() for item in line.split(",")]

                try:
                    if len(parts) == 3:
                        # NEW FORMAT: pH,moisture,temperature
                        ph = float(parts[0])
                        moisture = float(parts[1])
                        temperature = float(parts[2])

                        if not (0 <= ph <= 14 and 0 <= moisture <= 100 and -50 <= temperature <= 70):
                            continue
                        with sensor_lock:
                            sensor_data["ph"] = ph
                            sensor_data["moisture"] = moisture
                            sensor_data["temperature"] = temperature
                            sensor_data["timestamp"] = utc_now()
                            sensor_data["connected"] = True
                            sensor_data["error"] = None
                        print(f"[ARDUINO] pH={ph:.2f}, Moisture={moisture:.2f}%, Temperature={temperature:.2f} C")
                    elif len(parts) == 2:
                        # OLD FORMAT: moisture,temperature
                        moisture = float(parts[0])
                        temperature = float(parts[1])
                        if not (0 <= moisture <= 100 and -50 <= temperature <= 70):
                            continue
                        with sensor_lock:
                            sensor_data["moisture"] = moisture
                            sensor_data["temperature"] = temperature
                            sensor_data["timestamp"] = utc_now()
                            sensor_data["connected"] = True
                            sensor_data["error"] = "pH not received from Arduino yet."
                except ValueError:
                    continue
        except Exception as exc:
            with sensor_lock:
                sensor_data["connected"] = False
                sensor_data["error"] = f"Arduino unavailable on {port}: {exc}"
            time.sleep(3)
        finally:
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass


threading.Thread(
    target=sensor_reader,
    daemon=True
).start()


@app.route("/api/latest")
def latest():
    with sensor_lock:
        result = dict(sensor_data)

    result["logged_in"] = current_user() is not None
    return jsonify(result)


@app.route("/api/sensor", methods=["POST"])
def save_sensor():
    user, error = login_required()

    if error:
        return error

    data = request.get_json(
        silent=True
    ) or {}

    try:
        ph = data.get("ph")
        if ph is not None and ph != "":
            ph = number(data, "ph", 0, 14)

        moisture = number(
            data,
            "moisture",
            0,
            100
        )

        temperature = number(
            data,
            "temperature",
            -50,
            70
        )

        timestamp = utc_now()

        with DB_LOCK:
            conn = db()

            conn.execute(
                """
                INSERT INTO sensor_readings (
                    user_id,
                    timestamp,
                    ph,
                    moisture,
                    temperature
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user["id"],
                    timestamp,
                    ph,
                    moisture,
                    temperature
                )
            )

            conn.commit()
            conn.close()

        return jsonify({
            "success": True,
            "timestamp": timestamp
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400


# ============================================================
# PREDICTION EXPLANATION
# ============================================================

@app.route("/api/prediction/<int:prediction_id>/explanation")
def prediction_explanation(prediction_id):
    user, error = login_required()
    if error:
        return error

    with DB_LOCK:
        conn = db()
        row = conn.execute(
            """
            SELECT shap_data, lime_data
            FROM predictions
            WHERE id = ? AND user_id = ?
            """,
            (prediction_id, user["id"]),
        ).fetchone()
        conn.close()

    if row is None:
        return jsonify({"success": False, "error": "Prediction not found."}), 404

    shap = json.loads(row["shap_data"] or "[]")
    lime = json.loads(row["lime_data"] or "[]")
    return jsonify({
        "success": True,
        "ready": bool(shap or lime),
        "shap": shap,
        "lime": lime,
    })


# ============================================================
# HISTORY
# ============================================================

@app.route("/api/history")
def history():
    user, error = login_required()

    if error:
        return error

    with DB_LOCK:
        conn = db()

        rows = conn.execute(
            """
            SELECT
                id,
                timestamp,
                latitude,
                longitude,
                input_mode,
                ph,
                moisture,
                temperature,
                nitrogen,
                cec,
                fertility,
                confidence,
                lgb_prediction,
                cat_prediction,
                lgb_confidence,
                cat_confidence,
                model_agreement,
                shap_data,
                lime_data,
                crop_recommendation
            FROM predictions
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 100
            """,
            (user["id"],)
        ).fetchall()

        conn.close()

    output = []

    for row in rows:
        item = dict(row)

        item["shap"] = json.loads(
            item.pop("shap_data") or "[]"
        )

        item["lime"] = json.loads(
            item.pop("lime_data") or "[]"
        )

        item["crops"] = json.loads(
            item.pop("crop_recommendation") or "{}"
        )

        output.append(item)

    return jsonify({
        "success": True,
        "history": output
    })


# ============================================================
# ANALYTICS
# ============================================================

@app.route("/api/analytics")
def analytics():
    user, error = login_required()

    if error:
        return error

    with DB_LOCK:
        conn = db()

        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                AVG(confidence) AS avg_confidence,
                AVG(temperature) AS avg_temperature,
                AVG(moisture) AS avg_moisture,
                AVG(ph) AS avg_ph
            FROM predictions
            WHERE user_id = ?
            """,
            (user["id"],)
        ).fetchone()

        distribution = conn.execute(
            """
            SELECT fertility, COUNT(*) AS count
            FROM predictions
            WHERE user_id = ?
            GROUP BY fertility
            """,
            (user["id"],)
        ).fetchall()

        conn.close()

    return jsonify({
        "success": True,
        "total_predictions": totals["total"] or 0,
        "average_confidence": totals["avg_confidence"] or 0,
        "average_temperature": totals["avg_temperature"] or 0,
        "average_moisture": totals["avg_moisture"] or 0,
        "average_ph": totals["avg_ph"] or 0,
        "distribution": [
            {
                "fertility": row["fertility"],
                "count": row["count"]
            }
            for row in distribution
        ],
        "fertility_distribution": [
            {
                "fertility": row["fertility"],
                "count": row["count"]
            }
            for row in distribution
        ]
    })


# ============================================================
# WEATHER
# ============================================================

@app.route("/api/weather")
def weather():
    try:
        latitude = float(
            request.args.get("latitude")
        )

        longitude = float(
            request.args.get("longitude")
        )

        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,"
                    "relative_humidity_2m,"
                    "precipitation,"
                    "wind_speed_10m"
                ),
                "timezone": "auto"
            },
            timeout=10
        )

        response.raise_for_status()

        return jsonify({
            "success": True,
            "weather": response.json()
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": str(exc)
        }), 503


# ============================================================
# HEALTH / STATUS
# ============================================================

@app.route("/api/health")
def health():
    with sensor_lock:
        connected = sensor_data["connected"]

    return jsonify({
        "status": "online",
        "database": DB_FILE.exists(),
        "models_loaded": True,
        "temperature_models": True,
        "features": feature_names,
        "arduino_connected": connected,
        "shap_available": shap_explainer is not None,
        "lime_available": lime_explainer is not None,
        "real_data_only": True
    })


@app.route("/api/status")
def status():
    with sensor_lock:
        connected = sensor_data["connected"]

    return jsonify({
        "models_loaded": True,
        "temperature_models": True,
        "features": FEATURES,
        "arduino_connected": connected,
        "shap_available": shap_explainer is not None,
        "lime_available": lime_explainer is not None
    })


# ============================================================
# FRONTEND
# ============================================================

@app.route("/")
def index():
    return send_from_directory(
        str(ROOT_DIR / "frontend"),
        "index.html"
    )


@app.route("/<path:path>")
def frontend_files(path):
    file_path = ROOT_DIR / "frontend" / path

    if file_path.is_file():
        return send_from_directory(
            str(ROOT_DIR / "frontend"),
            path
        )

    return send_from_directory(
        str(ROOT_DIR / "frontend"),
        "index.html"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    host = getattr(
        config,
        "FLASK_HOST",
        "127.0.0.1"
    )

    port = int(
        getattr(
            config,
            "FLASK_PORT",
            5000
        )
    )

    print()
    print("=" * 70)
    print("SOILAI SERVER")
    print("=" * 70)
    print("Database:", DB_FILE)
    print("Features:", FEATURES)
    print("Temperature models: loaded")
    print(f"Open: http://localhost:{port}")
    print("=" * 70)

    app.run(
        host=host,
        port=port,
        debug=False,
        use_reloader=False
    )
