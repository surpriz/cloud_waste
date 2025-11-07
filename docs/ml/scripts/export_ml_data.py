#!/usr/bin/env python3
"""
Script simple pour exporter les données ML vers un fichier pour training.

Usage:
    python export_ml_data.py

Génère:
    - ml_dataset.json : Toutes les données ML pour training
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, "backend")

from app.ml.data_pipeline import export_all_ml_datasets


async def main():
    """Export all ML data for training."""

    print("🚀 CloudWaste ML Data Export")
    print("=" * 50)

    # Export datasets (last 90 days)
    print("\n📊 Exporting ML datasets...")

    results = await export_all_ml_datasets(
        output_format="json",
        output_dir="./ml_datasets"
    )

    print("\n✅ Export complete!")
    print("\nFiles created:")
    for dataset_type, filepath in results.items():
        print(f"  - {dataset_type}: {filepath}")

    print("\n📈 You can now use these files to train your ML models!")
    print("\nRecommended ML models:")
    print("  1. Waste Prediction (Classification): ml_training_data.json")
    print("  2. Cost Forecasting (Time Series): cost_trends.json")
    print("  3. User Behavior (Recommendation): user_action_patterns.json")


if __name__ == "__main__":
    asyncio.run(main())
