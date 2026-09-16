import joblib
import pandas as pd

# --------------------------------------------------
# Test input - same values used in dashboard
# --------------------------------------------------

x = pd.DataFrame(
    [[
        13.068198,   # latitude
        77.50388,    # longitude
        6.5,         # pH
        65,          # moisture
        25,          # temperature
        174,         # nitrogen
        140          # CEC
    ]],
    columns=[
        "latitude",
        "longitude",
        "ph",
        "moisture",
        "temperature",
        "nitrogen",
        "cec"
    ]
)


# --------------------------------------------------
# Load trained models
# --------------------------------------------------

lgb_model = joblib.load(
    "backend/models/lgb_model_temperature.joblib"
)

cat_model = joblib.load(
    "backend/models/cat_model_temperature.joblib"
)


# --------------------------------------------------
# LightGBM
# --------------------------------------------------

lgb_prediction = lgb_model.predict(x)
lgb_probability = lgb_model.predict_proba(x)[0]

print()
print("=" * 60)
print("LIGHTGBM")
print("=" * 60)

print("Classes:")
print(lgb_model.classes_)

print()
print("Prediction:")
print(lgb_prediction)

print()
print("Probabilities:")

for class_name, probability in zip(
    lgb_model.classes_,
    lgb_probability
):
    print(
        f"{class_name}: {probability * 100:.4f}%"
    )

print()
print(
    "Confidence:",
    f"{max(lgb_probability) * 100:.4f}%"
)


# --------------------------------------------------
# CatBoost
# --------------------------------------------------

cat_prediction = cat_model.predict(x)
cat_probability = cat_model.predict_proba(x)[0]

print()
print("=" * 60)
print("CATBOOST")
print("=" * 60)

print("Classes:")
print(cat_model.classes_)

print()
print("Prediction:")
print(cat_prediction)

print()
print("Probabilities:")

for class_name, probability in zip(
    cat_model.classes_,
    cat_probability
):
    print(
        f"{class_name}: {probability * 100:.4f}%"
    )

print()
print(
    "Confidence:",
    f"{max(cat_probability) * 100:.4f}%"
)


# --------------------------------------------------
# Combined confidence
# --------------------------------------------------

lgb_confidence = max(lgb_probability)
cat_confidence = max(cat_probability)

combined_confidence = (
    lgb_confidence +
    cat_confidence
) / 2

print()
print("=" * 60)
print("COMBINED RESULT")
print("=" * 60)

print(
    "LightGBM confidence:",
    f"{lgb_confidence * 100:.4f}%"
)

print(
    "CatBoost confidence:",
    f"{cat_confidence * 100:.4f}%"
)

print(
    "Combined confidence:",
    f"{combined_confidence * 100:.4f}%"
)

print()
print("=" * 60)