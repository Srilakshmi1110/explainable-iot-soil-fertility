"""
SOIL FERTILITY MODEL TRAINING
=============================

Uses extracted soil data:
- latitude
- longitude
- ph
- moisture
- nitrogen
- cec

Creates fertility classes from the soil measurements
and trains LightGBM + CatBoost.
"""

import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import lightgbm as lgb
from catboost import CatBoostClassifier
import joblib


DATA_FILE = "backend/data/soil_data.csv"
MODEL_DIR = "backend/models"

os.makedirs(MODEL_DIR, exist_ok=True)


# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

def load_data():

    print("=" * 70)
    print("LOADING SOIL DATA")
    print("=" * 70)

    df = pd.read_csv(DATA_FILE)

    print(f"Loaded {len(df)} rows")
    print("Columns:", df.columns.tolist())

    required = [
        "latitude",
        "longitude",
        "ph",
        "moisture",
        "nitrogen",
        "cec"
    ]

    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    # Remove invalid rows
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=required)

    print(f"Valid rows after cleaning: {len(df)}")

    return df


# ---------------------------------------------------------
# CREATE FERTILITY LABEL
# ---------------------------------------------------------

def create_fertility_labels(df):

    print("\nCreating fertility classes...")

    # Normalize each soil parameter between 0 and 1
    def normalize(series):
        minimum = series.min()
        maximum = series.max()

        if maximum == minimum:
            return pd.Series(0.5, index=series.index)

        return (series - minimum) / (maximum - minimum)

    ph_score = normalize(df["ph"])

    # pH is best roughly around neutral
    ph_score = 1 - abs(ph_score - 0.5) * 2
    ph_score = ph_score.clip(0, 1)

    moisture_score = normalize(df["moisture"])
    nitrogen_score = normalize(df["nitrogen"])
    cec_score = normalize(df["cec"])

    # Overall fertility score
    fertility_score = (
        0.30 * ph_score +
        0.20 * moisture_score +
        0.30 * nitrogen_score +
        0.20 * cec_score
    )

    # Convert score into classes
    df["fertility"] = pd.cut(
        fertility_score,
        bins=[-np.inf, 0.33, 0.66, np.inf],
        labels=["Low", "Medium", "High"]
    )

    print("\nFertility distribution:")
    print(df["fertility"].value_counts())

    return df


# ---------------------------------------------------------
# TRAIN MODELS
# ---------------------------------------------------------

def train_models(X_train, X_test, y_train, y_test):

    print("\n" + "=" * 70)
    print("TRAINING LIGHTGBM")
    print("=" * 70)

    lgb_model = lgb.LGBMClassifier(
        n_estimators=200,
        learning_rate=0.05,
        num_leaves=31,
        random_state=42,
        verbosity=-1
    )

    lgb_model.fit(X_train, y_train)

    lgb_pred = lgb_model.predict(X_test)

    lgb_accuracy = accuracy_score(y_test, lgb_pred)

    print(f"LightGBM Accuracy: {lgb_accuracy:.4f}")

    print("\nLightGBM Report:")
    print(classification_report(y_test, lgb_pred))


    print("\n" + "=" * 70)
    print("TRAINING CATBOOST")
    print("=" * 70)

    cat_model = CatBoostClassifier(
        iterations=200,
        learning_rate=0.05,
        depth=6,
        random_seed=42,
        verbose=False
    )

    cat_model.fit(X_train, y_train)

    cat_pred = cat_model.predict(X_test)

    cat_accuracy = accuracy_score(y_test, cat_pred)

    print(f"CatBoost Accuracy: {cat_accuracy:.4f}")

    print("\nCatBoost Report:")
    print(classification_report(y_test, cat_pred))


    return lgb_model, cat_model


# ---------------------------------------------------------
# SAVE MODELS
# ---------------------------------------------------------

def save_models(lgb_model, cat_model, X_train, class_names):

    print("\n" + "=" * 70)
    print("SAVING MODELS")
    print("=" * 70)

    joblib.dump(
        lgb_model,
        f"{MODEL_DIR}/lgb_model.joblib"
    )

    joblib.dump(
        cat_model,
        f"{MODEL_DIR}/cat_model.joblib"
    )

    joblib.dump(
        X_train,
        f"{MODEL_DIR}/background_data.joblib"
    )

    joblib.dump(
        class_names,
        f"{MODEL_DIR}/class_names.joblib"
    )

    # Save feature names
    joblib.dump(
        X_train.columns.tolist(),
        f"{MODEL_DIR}/feature_names.joblib"
    )

    print("✓ lgb_model.joblib")
    print("✓ cat_model.joblib")
    print("✓ background_data.joblib")
    print("✓ class_names.joblib")
    print("✓ feature_names.joblib")


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():

    print("\n")
    print("=" * 70)
    print("🌱 SOIL FERTILITY MODEL TRAINING")
    print("=" * 70)

    # Load
    df = load_data()

    # Create target
    df = create_fertility_labels(df)

    # Features
    features = [
        "latitude",
        "longitude",
        "ph",
        "moisture",
        "nitrogen",
        "cec"
    ]

    X = df[features]
    y = df["fertility"].astype(str)

    print("\nFeatures used:")
    print(features)

    print("\nClasses:")
    print(y.unique())

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42,
        stratify=y
    )

    print("\nTraining samples:", len(X_train))
    print("Testing samples:", len(X_test))

    # Train
    lgb_model, cat_model = train_models(
        X_train,
        X_test,
        y_train,
        y_test
    )

    # Save
    class_names = sorted(y.unique().tolist())

    save_models(
        lgb_model,
        cat_model,
        X_train,
        class_names
    )

    print("\n" + "=" * 70)
    print("✅ TRAINING COMPLETE!")
    print("=" * 70)

    print("\nYour models are now in:")
    print("backend/models/")


if __name__ == "__main__":
    main()