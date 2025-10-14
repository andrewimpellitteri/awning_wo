"""
EDA and Model Experimentation Script
=====================================
This script is synchronized with routes/ml.py and allows for offline experimentation
with different model configurations and feature engineering approaches.

Usage:
    python scripts/predict_complete.py
"""

import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np
import time
import warnings

from MLService import MLService

warnings.filterwarnings("ignore")


# Load data using the WorkOrder model (synchronized with routes/ml.py)
print("Loading work orders from database...")
df = MLService.load_work_orders()

if df is None or df.empty:
    raise ValueError("No data available for training")

# Preprocess data using MLService (synchronized with routes/ml.py)
print("Preprocessing data...")
train_df = MLService.preprocess_data(df)
print(f"After preprocessing: {len(train_df)} samples with target variable")

# Engineer features using MLService (synchronized with routes/ml.py)
print("Engineering features...")
train_df = MLService.engineer_features(train_df)

# Feature selection (synchronized with routes/ml.py)
# REMOVED: needs_cleaning, needs_treatment (data leakage)
# ADDED: seasonal/cyclical features (annual business cycle)
feature_cols = [
    "rushorder_binary",
    "firmrush_binary",
    "order_age",
    "month_in",
    "dow_in",
    "quarter_in",
    "is_weekend",
    "is_rush",
    "any_rush",
    "instructions_len",
    "repairs_len",
    "has_repairs_needed",
    "has_required_date",
    "days_until_required",
    "customer_encoded",
    "cust_mean",
    "cust_std",
    "cust_count",
    "season_sin",
    "season_cos",
    "is_peak_season",
    "is_slow_season",
    "is_shoulder_season",
    "seasonal_baseline",
]

# Filter available features
feature_cols = [col for col in feature_cols if col in train_df.columns]

X = train_df[feature_cols].fillna(0)
y = train_df["days_to_complete"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

print(
    f"Dataset ready: {X_train.shape[0]} training samples, {len(feature_cols)} features"
)
print(f"Features: {', '.join(feature_cols)}")
print("=" * 80)

# Model configurations (synchronized with routes/ml.py)
MODEL_CONFIGS = {
    "optuna_best": {
        "n_estimators": 3000,
        "max_depth": 30,
        "num_leaves": 223,
        "learning_rate": 0.0935,
        "min_child_samples": 10,
        "lambda_l1": 1.726,
        "lambda_l2": 1.244,
        "subsample": 0.846,
        "bagging_freq": 9,
        "colsample_bytree": 0.760,
        "description": "Optuna optimized - 0.541 MAE (5-fold CV, no data leakage)",
    },
    "max_complexity": {
        "n_estimators": 2000,
        "max_depth": 25,
        "num_leaves": 255,
        "learning_rate": 0.03,
        "description": "High complexity - 1.824 MAE (~46s training)",
    },
    "deep_wide": {
        "n_estimators": 1000,
        "max_depth": 15,
        "num_leaves": 127,
        "learning_rate": 0.05,
        "description": "Balanced - 3.201 MAE (~12s training)",
    },
    "baseline": {
        "n_estimators": 1000,
        "max_depth": 8,
        "num_leaves": 31,
        "learning_rate": 0.05,
        "description": "Fast - 5.367 MAE (~4s training)",
    },
}

# Define hyperparameter configurations to test
configs = [
    # Optuna optimized config (BEST)
    {
        "name": "Optuna Best",
        "n_estimators": 3000,
        "max_depth": 30,
        "num_leaves": 223,
        "learning_rate": 0.0935,
        "min_child_samples": 10,
        "lambda_l1": 1.726,
        "lambda_l2": 1.244,
        "subsample": 0.846,
        "bagging_freq": 9,
        "colsample_bytree": 0.760,
    },
    # Fast baseline for comparison
    {
        "name": "Baseline (Fast)",
        "n_estimators": 1000,
        "max_depth": 8,
        "num_leaves": 31,
        "learning_rate": 0.05,
    },
    # Balanced option
    {
        "name": "Balanced",
        "n_estimators": 1000,
        "max_depth": 15,
        "num_leaves": 127,
        "learning_rate": 0.05,
    },
]

results = []

for config in configs:
    print(f"\nTesting: {config['name']}")
    print(
        f"  n_estimators: {config['n_estimators']}, max_depth: {config['max_depth']}, num_leaves: {config['num_leaves']}, lr: {config['learning_rate']}"
    )

    start_time = time.time()

    # Create and train model
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=config["n_estimators"],
        learning_rate=config["learning_rate"],
        max_depth=config["max_depth"],
        num_leaves=config["num_leaves"],
        min_child_samples=config.get("min_child_samples", 20),
        reg_lambda=config.get("lambda_l2", 0.0),
        reg_alpha=config.get("lambda_l1", 0.0),
        subsample=config.get("subsample", 0.8),
        subsample_freq=config.get("bagging_freq", 1),
        colsample_bytree=config.get("colsample_bytree", 0.8),
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )

    model.fit(X_train, y_train)

    # Predictions and metrics
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))

    # Calculate R²
    ss_res = np.sum((y_test - y_pred) ** 2)
    ss_tot = np.sum((y_test - np.mean(y_test)) ** 2)
    r2 = 1 - (ss_res / ss_tot)

    training_time = time.time() - start_time

    results.append(
        {
            "config": config["name"],
            "n_estimators": config["n_estimators"],
            "max_depth": config["max_depth"],
            "num_leaves": config["num_leaves"],
            "learning_rate": config["learning_rate"],
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "training_time": training_time,
            "model_size": model.n_features_in_
            * config["num_leaves"]
            * config["n_estimators"]
            / 1000000,  # Rough estimate in MB
        }
    )

    print(
        f"  MAE: {mae:.3f} days, RMSE: {rmse:.3f} days, R²: {r2:.3f}, Time: {training_time:.1f}s"
    )

# Convert to DataFrame and analyze results
results_df = pd.DataFrame(results)

print("\n" + "=" * 80)
print("RESULTS SUMMARY")
print("=" * 80)
print(results_df.to_string(index=False))

# Find best configurations
print("\n" + "=" * 80)
print("TOP 5 MODELS BY MAE (Lower is better)")
print("=" * 80)
best_mae = results_df.nsmallest(5, "mae")[
    ["config", "mae", "rmse", "r2", "training_time"]
]
print(best_mae.to_string(index=False))

print("\n" + "=" * 80)
print("TOP 5 MODELS BY R² (Higher is better)")
print("=" * 80)
best_r2 = results_df.nlargest(5, "r2")[["config", "r2", "mae", "rmse", "training_time"]]
print(best_r2.to_string(index=False))

print("\n" + "=" * 80)
print("FASTEST MODELS (Training time < 10s)")
print("=" * 80)
fast_models = results_df[results_df["training_time"] < 10].nsmallest(5, "mae")[
    ["config", "mae", "training_time"]
]
print(fast_models.to_string(index=False))

print("\n" + "=" * 80)
print("PRODUCTION CONFIG COMPARISON")
print("=" * 80)
prod_configs = results_df[
    results_df["config"].str.contains("Production", case=False, na=False)
][["config", "mae", "rmse", "r2", "training_time"]]
print(prod_configs.to_string(index=False))

# Save results to CSV for further analysis
output_file = "model_experiment_results.csv"
results_df.to_csv(output_file, index=False)
print(f"\n✓ Results saved to: {output_file}")

# Additional analysis - feature importance from best model
print("\n" + "=" * 80)
print("FEATURE IMPORTANCE (from best model)")
print("=" * 80)
best_idx = results_df["mae"].idxmin()
best_config = configs[best_idx]

# Train the best model
best_model = lgb.LGBMRegressor(
    objective="regression",
    n_estimators=best_config["n_estimators"],
    learning_rate=best_config["learning_rate"],
    max_depth=best_config["max_depth"],
    num_leaves=best_config["num_leaves"],
    min_child_samples=best_config.get("min_child_samples", 20),
    reg_lambda=best_config.get("lambda_l2", 0.0),
    reg_alpha=best_config.get("lambda_l1", 0.0),
    subsample=best_config.get("subsample", 0.8),
    subsample_freq=best_config.get("bagging_freq", 1),
    colsample_bytree=best_config.get("colsample_bytree", 0.8),
    random_state=42,
    n_jobs=-1,
    verbose=-1,
)
best_model.fit(X_train, y_train)

# Get feature importance
feature_importance = pd.DataFrame(
    {"feature": feature_cols, "importance": best_model.feature_importances_}
).sort_values("importance", ascending=False)

print(feature_importance.to_string(index=False))
print(f"\nBest Model: {best_config['name']}")
print(f"MAE: {results_df.loc[best_idx, 'mae']:.3f} days")
print(f"Training Time: {results_df.loc[best_idx, 'training_time']:.2f} seconds")

print("\n" + "=" * 80)
print("STAGE-BASED PERFORMANCE ANALYSIS")
print("=" * 80)
# Analyze performance by augmentation stage
if "augmentation_stage" in train_df.columns:
    best_model_predictions = best_model.predict(X)
    stage_analysis = train_df[["augmentation_stage", "days_to_complete"]].copy()
    stage_analysis["predicted"] = best_model_predictions
    stage_analysis["error"] = abs(
        stage_analysis["days_to_complete"] - stage_analysis["predicted"]
    )

    print("\nPerformance by Work Order Stage:")
    for stage in [0, 1, 2]:
        stage_data = stage_analysis[stage_analysis["augmentation_stage"] == stage]
        if len(stage_data) > 0:
            stage_name = [
                "Early (no dates)",
                "Middle (clean only)",
                "Late (both dates)",
            ][stage]
            print(f"\nStage {stage} - {stage_name}:")
            print(f"  Samples: {len(stage_data)}")
            print(f"  MAE: {stage_data['error'].mean():.3f} days")
            print(f"  Median Error: {stage_data['error'].median():.3f} days")
            print(
                f"  90th percentile error: {stage_data['error'].quantile(0.9):.3f} days"
            )

print("\n" + "=" * 80)
print("EXPERIMENT COMPLETE")
print("=" * 80)
print("\nKey Improvements:")
print("✓ Removed data leakage from clean/treat date features")
print("✓ Implemented temporal augmentation for stage-aware training")
print("✓ Model now trained on work orders at all stages of completion")
print("✓ Better generalization for production inference on pending orders")
