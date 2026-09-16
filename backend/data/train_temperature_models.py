"""
TRAIN TEMPERATURE-AUGMENTED SOIL FERTILITY MODELS
=================================================

Purpose
-------
Train the 7-feature soil fertility models used by the dashboard.

Features
--------
1. latitude
2. longitude
3. ph
4. moisture
5. temperature
6. nitrogen
7. cec

Important
---------
The original soil_data.csv does not contain an observation date.
Therefore, observation-time historical temperature cannot be recovered
from the dataset.

This training script uses a fixed reference temperature of 25.0 °C
so that the 7-feature model can be trained without depending on the
NASA POWER API.

This temperature is a training compatibility value, NOT historical
temperature measured at each soil observation.

The live Arduino thermistor temperature can still be supplied to the
trained model by the application.

The original dataset stores pH and moisture in scaled form:
    pH       -> approximately 60-70
    moisture -> approximately 400-600

The dashboard uses:
    pH       -> 0-14
    moisture -> 0-100

Therefore:
    pH       = original pH / 10
    moisture = original moisture / 10

Nitrogen and CEC are kept in their original dataset scale.
"""

from pathlib import Path
import sys
import warnings

import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)

from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier

warnings.filterwarnings("ignore")


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent

DATA_DIR = BASE_DIR
MODEL_DIR = PROJECT_ROOT / "backend" / "models"

DATA_FILE = DATA_DIR / "soil_data.csv"

MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# SETTINGS
# ============================================================

RANDOM_STATE = 42

TEST_SIZE = 0.20

REFERENCE_TEMPERATURE = 25.0

FEATURES = [
    "latitude",
    "longitude",
    "ph",
    "moisture",
    "temperature",
    "nitrogen",
    "cec",
]


# ============================================================
# PRINT HEADER
# ============================================================

print()
print("=" * 70)
print("TEMPERATURE-AUGMENTED SOIL FERTILITY MODEL TRAINING")
print("=" * 70)
print()

print("Project root :", PROJECT_ROOT)
print("Data file    :", DATA_FILE)
print("Model folder :", MODEL_DIR)
print()


# ============================================================
# CHECK DATASET
# ============================================================

if not DATA_FILE.exists():
    raise FileNotFoundError(
        f"Dataset not found:\n{DATA_FILE}"
    )


# ============================================================
# LOAD DATA
# ============================================================

print("Loading soil dataset...")

df = pd.read_csv(DATA_FILE)

print()
print("Dataset loaded successfully.")
print("Rows    :", len(df))
print("Columns :", list(df.columns))
print()


# ============================================================
# CHECK REQUIRED COLUMNS
# ============================================================

required_columns = [
    "latitude",
    "longitude",
    "ph",
    "moisture",
    "nitrogen",
    "cec",
]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise ValueError(
        "Missing required columns: "
        + ", ".join(missing_columns)
    )


# ============================================================
# CLEAN DATA
# ============================================================

print("Cleaning dataset...")

for column in required_columns:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    )

before_rows = len(df)

df = df.dropna(
    subset=required_columns
).reset_index(drop=True)

after_rows = len(df)

print(
    f"Removed {before_rows - after_rows} rows "
    f"with missing/invalid values."
)

print("Remaining rows:", after_rows)
print()


# ============================================================
# CREATE PSEUDO LABELS
# ============================================================
#
# The original dataset does not contain an independent fertility
# target. The project already uses the existing 6-feature models
# to generate the fertility classes.
#
# We load the original models and reproduce their predictions.
#
# ============================================================

print("=" * 70)
print("CREATING FERTILITY LABELS")
print("=" * 70)
print()

OLD_LGB_FILE = MODEL_DIR / "lgb_model.joblib"
OLD_CAT_FILE = MODEL_DIR / "cat_model.joblib"

if not OLD_LGB_FILE.exists():
    raise FileNotFoundError(
        f"Original LightGBM model not found:\n{OLD_LGB_FILE}"
    )

if not OLD_CAT_FILE.exists():
    raise FileNotFoundError(
        f"Original CatBoost model not found:\n{OLD_CAT_FILE}"
    )


print("Loading original LightGBM model...")
old_lgb_model = joblib.load(OLD_LGB_FILE)

print("Loading original CatBoost model...")
old_cat_model = joblib.load(OLD_CAT_FILE)

print("Original models loaded.")
print()


# ============================================================
# PRESERVE ORIGINAL VALUES
# ============================================================
#
# IMPORTANT:
# The original six-feature models were trained using the original
# dataset coordinate/value representation.
#
# Therefore labels are generated BEFORE changing pH/moisture units.
#
# ============================================================

label_features = [
    "latitude",
    "longitude",
    "ph",
    "moisture",
    "nitrogen",
    "cec",
]

X_original = df[label_features].copy()


# ============================================================
# GENERATE LABELS
# ============================================================

print("Generating provisional fertility labels...")

old_lgb_predictions = old_lgb_model.predict(
    X_original
)

old_cat_predictions = old_cat_model.predict(
    X_original
)


# ============================================================
# HANDLE DIFFERENT MODEL OUTPUT FORMATS
# ============================================================

def clean_prediction(prediction):
    """
    Convert model prediction into a clean class name.
    """

    if isinstance(prediction, np.ndarray):
        prediction = prediction.item()

    prediction = str(prediction)

    # Handle strings such as:
    # ['Medium']
    prediction = prediction.strip(
        "[]'\" "
    )

    return prediction


lgb_labels = np.array([
    clean_prediction(x)
    for x in old_lgb_predictions
])

cat_labels = np.array([
    clean_prediction(x)
    for x in old_cat_predictions
])


# ============================================================
# COMBINE MODEL LABELS
# ============================================================
#
# If both original models agree, use that class.
#
# If they disagree, use the LightGBM result because it was the
# primary model used in the existing project.
#
# ============================================================

fertility_labels = []

for lgb_label, cat_label in zip(
    lgb_labels,
    cat_labels
):

    if lgb_label == cat_label:
        fertility_labels.append(lgb_label)
    else:
        fertility_labels.append(lgb_label)


df["fertility"] = fertility_labels


# ============================================================
# SHOW LABEL DISTRIBUTION
# ============================================================

print()
print("Fertility label distribution:")
print()

print(
    df["fertility"].value_counts()
)

print()


# ============================================================
# CONVERT HUMAN-UNIT FEATURES
# ============================================================
#
# Original dataset:
# pH       ≈ 60-70
# moisture ≈ 400-600
#
# Dashboard:
# pH       = 0-14
# moisture = 0-100
#
# Convert before training the new 7-feature models.
#
# ============================================================

print("=" * 70)
print("CONVERTING SOIL FEATURE UNITS")
print("=" * 70)
print()

print("Original pH range:")
print(
    df["ph"].min(),
    "to",
    df["ph"].max()
)

print("Original moisture range:")
print(
    df["moisture"].min(),
    "to",
    df["moisture"].max()
)

print()


df["ph"] = df["ph"] / 10.0

df["moisture"] = df["moisture"] / 10.0


print("Converted pH range:")
print(
    df["ph"].min(),
    "to",
    df["ph"].max()
)

print("Converted moisture range:")
print(
    df["moisture"].min(),
    "to",
    df["moisture"].max()
)

print()


# ============================================================
# ADD TEMPERATURE FEATURE
# ============================================================
#
# The original dataset does not contain observation dates.
# Therefore, a historical temperature cannot be reconstructed.
#
# We use 25 °C as a reference training value.
#
# IMPORTANT:
# This is NOT claimed to be the historical temperature for the
# original observations.
#
# ============================================================

print("=" * 70)
print("ADDING TEMPERATURE FEATURE")
print("=" * 70)
print()

print(
    f"Using reference training temperature: "
    f"{REFERENCE_TEMPERATURE:.1f} °C"
)

print(
    "Note: the original dataset has no observation date, "
    "so observation-specific historical temperature cannot "
    "be recovered."
)

print()


df["temperature"] = REFERENCE_TEMPERATURE


# ============================================================
# CREATE FINAL MODEL DATASET
# ============================================================

model_df = df[
    FEATURES + ["fertility"]
].copy()


# ============================================================
# REMOVE INVALID VALUES
# ============================================================

model_df = model_df.replace(
    [np.inf, -np.inf],
    np.nan
)

model_df = model_df.dropna(
    subset=FEATURES + ["fertility"]
).reset_index(drop=True)


# ============================================================
# FINAL DATASET INFORMATION
# ============================================================

print("=" * 70)
print("FINAL TRAINING DATA")
print("=" * 70)
print()

print("Rows:", len(model_df))
print()

print("Features:")
for feature in FEATURES:
    print("  -", feature)

print()

print("Final feature ranges:")
print()

for feature in FEATURES:

    print(
        f"{feature:12s}: "
        f"{model_df[feature].min():.4f}"
        f" -> "
        f"{model_df[feature].max():.4f}"
    )

print()


# ============================================================
# PREPARE X AND Y
# ============================================================

X = model_df[FEATURES].copy()

y = model_df["fertility"].astype(str)


# ============================================================
# TRAIN / TEST SPLIT
# ============================================================

print("=" * 70)
print("TRAIN / TEST SPLIT")
print("=" * 70)
print()

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=TEST_SIZE,
    random_state=RANDOM_STATE,
    stratify=y,
)

print("Training samples:", len(X_train))
print("Testing samples :", len(X_test))
print()


# ============================================================
# LIGHTGBM
# ============================================================

print("=" * 70)
print("TRAINING LIGHTGBM")
print("=" * 70)
print()

lgb_model = LGBMClassifier(
    objective="multiclass",
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=31,
    max_depth=-1,
    subsample=0.9,
    colsample_bytree=0.9,
    random_state=RANDOM_STATE,
    n_jobs=-1,
    verbosity=-1,
)


lgb_model.fit(
    X_train,
    y_train
)


# ============================================================
# LIGHTGBM EVALUATION
# ============================================================

lgb_test_predictions = lgb_model.predict(
    X_test
)

lgb_accuracy = accuracy_score(
    y_test,
    lgb_test_predictions
)

print(
    f"LightGBM Accuracy: "
    f"{lgb_accuracy * 100:.2f}%"
)

print()

print("LightGBM Classification Report:")
print(
    classification_report(
        y_test,
        lgb_test_predictions,
        zero_division=0
    )
)

print("LightGBM Confusion Matrix:")
print(
    confusion_matrix(
        y_test,
        lgb_test_predictions
    )
)

print()


# ============================================================
# CATBOOST
# ============================================================

print("=" * 70)
print("TRAINING CATBOOST")
print("=" * 70)
print()

cat_model = CatBoostClassifier(
    iterations=300,
    learning_rate=0.05,
    depth=7,
    loss_function="MultiClass",
    random_seed=RANDOM_STATE,
    verbose=False,
)


cat_model.fit(
    X_train,
    y_train
)


# ============================================================
# CATBOOST EVALUATION
# ============================================================

cat_test_predictions = cat_model.predict(
    X_test
)


cat_test_predictions = np.asarray(
    cat_test_predictions
).reshape(-1)

cat_test_predictions = np.array([
    clean_prediction(x)
    for x in cat_test_predictions
])


cat_accuracy = accuracy_score(
    y_test,
    cat_test_predictions
)


print(
    f"CatBoost Accuracy: "
    f"{cat_accuracy * 100:.2f}%"
)

print()

print("CatBoost Classification Report:")
print(
    classification_report(
        y_test,
        cat_test_predictions,
        zero_division=0
    )
)

print("CatBoost Confusion Matrix:")
print(
    confusion_matrix(
        y_test,
        cat_test_predictions
    )
)

print()


# ============================================================
# MODEL AGREEMENT
# ============================================================

agreement = (
    lgb_test_predictions.astype(str)
    ==
    cat_test_predictions.astype(str)
)

agreement_rate = agreement.mean()


print("=" * 70)
print("MODEL AGREEMENT")
print("=" * 70)
print()

print(
    f"LightGBM/CatBoost agreement: "
    f"{agreement_rate * 100:.2f}%"
)

print()


# ============================================================
# CLASS NAMES
# ============================================================

class_names = sorted(
    y.unique().tolist()
)


print("Class names:")
print(class_names)
print()


# ============================================================
# BACKGROUND DATA FOR SHAP / LIME
# ============================================================
#
# Use a representative sample instead of storing the complete
# training matrix.
#
# This keeps the XAI files reasonably small.
#
# ============================================================

BACKGROUND_SIZE = min(
    500,
    len(X_train)
)


background_data = (
    X_train
    .sample(
        n=BACKGROUND_SIZE,
        random_state=RANDOM_STATE
    )
    .values
)


# ============================================================
# SAVE LIGHTGBM
# ============================================================

lgb_output = (
    MODEL_DIR /
    "lgb_model_temperature.joblib"
)

joblib.dump(
    lgb_model,
    lgb_output
)


# ============================================================
# SAVE CATBOOST
# ============================================================

cat_output = (
    MODEL_DIR /
    "cat_model_temperature.joblib"
)

joblib.dump(
    cat_model,
    cat_output
)


# ============================================================
# SAVE FEATURE NAMES
# ============================================================

feature_output = (
    MODEL_DIR /
    "feature_names_temperature.joblib"
)

joblib.dump(
    FEATURES,
    feature_output
)


# ============================================================
# SAVE CLASS NAMES
# ============================================================

class_output = (
    MODEL_DIR /
    "class_names_temperature.joblib"
)

joblib.dump(
    class_names,
    class_output
)


# ============================================================
# SAVE BACKGROUND DATA
# ============================================================

background_output = (
    MODEL_DIR /
    "background_data_temperature.joblib"
)

joblib.dump(
    background_data,
    background_output
)


# ============================================================
# SAVE TRAINING DATA
# ============================================================

training_output = (
    DATA_DIR /
    "soil_training_temperature.csv"
)

model_df.to_csv(
    training_output,
    index=False
)


# ============================================================
# SAVE METRICS
# ============================================================

metrics = {
    "lightgbm_accuracy": float(lgb_accuracy),
    "catboost_accuracy": float(cat_accuracy),
    "model_agreement": float(agreement_rate),
    "training_samples": int(len(X_train)),
    "testing_samples": int(len(X_test)),
    "reference_temperature": float(
        REFERENCE_TEMPERATURE
    ),
    "features": FEATURES,
    "class_names": class_names,
    "pH_conversion": "original / 10",
    "moisture_conversion": "original / 10",
}


metrics_output = (
    MODEL_DIR /
    "temperature_model_metrics.joblib"
)

joblib.dump(
    metrics,
    metrics_output
)


# ============================================================
# VERIFY SAVED MODELS
# ============================================================

print("=" * 70)
print("VERIFYING SAVED MODELS")
print("=" * 70)
print()

saved_files = [
    lgb_output,
    cat_output,
    feature_output,
    class_output,
    background_output,
    training_output,
    metrics_output,
]


for file_path in saved_files:

    if file_path.exists():

        size_kb = (
            file_path.stat().st_size
            / 1024
        )

        print(
            f"OK  {file_path.name:45s}"
            f"{size_kb:10.1f} KB"
        )

    else:

        print(
            f"ERROR: {file_path.name}"
        )


print()


# ============================================================
# TEST A SAMPLE PREDICTION
# ============================================================

print("=" * 70)
print("TESTING SAMPLE PREDICTION")
print("=" * 70)
print()


sample = X_test.iloc[
    [0]
].copy()


sample_lgb_prediction = (
    lgb_model.predict(sample)[0]
)

sample_cat_prediction = (
    cat_model.predict(sample)
)

sample_cat_prediction = clean_prediction(
    sample_cat_prediction
)


sample_lgb_probability = (
    np.max(
        lgb_model.predict_proba(sample)[0]
    )
)

sample_cat_probability = (
    np.max(
        cat_model.predict_proba(sample)[0]
    )
)


print("Sample input:")
print()

for feature in FEATURES:

    print(
        f"{feature:12s}: "
        f"{sample.iloc[0][feature]:.4f}"
    )

print()

print(
    "LightGBM prediction :",
    sample_lgb_prediction
)

print(
    "LightGBM confidence :",
    f"{sample_lgb_probability * 100:.2f}%"
)

print()

print(
    "CatBoost prediction :",
    sample_cat_prediction
)

print(
    "CatBoost confidence :",
    f"{sample_cat_probability * 100:.2f}%"
)

print()


# ============================================================
# FINAL SUMMARY
# ============================================================

print("=" * 70)
print("TRAINING COMPLETE")
print("=" * 70)
print()

print(
    f"LightGBM Accuracy : "
    f"{lgb_accuracy * 100:.2f}%"
)

print(
    f"CatBoost Accuracy : "
    f"{cat_accuracy * 100:.2f}%"
)

print(
    f"Model Agreement   : "
    f"{agreement_rate * 100:.2f}%"
)

print()

print("Saved models:")
print(
    "  ",
    lgb_output
)

print(
    "  ",
    cat_output
)

print()

print("Saved XAI files:")
print(
    "  ",
    feature_output
)

print(
    "  ",
    class_output
)

print(
    "  ",
    background_output
)

print()

print(
    "Training dataset:"
)

print(
    "  ",
    training_output
)

print()

print(
    "Reference training temperature:",
    f"{REFERENCE_TEMPERATURE:.1f} °C"
)

print()

print(
    "IMPORTANT:"
)

print(
    "The 25 °C value is a reference training value because"
)

print(
    "the original soil dataset has no observation dates."
)

print(
    "The live dashboard can still supply the thermistor"
)

print(
    "temperature during real-time prediction."
)

print()

print("=" * 70)