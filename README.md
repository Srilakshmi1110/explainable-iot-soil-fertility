# Explainable IoT Framework for Soil Fertility Prediction

An IoT and machine-learning based system for real-time soil fertility prediction using soil sensor readings, geospatial soil data, explainable AI, weather information, and crop recommendations.

## 🌱 Project Overview

The **Explainable IoT Framework for Soil Fertility Prediction** combines real-time soil sensing with machine learning to provide an interpretable assessment of soil fertility.

The system collects:

- Real-time soil pH from an Arduino-connected pH sensor
- Real-time soil moisture from an Arduino-connected moisture sensor
- Latitude and longitude from the selected field location
- Nitrogen (N) and Cation Exchange Capacity (CEC) from geospatial soil raster data
- Weather information from an external weather data service

These inputs are processed by trained **LightGBM** and **CatBoost** models to predict soil fertility.

The system also provides **SHAP and LIME explanations** to show which soil features influence the prediction.

---

## 🎯 Objectives

- Collect real-time soil measurements using IoT sensors
- Combine sensor measurements with geospatial soil information
- Predict soil fertility using machine-learning models
- Compare predictions from LightGBM and CatBoost
- Provide model confidence and model-agreement information
- Explain predictions using SHAP and LIME
- Provide crop recommendations based on available soil conditions
- Display historical predictions and analytics
- Provide real-time weather information
- Maintain a real-data-only workflow without simulated sensor readings

---

## 🏗️ System Architecture

```text
                 ┌──────────────────────┐
                 │   Arduino + Sensors  │
                 │                      │
                 │  pH + Soil Moisture  │
                 └──────────┬───────────┘
                            │
                       Serial USB
                            │
                            ▼
                 ┌──────────────────────┐
                 │    Flask Backend     │
                 └──────────┬───────────┘
                            │
             ┌──────────────┼──────────────┐
             │              │              │
             ▼              ▼              ▼
       Field Location   Soil Raster     Weather API
       Lat / Longitude  Data (N, CEC)   Weather Data
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                 ┌──────────────────────┐
                 │   Feature Assembly   │
                 │                      │
                 │ lat, lon, pH,        │
                 │ moisture, N, CEC     │
                 └──────────┬───────────┘
                            │
                            ▼
                ┌────────────────────────┐
                │    ML Prediction       │
                │                        │
                │ LightGBM + CatBoost    │
                └────────────┬───────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
          Fertility       SHAP/LIME     Crop
          Prediction      Explanation   Recommendation
              │
              ▼
       ┌───────────────────┐
       │   SoilAI Dashboard │
       │                   │
       │ Analytics         │
       │ Explainability    │
       │ History           │
       │ Weather           │
       │ Crop Suggestions  │
       └───────────────────┘

🔬 Machine Learning

The system uses two classification models:

LightGBM

LightGBM is used as the primary machine-learning model for soil fertility classification.

CatBoost

CatBoost provides a second independent prediction which is used for model comparison and agreement analysis.

The system compares both predictions and reports:

LightGBM prediction
CatBoost prediction
Individual model confidence
Model agreement
Final fertility classification
Combined confidence
Fertility Classes

The current model predicts three fertility classes:

Low
Medium
High

The current training labels were derived from the available soil-property dataset using defined classification criteria. They should not be interpreted as independently measured ground-truth fertility labels.

📊 Model Features

The trained models use six features:

1. Latitude
2. Longitude
3. pH
4. Moisture
5. Nitrogen
6. CEC
Data Sources
Feature	Source
Latitude	Field/browser location
Longitude	Field/browser location
pH	Arduino pH sensor
Moisture	Arduino soil-moisture sensor
Nitrogen	Geospatial soil raster data
CEC	Geospatial soil raster data

N and CEC do not require additional sensors in the current system.

🤖 IoT Integration

The Arduino communicates with the Flask backend through a serial USB connection.

The expected Arduino output format is:

pH,moisture

Example:

6.42,48.7
6.45,49.1
6.43,48.9

Where:

6.42 = soil pH
48.7 = soil moisture percentage

The backend validates incoming sensor readings before using them for prediction.

If the Arduino is disconnected, the system does not generate simulated sensor values. Instead, the dashboard displays a waiting/disconnected state.

🧠 Explainable AI

The framework provides two explainability methods.

SHAP

SHAP (SHapley Additive exPlanations) shows the contribution of individual features to the model prediction.

The system analyzes:

Latitude
Longitude
pH
Moisture
Nitrogen
CEC
LIME

LIME (Local Interpretable Model-agnostic Explanations) provides a local explanation for an individual prediction.

Both explanations are generated from the actual prediction input.

🌦️ Weather Integration

The dashboard retrieves weather information based on the selected field location.

The current system uses the Open-Meteo weather service to obtain weather information such as:

Temperature
Relative humidity
Precipitation
Wind speed

Weather information is separate from the soil-fertility model inputs.

🌾 Crop Recommendations

The system provides crop recommendations based on the available soil conditions.

The current recommendation system evaluates crops using agronomic screening rules involving factors such as:

Soil pH
Soil moisture
Nitrogen
CEC

The current implementation provides recommendations for crops including:

Rice
Wheat
Maize
Groundnut
Millet

Crop recommendations are currently rule-based and are not produced by a separately trained crop-prediction model.

📈 Dashboard Features

The SoilAI dashboard provides:

Overview
Current soil readings
Fertility prediction
Model confidence
Model agreement
Field location
System status
Analytics
Model comparison
Prediction statistics
Historical information
Explainability
SHAP feature contributions
LIME local explanations
Crop Recommendations
Recommended crops
Recommendation reasoning
Current soil-condition basis
History
Previously recorded predictions
Soil measurements
Fertility results
Model information
🗂️ Project Structure
soil_project_complete/
│
├── arduino/
│   └── sensor_reader.ino
│
├── backend/
│   ├── app.py
│   │
│   ├── data/
│   │   ├── soil_data.csv
│   │   ├── soil_training.csv
│   │   ├── ph.tif
│   │   ├── moisture.tif
│   │   ├── nitrogen.tif
│   │   └── cec.tif
│   │
│   └── models/
│       ├── background_data.joblib
│       ├── cat_model.joblib
│       ├── class_names.joblib
│       ├── feature_names.joblib
│       └── lgb_model.joblib
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
├── .gitignore
└── README.md
💾 Dataset

The project uses geospatial soil data extracted from soil raster/GeoTIFF datasets.

The generated soil dataset contains:

12,748 observations

with the following fields:

latitude
longitude
ph
moisture
nitrogen
cec

The data was used to train the soil-fertility classification models.

Large GeoTIFF files are excluded from the Git repository because of their size and are intended to be handled separately for deployment.

📊 Model Performance

The current trained models achieved the following test accuracy:

Model	Accuracy
LightGBM	98.59%
CatBoost	97.49%

These results are based on the project's current dataset and evaluation procedure.

High accuracy on this dataset does not necessarily imply equivalent performance on unseen real-world field conditions. Real-world performance should be evaluated using independently collected and validated soil measurements.

⚙️ Technologies Used
Programming
Python
JavaScript
HTML
CSS
Backend
Flask
Flask-CORS
SQLite
Machine Learning
LightGBM
CatBoost
Scikit-learn
Pandas
NumPy
Explainable AI
SHAP
LIME
Geospatial Processing
Rasterio
GeoTIFF soil raster data
IoT
Arduino
Soil pH sensor
Capacitive soil-moisture sensor
Serial communication
External Data
Open-Meteo weather API
🚀 Running the Project Locally
1. Clone the repository
git clone https://github.com/Srilakshmi1110/explainable-iot-soil-fertility.git
cd explainable-iot-soil-fertility
2. Create a virtual environment
python -m venv .venv

Activate it on Windows:

.venv\Scripts\activate
3. Install dependencies
pip install -r requirements.txt
4. Configure Arduino

Open:

config.py

Set the correct Arduino COM port:

SERIAL_PORT = "COM3"
SERIAL_BAUD = 9600

Change COM3 if your Arduino appears on another port.

5. Upload the Arduino program

Open:

arduino/sensor_reader.ino

Upload it to the Arduino.

The Arduino should output:

pH,moisture

through the Serial Monitor.

6. Start the backend

From the project root:

python backend/app.py

Open:

http://localhost:5000
7. Set the field location

Allow browser location access or select/set the field location through the dashboard.

The location is required for retrieving geospatial nitrogen and CEC values.

🔐 Real Data Policy

This project follows a real-data-only approach.

The system does not intentionally generate fake sensor readings when hardware is unavailable.

When the Arduino is disconnected:

Waiting for Arduino

is displayed instead of fabricated pH or moisture values.

The same principle is applied to soil raster lookups and explainability: if valid data is unavailable, the system reports the problem rather than silently inventing values.

☁️ Deployment

The application is designed to be deployable as a Flask web application.

The planned cloud architecture is:

User Browser
     │
     ▼
Google Cloud Run
     │
     ├── Flask Application
     ├── ML Models
     └── Dashboard
          │
          ├── Soil Data
          ├── Weather API
          └── IoT Data Gateway

For cloud deployment, the large GeoTIFF datasets need to be hosted separately rather than committed directly to GitHub.

Important IoT Deployment Note

A Cloud Run application cannot directly access a USB Arduino connected to a personal laptop.

Therefore:

Local Development:
Arduino → USB → Laptop → Flask

Cloud Deployment:
Arduino → IoT/Network Gateway → Cloud Run

A network-based IoT bridge will be required for continuous Arduino readings after cloud deployment.

🔮 Future Improvements
Network-based Arduino/IoT communication
Persistent cloud database
Cloud Storage integration for large raster datasets
Independent field-data validation
More comprehensive crop recommendation dataset
Additional soil sensors
Automated model retraining
Improved geospatial soil-data integration
Cloud monitoring and logging
👩‍💻 Project

Title: Explainable IoT Framework for Soil Fertility Prediction

Domain:
IoT | Machine Learning | Explainable AI | Agriculture | Geospatial Data

Core Technologies:
Python | Flask | Arduino | LightGBM | CatBoost | SHAP | LIME | Rasterio

📜 License

This project is developed for educational and research purposes.

You used a geospatial soil-property dataset, extracted from GeoTIFF soil raster data.

The dataset you created for the ML model has 12,748 observations and these 6 features:

Latitude
Longitude
pH
Moisture
Nitrogen (N)
CEC (Cation Exchange Capacity)

Your soil_data.csv / soil_training.csv contains these values.

For the actual system:

pH + moisture → eventually come from your Arduino sensors
Nitrogen + CEC → come from your existing geospatial raster data at the selected location
Latitude + longitude → identify the field location

So if someone asks “What dataset did you use?”, a good answer is:

“I used a geospatial soil-property dataset derived from GeoTIFF raster data, containing 12,748 spatial observations with latitude, longitude, pH, moisture, nitrogen, and CEC attributes. These features were used to train the LightGBM and CatBoost soil-fertility classification models.”

The dataset is not an Arduino dataset—the Arduino is being integrated for real-time pH and moisture measurements after training.

