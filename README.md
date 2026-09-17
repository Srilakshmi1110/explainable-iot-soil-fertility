# 🌱 Explainable IoT Soil Fertility Prediction System

> **Sense the soil. Understand the prediction. Grow smarter.**

An **IoT + Machine Learning + Explainable AI** system that analyzes soil conditions, predicts soil fertility, explains the prediction, and provides crop recommendations.

---

## 🌾 Overview

The system combines **real-time IoT sensor readings**, **geospatial soil data**, **machine learning models**, and **Explainable AI** to perform soil fertility analysis.

The system collects real-time **pH, moisture, and temperature** from Arduino sensors. Location-based **nitrogen and CEC** values are obtained from geospatial soil datasets. These values are combined into a **7-feature input vector** and passed to LightGBM and CatBoost models.

The prediction is then explained using **SHAP and LIME**, followed by a **crop recommendation** based on soil conditions.

---

## ⚡ Key Features

**🌡️ Real-Time Soil Monitoring**
Measures pH, moisture, and temperature using Arduino sensors.

**📍 Location-Based Soil Analysis**
Extracts nitrogen and CEC values from geospatial soil datasets based on the selected location.

**🤖 Dual Machine Learning Prediction**
Uses LightGBM and CatBoost to classify soil fertility as High, Medium, or Low.

**🔍 Explainable AI**
Uses SHAP and LIME to show the contribution of individual features to the prediction.

**🌾 Crop Recommendation**
Provides crop recommendations based on the available soil characteristics.

**📊 Analytics Dashboard**
Displays fertility distribution, prediction statistics, and sensor history.

**🔐 User Authentication**
Provides login-based access and stores user predictions.

**💾 Prediction History**
Stores previous predictions and soil readings using SQLite.

---

## 🧠 System Workflow

```text
        ┌──────────────────────────┐
        │      Arduino Sensors     │
        │  pH | Moisture | Temp.   │
        └────────────┬─────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │      Location Input      │
        │   Latitude + Longitude   │
        └────────────┬─────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │    Geospatial Soil Data  │
        │     Nitrogen + CEC       │
        └────────────┬─────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │     7-Feature Vector     │
        │ Lat, Lon, pH, Moisture,  │
        │ Temp, Nitrogen, CEC      │
        └────────────┬─────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │   LightGBM + CatBoost    │
        │   Fertility Prediction   │
        └────────────┬─────────────┘
                     │
             ┌───────┴────────┐
             ▼                ▼
       ┌───────────┐    ┌──────────────┐
       │ SHAP +    │    │     Crop     │
       │ LIME      │    │Recommendation│
       └─────┬─────┘    └──────┬───────┘
             │                  │
             └────────┬─────────┘
                      ▼
             ┌─────────────────┐
             │ Web Dashboard   │
             └─────────────────┘
```

---

## 🔬 Machine Learning Models

### LightGBM

LightGBM is used as one of the primary gradient boosting classifiers for soil fertility prediction.

### CatBoost

CatBoost is used as the second classifier. Its prediction is compared with LightGBM to determine **model agreement and confidence**.

The models classify soil into:

```text
High
Medium
Low
```

The final dashboard displays the predictions and confidence obtained from the trained models.

---

## 🧩 Explainable AI

The system does not only provide a fertility class. It also explains **which input features influenced the prediction**.

### SHAP

**SHAP (SHapley Additive exPlanations)** is used to determine the contribution of individual features to the model prediction.

### LIME

**LIME (Local Interpretable Model-Agnostic Explanations)** provides a local explanation for an individual prediction.

Together, SHAP and LIME make the prediction more interpretable.

---

## 🌾 Crop Recommendation

The system provides crop recommendations after soil fertility prediction.

Currently supported crops include:

```text
Rice
Wheat
Maize
Groundnut
Millet
```

Recommendations are generated using available soil characteristics such as:

```text
pH
Moisture
Nitrogen
CEC
```

---

# 📡 IoT Sensor Layer

The Arduino provides real-time soil measurements.

```text
pH          → A1
Moisture    → A0
Temperature → A2
```

The 10K thermistor is used for temperature measurement.

Example serial output:

```text
6.50,65.00,25.00
```

This represents:

```text
pH          = 6.50
Moisture    = 65%
Temperature = 25°C
```

The readings are sent to the Flask backend through the serial connection.

---

# 📂 Datasets Used

## 1. Soil Dataset — `soil_data.csv`

The primary soil dataset contains **12,748 samples** with the following attributes:

```text
Latitude
Longitude
pH
Moisture
Nitrogen
CEC
```

The dataset is used for soil fertility model development.

The fertility classes used by the system are:

```text
High
Medium
Low
```

The fertility labels are derived from soil-property criteria used during model development.

### Important Coordinate Note

The latitude and longitude columns in the original dataset contain **projected spatial coordinates**, rather than standard decimal-degree latitude and longitude.

The backend transforms these coordinates when geographic coordinates are required.

---

## 2. Geospatial Soil Raster Datasets

The project uses GeoTIFF raster datasets for location-based soil information:

```text
ph.tif
nitrogen.tif
cec.tif
```

When a user selects a location, the backend converts the geographic coordinates into the raster coordinate system and extracts the corresponding soil-property value.

If the selected pixel contains a **NoData value**, the system searches nearby pixels for a valid value.

This allows the system to obtain:

```text
Location
   ↓
GeoTIFF
   ↓
Nitrogen + CEC + pH
```

---

## 3. Temperature Dataset

The temperature-enhanced model uses:

```text
soil_temperature.csv
soil_training_temperature.csv
```

These datasets contain the training data used for the model that includes **temperature as an additional feature**.

The final model uses seven features:

```text
Latitude
Longitude
pH
Moisture
Temperature
Nitrogen
CEC
```

---

## 4. Real-Time IoT Data

Real-time sensor readings are **not a static dataset**.

They are generated directly from the Arduino:

```text
pH          → pH Sensor
Moisture    → Soil Moisture Sensor
Temperature → 10K Thermistor
```

These real-time measurements are combined with location-based soil information before sending the data to the prediction models.

---

# 🔌 APIs Used

## Flask REST API

The Flask backend provides REST API endpoints that connect the frontend dashboard with the prediction system.

| Endpoint         | Purpose                                  |
| ---------------- | ---------------------------------------- |
| `/api/login`     | User authentication                      |
| `/api/location`  | Store and retrieve selected location     |
| `/api/latest`    | Retrieve latest IoT sensor readings      |
| `/api/predict`   | Perform soil fertility prediction        |
| `/api/analytics` | Retrieve prediction and sensor analytics |
| `/api/advice`    | Generate crop recommendations            |

The frontend communicates with these endpoints using JavaScript `fetch()` requests.

---

## 🌤️ Open-Meteo Weather API

The system also uses the **Open-Meteo Weather API** to obtain weather information for the selected location.

Weather information provides additional environmental context through parameters such as:

```text
Temperature
Humidity
Rainfall
Weather Conditions
```

Weather data is displayed separately from the soil fertility prediction pipeline.

---

# 🖥️ Technology Stack

### Hardware

```text
Arduino
Soil pH Sensor
Soil Moisture Sensor
10K Thermistor
```

### Backend

```text
Python
Flask
SQLite
Rasterio
PyProj
Requests
```

### Machine Learning

```text
LightGBM
CatBoost
Scikit-learn
```

### Explainable AI

```text
SHAP
LIME
```

### Frontend

```text
HTML
CSS
JavaScript
Chart.js
```

---

# 📁 Project Structure

```text
soil_project_complete/
│
├── arduino/
│   └── sensor_reader.ino
│
├── backend/
│   ├── app.py
│   ├── advice_engine.py
│   │
│   ├── data/
│   │   ├── soil_data.csv
│   │   ├── soil_training.csv
│   │   ├── soil_temperature.csv
│   │   ├── soil_training_temperature.csv
│   │   ├── train_temperature_models.py
│   │   ├── ph.tif
│   │   ├── nitrogen.tif
│   │   └── cec.tif
│   │
│   └── models/
│       ├── lgb_model.joblib
│       ├── cat_model.joblib
│       ├── feature_names.joblib
│       ├── class_names.joblib
│       ├── background_data.joblib
│       ├── lgb_model_temperature.joblib
│       ├── cat_model_temperature.joblib
│       ├── feature_names_temperature.joblib
│       ├── class_names_temperature.joblib
│       ├── background_data_temperature.joblib
│       └── temperature_model_metrics.joblib
│
├── frontend/
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
│
├── config.py
├── requirements.txt
└── README.md
```

---

# 🚀 Installation & Setup

## 1. Clone the Repository

```bash
git clone https://github.com/Srilakshmi1110/explainable-iot-soil-fertility.git
cd explainable-iot-soil-fertility
```

## 2. Create a Virtual Environment

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure Arduino

Update the serial port in `config.py`:

```python
SERIAL_PORT = "COM3"
SERIAL_BAUD = 9600
```

Upload:

```text
arduino/sensor_reader.ino
```

to the Arduino.

## 5. Start the Application

```bash
python backend/app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

# 🎯 Model Input

The final prediction model uses seven features:

```text
[Latitude,
 Longitude,
 pH,
 Moisture,
 Temperature,
 Nitrogen,
 CEC]
```

Example:

```text
Latitude    = 13.068198
Longitude   = 77.503880
pH          = 6.5
Moisture    = 65%
Temperature = 25°C
Nitrogen    = 174
CEC         = 140
```

The system produces:

```text
Fertility Prediction
        ↓
Model Confidence
        ↓
Model Agreement
        ↓
SHAP + LIME Explanation
        ↓
Crop Recommendation
```

---

# 📊 Dashboard

The dashboard provides a unified view of soil analysis.

### 🌡️ Sensor Monitoring

Displays real-time:

```text
pH
Moisture
Temperature
```

### 🧪 Soil Properties

Displays location-based:

```text
Nitrogen
CEC
```

### 🤖 Fertility Prediction

Shows:

```text
LightGBM Prediction
CatBoost Prediction
Confidence
Model Agreement
```

### 🔍 Explainability

Displays feature contributions using:

```text
SHAP
LIME
```

### 🌾 Crop Recommendation

Displays suitable crops based on soil conditions.

### 📈 Analytics

Displays:

```text
Total Predictions
High Fertility
Medium Fertility
Low Fertility
Moisture History
Temperature History
```

---

# 🔮 Future Scope

**• Integrate additional soil nutrients such as phosphorus, potassium, and organic carbon for more comprehensive soil analysis.**

**• Expand geospatial soil datasets to cover more regions and provide more location-specific predictions.**

**• Develop a cloud/mobile platform for long-term soil tracking and personalized agricultural recommendations.**

---

# 👩‍💻 Project Summary

This project integrates **IoT, geospatial data, machine learning, and explainable AI** into a single soil analysis platform.

The system moves beyond simply predicting soil fertility by providing:

```text
Measure → Predict → Explain → Recommend
```

> 🌱 **Smarter soil insights for smarter agricultural decisions.**
