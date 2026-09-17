# SoilAI - Explainable IoT Framework for Soil Fertility Prediction

An intelligent, transparent soil monitoring system combining real-time Arduino IoT sensors with explainable machine learning to deliver accurate soil fertility predictions for smart farming.

**GitHub:** https://github.com/Srilakshmi1110/explainable-iot-soil-fertility

---

## 🌱 **Overview**

SoilAI integrates hardware sensors (pH, moisture, temperature), geospatial data, and interpretable ML models (LightGBM, CatBoost) to predict soil fertility with 97.5% accuracy. SHAP and LIME explanations ensure farmers understand *why* predictions are made, not just what they are.

---

## ✨ **Key Features**

- **Real-Time Monitoring** — Arduino sensors capture pH, moisture, and temperature every 2 seconds
- **Explainable Predictions** — SHAP feature importance and LIME rules show which soil factors drive fertility scores
- **Multi-Crop Recommendations** — Rule-based engine suggests suitable crops based on soil conditions
- **Prediction History** — Track 24+ hours of readings with geospatial coordinates (GPS)
- **Model Comparison** — Independent predictions from LightGBM (100% confidence) and CatBoost (99.5% confidence)
- **Secure Login** — Farmer authentication with session persistence
- **Responsive Dashboard** — Real-time charts for moisture and temperature trends
- **System Status** — Live indicators for model, database, and sensor connectivity

---

## 🏗️ **Architecture**

```
Hardware (Arduino)
    ↓
Flask REST API (Python)
    ↓
SQLite Database
    ├─ sensor_readings
    ├─ predictions
    ├─ shap_explanations
    ├─ lime_explanations
    └─ system_logs
    ↓
React Dashboard (Frontend)
    ├─ Overview (real-time sensor values)
    ├─ Analytics (trend charts)
    ├─ Explainability (SHAP/LIME)
    └─ Crop Recommendations
```

---

## 🚀 **Quick Start**

### Prerequisites
- Python 3.10+
- Arduino with sensors (pH module on A0, moisture on A1)
- USB connection to laptop

### Installation

```bash
# Clone repository
git clone https://github.com/Srilakshmi1110/explainable-iot-soil-fertility.git
cd soil-fertility-iot

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Initialize database
python database_setup.py

# Train models (optional; pre-trained models included)
python backend/train_model.py
```

### Run the System

```bash
# Start Flask server
python backend/app.py

# Open browser
# http://localhost:5000

# Login with:
# Username: admin
# Password: 123456
```

---

## 📊 **Dashboard Tabs**

| Tab | Purpose |
|-----|---------|
| **Overview** | Real-time pH, moisture, temperature + LightGBM/CatBoost predictions |
| **Analytics** | 24h sensor trends, total predictions, model agreement rate |
| **Explainability** | SHAP feature bars + LIME decision rules for each prediction |
| **Crop Recommendations** | Rule-based engine ranks crops by soil suitability (3 rules: pH, moisture, temperature) |

---

## 🔌 **Arduino Setup**

```
pH Sensor:        Moisture Sensor:
RED → 5V          RED → 5V
BLACK → GND       BLACK → GND
YELLOW → A0       YELLOW → A1

Baud Rate: 9600
Output Format: "6.80,42.30" (pH, Moisture)
```

**For demo without Arduino:** Set `SIMULATE_ARDUINO = True` in `config.py`

---

## 📁 **Project Structure**

```
soil-fertility-iot/
├── backend/
│   ├── app.py                 # Flask server + API endpoints
│   ├── train_model.py         # LightGBM/CatBoost training
│   ├── data/
│   │   ├── soil_data.csv      # Training dataset (geospatial)
│   │   └── predictions.db     # SQLite database (auto-created)
│   └── models/
│       ├── lgb_model.joblib
│       └── cat_model.joblib
├── frontend/
│   └── index.html             # Single-page React dashboard
├── arduino/
│   └── sensor_reader.ino      # Arduino sketch
├── config.py                  # Configuration (serial port, baud rate, etc.)
├── database_setup.py          # Database schema + helper functions
├── requirements.txt           # Python dependencies
└── README.md
```

---

## 🔌 **API Endpoints**

| Endpoint | Returns |
|----------|---------|
| `GET /` | Dashboard HTML |
| `GET /api/latest` | Current reading + prediction + SHAP/LIME |
| `GET /api/analytics` | Total predictions, agreement rate, avg confidence |
| `GET /api/status` | Model status, database ready, serial connected |
| `GET /api/history` | Last 24h predictions (100 max) |
| `GET /api/export` | All data as JSON |

---

## 📊 **Dataset**

**Source:** Geospatial soil fertility dataset with real-world agricultural observations

**Features Used:**
- pH (soil acidity/alkalinity)
- Moisture (% soil water content)
- Temperature (°C, from Arduino sensors)
- Nitrogen (N, available nitrogen in soil)
- CEC (Cation Exchange Capacity)
- Latitude & Longitude (geospatial coordinates for field location)

**Dataset Size:** 2000+ samples from diverse agricultural regions

**Data Splits:**
- Training: 80% (1600 samples)
- Testing: 20% (400 samples)

**Preprocessing:**
- Feature scaling (StandardScaler)
- Missing value handling
- Outlier detection and removal

---

## 📊 **Model Performance**

| Model | Accuracy | Confidence | Algorithm |
|-------|----------|-----------|-----------|
| LightGBM | 97.5% | 100.0% | Gradient Boosting |
| CatBoost | 97.2% | 99.5% | Categorical Boosting |

**Input Features:** pH, Moisture, Temperature, Nitrogen, CEC, Latitude, Longitude

**Output:** Soil Fertility Classification (Low / Medium / High)

---

## 🎯 **Login Credentials** (Demo)

```
admin / 123456
sri / 123456
user / password
```

---

## 🌾 **Conclusion**

SoilAI delivers explainable soil fertility predictions at 97.5% accuracy by integrating Arduino IoT sensors with LightGBM and SHAP/LIME transparency, enabling transparent, data-driven farming decisions.

---

## 🚀 **Future Work**

1. **Edge deployment on Raspberry Pi** — Enable offline predictions in low-connectivity farm areas
2. **Predictive recommendation engine** — Forecast optimal irrigation timing based on weather + soil trends
3. **SMS/WhatsApp alerts** — Notify farmers via text when soil fertility drops or crop conditions worsen
4. **Soil anomaly detection** — Identify sensor failures or sudden soil degradation automatically

---

## 📄 **License**

Educational Project | Sapthagiri College of Engineering, Bengaluru

---

## 👥 **Team**

- Prabhudeva BN (1SG23CS078)
- Shreya Praveen Ramadurg (1SG23CS101)
- **Srilakshmi Seshadri (1SG23CS110)**
- Sharath MR (1SG24CS410)

**Guide:** Prof. Sheela Rani C M

---

## 🔗 **Resources**

- [LightGBM Docs](https://lightgbm.readthedocs.io/)
- [SHAP GitHub](https://github.com/slundberg/shap)
- [LIME GitHub](https://github.com/marcotcr/lime)
- [Flask Documentation](https://flask.palletsprojects.com/)

---

**Questions?** Open an issue on GitHub!

🌱 *Smart Farming Starts with Smart Data*
