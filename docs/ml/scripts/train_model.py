#!/usr/bin/env python3
"""
Script simple pour entraîner un modèle de prédiction de waste.

Usage:
    python train_model.py

Requirements:
    pip install pandas scikit-learn numpy
"""

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder


def load_ml_data(data_dir="./ml_datasets"):
    """Load ML training data from JSON file."""

    data_dir = Path(data_dir)

    # Find latest ml_training_data file
    ml_files = list(data_dir.glob("ml_training_data_*.json"))

    if not ml_files:
        print("❌ No ML training data found!")
        print(f"   Run: python export_ml_data.py first")
        return None

    latest_file = max(ml_files, key=lambda p: p.stat().st_mtime)

    print(f"📂 Loading data from: {latest_file}")

    with open(latest_file) as f:
        data = json.load(f)

    return pd.DataFrame(data)


def prepare_features(df):
    """Prepare features for training."""

    print(f"\n📊 Dataset info:")
    print(f"   Total records: {len(df)}")
    print(f"   Resources with user action: {df['user_action'].notna().sum()}")

    # Filter only records with user action (deleted or kept)
    df_labeled = df[df["user_action"].notna()].copy()

    print(f"   Labeled records for training: {len(df_labeled)}")

    if len(df_labeled) < 100:
        print(f"\n⚠️  Warning: Only {len(df_labeled)} labeled records.")
        print("   Recommendation: Wait for more user actions (target: 1000+)")
        return None, None, None

    # Map user_action to binary: deleted = 1 (waste), kept = 0 (not waste)
    df_labeled["is_waste"] = df_labeled["user_action"].map({"deleted": 1, "kept": 0, "ignored": 0})

    # Encode categorical variables
    le_resource_type = LabelEncoder()
    le_provider = LabelEncoder()
    le_region = LabelEncoder()
    le_scenario = LabelEncoder()
    le_confidence = LabelEncoder()

    df_labeled["resource_type_encoded"] = le_resource_type.fit_transform(
        df_labeled["resource_type"]
    )
    df_labeled["provider_encoded"] = le_provider.fit_transform(df_labeled["provider"])
    df_labeled["region_encoded"] = le_region.fit_transform(df_labeled["region_anonymized"])
    df_labeled["scenario_encoded"] = le_scenario.fit_transform(df_labeled["detection_scenario"])
    df_labeled["confidence_encoded"] = le_confidence.fit_transform(df_labeled["confidence_level"])

    # Features
    features = [
        "resource_type_encoded",
        "provider_encoded",
        "region_encoded",
        "scenario_encoded",
        "confidence_encoded",
        "resource_age_days",
        "cost_monthly",
    ]

    X = df_labeled[features]
    y = df_labeled["is_waste"]

    encoders = {
        "resource_type": le_resource_type,
        "provider": le_provider,
        "region": le_region,
        "scenario": le_scenario,
        "confidence": le_confidence,
    }

    return X, y, encoders


def train_model(X, y):
    """Train Random Forest model."""

    print("\n🤖 Training Random Forest model...")

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print(f"   Training set: {len(X_train)} samples")
    print(f"   Test set: {len(X_test)} samples")

    # Train model
    model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)

    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    print(f"\n📈 Model Performance:")
    print(f"   Accuracy: {accuracy * 100:.2f}%")

    print("\n📊 Classification Report:")
    print(classification_report(y_test, y_pred, target_names=["Not Waste", "Waste"]))

    print("\n🎯 Confusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"   True Negatives:  {cm[0][0]}")
    print(f"   False Positives: {cm[0][1]}")
    print(f"   False Negatives: {cm[1][0]}")
    print(f"   True Positives:  {cm[1][1]}")

    # Feature importance
    print("\n🔍 Top 5 Most Important Features:")
    feature_importance = pd.DataFrame(
        {"feature": X.columns, "importance": model.feature_importances_}
    ).sort_values("importance", ascending=False)

    for idx, row in feature_importance.head(5).iterrows():
        print(f"   {row['feature']}: {row['importance']:.4f}")

    return model, accuracy


def save_model(model, encoders, accuracy):
    """Save trained model and encoders."""

    output_dir = Path("./ml_models")
    output_dir.mkdir(exist_ok=True)

    # Save model
    model_path = output_dir / "waste_prediction_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    # Save encoders
    encoders_path = output_dir / "encoders.pkl"
    with open(encoders_path, "wb") as f:
        pickle.dump(encoders, f)

    # Save metadata
    metadata = {"accuracy": accuracy, "model_type": "RandomForestClassifier", "n_estimators": 100}

    metadata_path = output_dir / "model_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n💾 Model saved to: {model_path}")
    print(f"💾 Encoders saved to: {encoders_path}")
    print(f"💾 Metadata saved to: {metadata_path}")


def main():
    """Main training pipeline."""

    print("🚀 CloudWaste ML Model Training")
    print("=" * 60)

    # Load data
    df = load_ml_data()
    if df is None:
        return

    # Prepare features
    X, y, encoders = prepare_features(df)
    if X is None:
        return

    # Train model
    model, accuracy = train_model(X, y)

    # Save model
    save_model(model, encoders, accuracy)

    print("\n✅ Training complete!")
    print("\n🎯 Next steps:")
    print("   1. Review model performance above")
    print("   2. If accuracy > 80%, deploy to production")
    print("   3. If accuracy < 80%, collect more data and retrain")
    print(f"\n📊 Current accuracy: {accuracy * 100:.2f}%")

    if accuracy > 0.8:
        print("   ✅ Model is production-ready!")
    elif accuracy > 0.7:
        print("   ⚠️  Model is decent, but could be improved")
    else:
        print("   ❌ Model needs more data (target: 1000+ labeled samples)")


if __name__ == "__main__":
    try:
        import sklearn  # noqa
    except ImportError:
        print("❌ Missing dependencies!")
        print("   Run: pip install pandas scikit-learn numpy")
        exit(1)

    main()
