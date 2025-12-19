from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required
from extensions import db
from models.work_order import WorkOrder
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import LabelEncoder
import numpy as np
import time
import warnings
import joblib
import os
from datetime import datetime, timedelta
from utils.file_upload import save_ml_model

warnings.filterwarnings("ignore")

# Create blueprint
ml_bp = Blueprint("ml", __name__, url_prefix="/ml")

# Model configurations from your analysis
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

# Model cache with TTL (thread-safe, simple solution for multi-worker issue #93)
# Each worker loads the model independently, with a 5-minute cache
# When cron job saves a new model to S3, workers pick it up on next load
_model_cache = {
    "model": None,
    "metadata": {},
    "loaded_at": None,
    "cache_ttl_seconds": 300,  # 5 minutes
}


def get_current_model():
    """
    Get the current model, loading from S3 if cache is expired or empty.

    This fixes issue #93 by:
    - Each worker has its own cache (no shared global state)
    - Cache expires after 5 minutes (workers pick up new models automatically)
    - Falls back to S3 as single source of truth

    Returns:
        tuple: (model, metadata) or (None, {}) if no model available
    """
    import time
    from datetime import datetime

    cache = _model_cache
    now = time.time()

    # Check if cache is valid
    if (cache["model"] is not None and
        cache["loaded_at"] is not None and
        (now - cache["loaded_at"]) < cache["cache_ttl_seconds"]):
        # Cache hit
        return cache["model"], cache["metadata"]

    # Cache miss or expired - load from S3
    print(f"[ML CACHE] Loading model from S3 (cache expired or empty)")
    success = load_latest_model_from_s3()

    if success:
        return cache["model"], cache["metadata"]
    else:
        return None, {}


def load_latest_model_from_s3():
    """Load the most recently trained model from S3 and update cache"""
    import time

    cache = _model_cache

    try:
        from utils.file_upload import s3_client, AWS_S3_BUCKET
        import pickle
        import json
        from io import BytesIO

        # List all model files in S3
        response = s3_client.list_objects_v2(
            Bucket=AWS_S3_BUCKET,
            Prefix="ml_models/",
        )

        if "Contents" not in response:
            print("[ML LOAD] No models found in S3")
            return False

        # Get all .pkl model files
        all_model_files = [
            obj for obj in response["Contents"]
            if obj["Key"].endswith(".pkl")
        ]

        if not all_model_files:
            print("[ML LOAD] No model files found in S3")
            return False

        # Prefer cron models, but fall back to any model
        cron_models = [obj for obj in all_model_files if "cron_" in obj["Key"]]

        if cron_models:
            # Use the most recent cron model
            model_files = cron_models
            print(f"[ML LOAD] Found {len(cron_models)} cron model(s)")
        else:
            # Fall back to any available model
            model_files = all_model_files
            print(f"[ML LOAD] No cron models found, using fallback - found {len(model_files)} model(s)")

        # Sort by last modified date, get most recent
        latest_model = sorted(model_files, key=lambda x: x["LastModified"], reverse=True)[0]
        model_name = latest_model["Key"].replace("ml_models/", "").replace(".pkl", "")

        print(f"[ML LOAD] Loading model: {model_name}")

        # Download model from S3
        model_buffer = BytesIO()
        s3_client.download_fileobj(AWS_S3_BUCKET, latest_model["Key"], model_buffer)
        model_buffer.seek(0)
        model = pickle.load(model_buffer)

        # Download metadata from S3
        metadata_key = f"ml_models/{model_name}_metadata.json"
        metadata_buffer = BytesIO()
        s3_client.download_fileobj(AWS_S3_BUCKET, metadata_key, metadata_buffer)
        metadata_buffer.seek(0)
        metadata = json.loads(metadata_buffer.read().decode("utf-8"))

        print(f"[ML LOAD] Model loaded successfully - MAE: {metadata.get('mae')}, "
              f"Trained at: {metadata.get('trained_at')}")

        # Update cache
        cache["model"] = model
        cache["metadata"] = metadata
        cache["loaded_at"] = time.time()

        return True

    except Exception as e:
        print(f"[ML LOAD] Failed to load model from S3: {e}")
        return False


# Load the latest model on startup
print("[ML STARTUP] Attempting to load latest model from S3...")
load_latest_model_from_s3()


class MLService:
    @staticmethod
    def convert_to_binary(series):
        """Convert various formats to binary"""
        if series.dtype == "object":
            return (
                series.fillna("")
                .astype(str)
                .str.lower()
                .isin(["true", "t", "1", "yes", "y"])
                .astype(int)
            )
        return series.fillna(0).astype(bool).astype(int)

    @staticmethod
    def convert_to_numeric(series):
        """Convert to numeric, filling NaN with 0"""
        if series.dtype == "object":
            return pd.to_numeric(series, errors="coerce").fillna(0)
        return series.fillna(0)

    @staticmethod
    def load_work_orders():
        """Load work orders using SQLAlchemy model"""
        try:
            # Get all work orders and convert to DataFrame
            work_orders = WorkOrder.query.all()
            data = [wo.to_dict(include_items=False) for wo in work_orders]
            df = pd.DataFrame(data)

            # Convert column names to match your original script
            column_mapping = {
                "WorkOrderNo": "workorderid",
                "CustID": "custid",
                "DateIn": "datein",
                "DateCompleted": "datecompleted",
                "DateRequired": "daterequired",
                "RushOrder": "rushorder",
                "FirmRush": "firmrush",
                "StorageTime": "storagetime",
                "SpecialInstructions": "specialinstructions",
                "RepairsNeeded": "repairsneeded",
                "Clean": "clean",
                "Treat": "treat",
            }
            df = df.rename(columns=column_mapping)

            return df
        except Exception as e:
            print(f"Error loading work orders: {e}")
            return None

    @staticmethod
    def preprocess_data(df):
        """Preprocess the work order data with temporal augmentation

        This creates multiple training samples from each completed work order,
        simulating different stages of completion to prevent data leakage.
        """
        # Convert date columns
        date_cols = ["datein", "datecompleted", "daterequired", "clean", "treat"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # Calculate target variable
        df["days_to_complete"] = (df["datecompleted"] - df["datein"]).dt.days
        train_df = df.dropna(subset=["days_to_complete"]).copy()

        # Filter outliers
        mean_days = train_df["days_to_complete"].mean()
        std_days = train_df["days_to_complete"].std()
        train_df = train_df[
            (train_df["days_to_complete"] >= 0)
            & (train_df["days_to_complete"] <= mean_days + 3 * std_days)
        ].copy()

        # TEMPORAL AUGMENTATION: Create Stage 0 samples (no clean/treat info)
        # This matches the prediction scenario where we don't have progress dates yet
        # Previously used 3 stages (0, 1, 2) but Stage 1/2 diluted training signal
        augmented_samples = []

        for idx, row in train_df.iterrows():
            # Stage 0 ONLY: No clean or treat dates (matches prediction time)
            stage_0 = row.copy()
            stage_0["clean"] = pd.NaT
            stage_0["treat"] = pd.NaT
            stage_0["augmentation_stage"] = 0
            augmented_samples.append(stage_0)

        # Create augmented dataframe
        augmented_df = pd.DataFrame(augmented_samples).reset_index(drop=True)

        print(f"[AUGMENTATION] Original samples: {len(train_df)}")
        print(f"[AUGMENTATION] Stage 0 only (no clean/treat info): {len(augmented_df)}")
        print(f"[AUGMENTATION] This matches prediction scenario for better accuracy")

        return augmented_df

    @staticmethod
    def compute_recency_weights(df, scale=4.0):
        """Compute sample weights based on recency to bias toward recent data

        Args:
            df: DataFrame with 'datecompleted' column
            scale: Controls strength of recency bias (3-5 recommended)
                   Higher = stronger bias toward recent data

        Returns:
            Array of weights (same length as df)
        """
        # Calculate days since earliest completion
        df['datecompleted'] = pd.to_datetime(df['datecompleted'], errors='coerce')
        min_date = df['datecompleted'].min()
        max_date = df['datecompleted'].max()

        # Calculate normalized recency (0 to 1, where 1 = most recent)
        df['days_since_start'] = (df['datecompleted'] - min_date).dt.days
        max_days = (max_date - min_date).days

        if max_days == 0:
            # All samples from same day - equal weights
            return np.ones(len(df))

        # Normalize to 0-1 range
        recency_normalized = df['days_since_start'] / max_days

        # Exponential weighting: exp(recency * scale)
        # This gives stronger preference to recent data
        weights = np.exp(recency_normalized * scale)

        # Normalize so average weight = 1 (preserves scale of gradients)
        weights = weights / weights.mean()

        print(f"[RECENCY WEIGHTS] Scale: {scale}")
        print(f"[RECENCY WEIGHTS] Date range: {min_date.date()} to {max_date.date()}")
        print(f"[RECENCY WEIGHTS] Weight range: {weights.min():.3f} to {weights.max():.3f}")
        print(f"[RECENCY WEIGHTS] Recent data (last 20%) avg weight: {weights[recency_normalized > 0.8].mean():.3f}")
        print(f"[RECENCY WEIGHTS] Old data (first 20%) avg weight: {weights[recency_normalized < 0.2].mean():.3f}")

        return weights.values

    @staticmethod
    def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
        """Apply feature engineering to work order data"""
        from datetime import date
        today = pd.Timestamp.today()

        # --- Date parsing ---
        if "datein" in df.columns:
            df["datein"] = pd.to_datetime(df["datein"], errors="coerce")
        else:
            df["datein"] = pd.NaT

        if "daterequired" in df.columns:
            df["daterequired"] = pd.to_datetime(df["daterequired"], errors="coerce")
        else:
            df["daterequired"] = pd.NaT

        # --- Time-based features ---
        df["order_age"] = (today - df["datein"]).dt.days.fillna(0).astype(int)
        df["month_in"] = df["datein"].dt.month.fillna(0).astype(int)
        df["dow_in"] = df["datein"].dt.dayofweek.fillna(0).astype(int)
        df["quarter_in"] = df["datein"].dt.quarter.fillna(0).astype(int)
        df["is_weekend"] = (df["dow_in"] >= 5).astype(int)

        # --- Rush order features (now proper booleans) ---
        df["rushorder_binary"] = MLService.convert_to_binary(
            df.get("rushorder", pd.Series())
        )
        df["firmrush_binary"] = MLService.convert_to_binary(
            df.get("firmrush", pd.Series())
        )
        df["is_rush"] = df["rushorder_binary"] + df["firmrush_binary"]
        df["any_rush"] = (df["is_rush"] > 0).astype(int)

        # --- Text features ---
        df["instructions_len"] = (
            df.get("specialinstructions", "").fillna("").astype(str).apply(len)
        )
        df["has_special_instructions"] = (df["instructions_len"] > 0).astype(int)

        df["repairs_len"] = (
            df.get("repairsneeded", "").fillna("").astype(str).apply(len)
        )
        df["has_repairs_needed"] = (df["repairs_len"] > 0).astype(int)

        # --- Service features - REMOVED DATA LEAKAGE ---
        # Previously: used presence of clean/treat dates which leaked information
        # These dates only exist AFTER work is done, making predictions unrealistic
        # Now: Rely on other features that are known at work order creation time

        # --- Date requirement features ---
        df["has_required_date"] = df["daterequired"].notna().astype(int)
        df["days_until_required"] = 999  # default placeholder
        mask = df["daterequired"].notna() & df["datein"].notna()
        if mask.any():
            df.loc[mask, "days_until_required"] = (
                (df.loc[mask, "daterequired"].values - df.loc[mask, "datein"].values)
                .astype("timedelta64[D]")
                .astype(int)
            )

        # --- Customer features ---
        # NOTE: Customer stats (cust_mean, cust_std, cust_count) are calculated
        # AFTER train/test split to prevent data leakage. This function only
        # encodes customer IDs and creates placeholder columns.
        if "custid" in df.columns and df["custid"].nunique() > 1:
            le_cust = LabelEncoder()
            df["customer_encoded"] = le_cust.fit_transform(df["custid"].astype(str))

            # Create placeholder columns (will be filled after train/test split)
            df["cust_mean"] = 0.0
            df["cust_std"] = 0.0
            df["cust_count"] = 0
        else:
            df["customer_encoded"] = 0
            df["cust_mean"] = 0.0
            df["cust_std"] = 0.0
            df["cust_count"] = 0

        # --- Storage features ---
        df["storagetime_numeric"] = MLService.convert_to_numeric(
            df.get("storagetime", pd.Series())
        )
        df["storage_impact"] = df["storagetime_numeric"]

        return df

    @staticmethod
    def generate_daily_predictions(model, metadata):
        """Generate predictions for all open work orders and return DataFrame

        Args:
            model: Trained LightGBM model
            metadata: Model metadata containing feature columns and config info

        Returns:
            DataFrame with columns: workorderid, prediction_date, predicted_days,
                                   model_name, model_mae_at_train
        """
        df = MLService.load_work_orders()
        if df is None or df.empty:
            raise ValueError("No work orders found")

        # Only open orders (datecompleted is NULL)
        open_df = df[df["datecompleted"].isna()].copy()

        if open_df.empty:
            print("[DAILY PRED] No open work orders")
            return pd.DataFrame()

        # Prepare features
        open_df = MLService.engineer_features(open_df)
        feature_cols = metadata["feature_columns"]
        X = open_df[feature_cols].fillna(0)

        # Predict
        prediction_timestamp = datetime.now()
        open_df["predicted_days"] = model.predict(X)
        open_df["prediction_date"] = prediction_timestamp.strftime("%Y-%m-%d")
        open_df["model_name"] = metadata["config_name"]
        open_df["model_mae_at_train"] = metadata["mae"]

        # Track model training date to measure staleness
        open_df["model_trained_at"] = metadata.get("trained_at", prediction_timestamp.strftime("%Y-%m-%d %H:%M:%S"))

        # Calculate model age in days (for staleness tracking)
        model_trained_dt = pd.to_datetime(metadata.get("trained_at", prediction_timestamp))
        model_age_days = (prediction_timestamp - model_trained_dt).days
        open_df["model_age_days"] = model_age_days

        return open_df[[
            "workorderid", "prediction_date", "predicted_days",
            "model_name", "model_mae_at_train", "model_trained_at", "model_age_days"
        ]]


@ml_bp.route("/")
@login_required
def dashboard():
    return render_template("ml/dashboard.html")


# Replace your existing train_model route with this updated version


@ml_bp.route("/train", methods=["POST"])
@login_required
def train_model():
    """Train a new model"""
    # Store in cache after training (fixes #93 race condition)
    cache = _model_cache

    try:
        config_name = request.json.get("config", "optuna_best")
        config = MODEL_CONFIGS.get(config_name, MODEL_CONFIGS["optuna_best"])
        auto_save = request.json.get("auto_save", True)  # New parameter

        # Load data using the WorkOrder model
        df = MLService.load_work_orders()
        if df is None or df.empty:
            return jsonify({"error": "No data available for training"}), 400

        # Preprocess and engineer features
        train_df = MLService.preprocess_data(df)
        train_df = MLService.engineer_features(train_df)

        # Feature selection - NO DATA LEAKAGE
        # Removed: needs_cleaning, needs_treatment (only exist after work is done)
        # Removed: storage_impact (redundant with storagetime_numeric)
        # Removed: has_special_instructions (low importance, redundant with instructions_len)
        # Removed: order_age (causes train/predict mismatch - training sees aged orders, prediction sees age=0)
        feature_cols = [
            "rushorder_binary",
            "firmrush_binary",
            "storagetime_numeric",
            # "order_age",  # REMOVED - see above
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
        ]

        # Filter available features
        feature_cols = [col for col in feature_cols if col in train_df.columns]

        if len(feature_cols) == 0:
            return jsonify({"error": "No valid features found"}), 400

        X = train_df[feature_cols].fillna(0)
        y = train_df["days_to_complete"]

        if len(X) < 10:
            return jsonify({"error": "Insufficient training data"}), 400

        # Compute recency weights (bias toward recent completion patterns)
        # Reduced from 4.0 to 2.0 to avoid overfitting (4.0 gave 55x weight, 2.0 gives ~7x)
        sample_weights = MLService.compute_recency_weights(train_df, scale=2.0)

        # Train/test split (stratified by weights to preserve recency distribution)
        X_train, X_test, y_train, y_test, weights_train, weights_test = train_test_split(
            X, y, sample_weights, test_size=0.2, random_state=42
        )

        # FIX DATA LEAKAGE: Calculate customer stats using ONLY training data
        # (Previously calculated on entire dataset, causing 50x MAE inflation)
        if "custid" in train_df.columns and train_df["custid"].nunique() > 1:
            # Create temporary dataframe with training data + target
            train_with_target = pd.DataFrame({
                'custid': train_df.loc[X_train.index, 'custid'],
                'days_to_complete': y_train.values
            })

            # Calculate customer statistics from TRAINING data only
            train_cust_stats = train_with_target.groupby("custid")["days_to_complete"] \
                .agg(["mean", "std", "count"]) \
                .add_prefix("cust_")
            train_cust_stats["cust_std"] = train_cust_stats["cust_std"].fillna(0)

            # Apply to training set
            train_custids = train_df.loc[X_train.index, ['custid']]
            train_stats_merged = train_custids.merge(train_cust_stats, on='custid', how='left')
            X_train.loc[:, 'cust_mean'] = train_stats_merged['cust_mean'].fillna(0).values
            X_train.loc[:, 'cust_std'] = train_stats_merged['cust_std'].fillna(0).values
            X_train.loc[:, 'cust_count'] = train_stats_merged['cust_count'].fillna(0).values

            # Apply same stats to test set (using training stats, not test stats!)
            test_custids = train_df.loc[X_test.index, ['custid']]
            test_stats_merged = test_custids.merge(train_cust_stats, on='custid', how='left')
            X_test.loc[:, 'cust_mean'] = test_stats_merged['cust_mean'].fillna(0).values
            X_test.loc[:, 'cust_std'] = test_stats_merged['cust_std'].fillna(0).values
            X_test.loc[:, 'cust_count'] = test_stats_merged['cust_count'].fillna(0).values

            print(f"[CUSTOMER STATS] Calculated from {len(X_train)} training samples")
            print(f"[CUSTOMER STATS] Unique customers in train: {train_df.loc[X_train.index, 'custid'].nunique()}")
            print(f"[CUSTOMER STATS] Mean completion time range: {train_cust_stats['cust_mean'].min():.1f} to {train_cust_stats['cust_mean'].max():.1f} days")

        # Train model with recency weighting
        start_time = time.time()

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

        # Fit with sample weights to emphasize recent data
        model.fit(X_train, y_train, sample_weight=weights_train)
        training_time = time.time() - start_time

        # Evaluate
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))

        ss_res = np.sum((y_test - y_pred) ** 2)
        ss_tot = np.sum((y_test - np.mean(y_test)) ** 2)
        r2 = 1 - (ss_res / ss_tot)

        # Store model and update cache (fixes #93 race condition)
        current_model = model
        model_metadata = {
            "config_name": config_name,
            "training_time": round(training_time, 2),
            "mae": round(mae, 3),
            "rmse": round(rmse, 3),
            "r2": round(r2, 3),
            "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sample_count": len(X_train),
            "feature_columns": feature_cols,
        }

        # Update cache so this worker immediately uses new model
        cache["model"] = current_model
        cache["metadata"] = model_metadata
        cache["loaded_at"] = time.time()

        # Auto-save the model if requested
        save_result = None
        if auto_save:
            try:
                model_name = f"{config_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                save_metadata = model_metadata.copy()
                save_metadata["model_name"] = model_name
                save_result = save_ml_model(current_model, save_metadata, model_name)
            except Exception as save_error:
                print(f"Warning: Failed to auto-save model: {save_error}")

        response_data = {
            "message": "Model trained successfully",
            "metrics": {
                "mae": mae,
                "rmse": rmse,
                "r2": r2,
                "training_time": training_time,
                "samples": len(X_train),
            },
        }

        if save_result:
            response_data["saved"] = save_result

        return jsonify(response_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ml_bp.route("/predict", methods=["POST"])
@login_required
def predict():
    """Make a prediction"""
    # Use cached model (fixes #93 race condition)
    current_model, model_metadata = get_current_model()

    if current_model is None:
        return jsonify({"error": "No trained model available"}), 400

    try:
        data = request.json

        # Create a minimal DataFrame for feature engineering
        from datetime import date
        df = pd.DataFrame(
            [
                {
                    "custid": data.get("custid", "UNKNOWN"),
                    "datein": data.get("datein", date.today()),
                    "daterequired": data.get("daterequired"),
                    "rushorder": bool(data.get("rushorder", False)),
                    "firmrush": bool(data.get("firmrush", False)),
                    "storagetime": data.get("storagetime", 0),
                    "specialinstructions": data.get("specialinstructions", ""),
                    "repairsneeded": data.get("repairsneeded", ""),
                    "clean": data.get("clean"),  # Date object or None
                    "treat": data.get("treat"),  # Date object or None
                }
            ]
        )

        # Convert date columns properly
        df["datein"] = pd.to_datetime(df["datein"], errors="coerce")
        if data.get("daterequired"):
            df["daterequired"] = pd.to_datetime(
                data.get("daterequired"), errors="coerce"
            )
        else:
            df["daterequired"] = pd.NaT

        # Engineer features
        df = MLService.engineer_features(df)

        # Select features
        feature_cols = model_metadata.get("feature_columns", [])
        available_cols = [col for col in feature_cols if col in df.columns]

        if len(available_cols) == 0:
            return jsonify({"error": "No valid features available for prediction"}), 400

        X = df[available_cols].fillna(0)

        # Make prediction
        prediction = current_model.predict(X)[0]

        # Calculate completion date
        date_in = pd.to_datetime(data.get("datein"))
        completion_date = date_in + pd.Timedelta(days=prediction)

        return jsonify(
            {
                "predicted_days": round(prediction, 2),
                "confidence_interval": {
                    "lower": round(prediction - 1.5, 2),
                    "upper": round(prediction + 1.5, 2),
                },
                "estimated_completion": completion_date.strftime("%Y-%m-%d"),
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ml_bp.route("/batch_predict")
@login_required
def batch_predict():
    """Predict for all pending orders"""
    # Use cached model (fixes #93 race condition)
    current_model, model_metadata = get_current_model()

    if current_model is None:
        return jsonify({"error": "No trained model available"}), 400

    try:
        # Get pending work orders (DateCompleted is now DateTime, not string)
        pending_orders = (
            WorkOrder.query.filter(WorkOrder.DateCompleted.is_(None))
            .limit(50)
            .all()
        )

        if not pending_orders:
            # Try alternative query
            all_orders = WorkOrder.query.limit(10).all()
            log_msg = f"No pending orders found. Total orders in DB: {WorkOrder.query.count()}"
            return jsonify({"message": log_msg, "results": []})

        results = []
        for order in pending_orders:
            try:
                # Create prediction data with proper data types
                from datetime import date
                data = {
                    "custid": order.CustID or "UNKNOWN",
                    "datein": order.DateIn or date.today(),  # Now a date object
                    "daterequired": order.DateRequired,  # Already a date object or None
                    "rushorder": bool(order.RushOrder),  # Now a boolean
                    "firmrush": bool(order.FirmRush),  # Now a boolean
                    "storagetime": order.StorageTime or 0,
                    "specialinstructions": order.SpecialInstructions or "",
                    "repairsneeded": order.RepairsNeeded or "",
                    "clean": order.Clean,  # Date object or None (when cleaning completed)
                    "treat": order.Treat,  # Date object or None (when treatment completed)
                }

                # Make prediction with better error handling
                df = pd.DataFrame([data])

                # Ensure proper datetime conversion
                df["datein"] = pd.to_datetime(df["datein"], errors="coerce")
                if df["daterequired"].iloc[0]:
                    df["daterequired"] = pd.to_datetime(
                        df["daterequired"], errors="coerce"
                    )
                else:
                    df["daterequired"] = pd.NaT

                df = MLService.engineer_features(df)
                feature_cols = model_metadata.get("feature_columns", [])
                available_cols = [col for col in feature_cols if col in df.columns]

                if len(available_cols) == 0:
                    continue

                X = df[available_cols].fillna(0)
                prediction = current_model.predict(X)[0]

                results.append(
                    {
                        "work_order": order.WorkOrderNo,
                        "customer": order.CustID,
                        "date_in": order.DateIn,
                        "predicted_days": round(prediction),
                        "rush_order": bool(order.RushOrder),
                        "instructions": (order.SpecialInstructions or "")[:100],
                    }
                )

            except Exception as e:
                print(f"Error predicting for order {order.WorkOrderNo}: {e}")
                continue

        return jsonify(
            {"message": f"Processed {len(results)} orders", "results": results}
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ml_bp.route("/predict/<int:work_order_no>")
@login_required
def predict_work_order(work_order_no):
    """Predict estimated completion days for a specific work order"""
    # Use cached model (fixes #93 race condition)
    current_model, model_metadata = get_current_model()

    if current_model is None:
        return jsonify({"error": "No trained model available"}), 400

    # Fetch the order
    order = WorkOrder.query.filter_by(WorkOrderNo=str(work_order_no)).first()
    if not order:
        return jsonify({"error": f"Work order {work_order_no} not found"}), 404

    try:
        # Build input data with proper data types
        from datetime import date
        data = {
            "custid": order.CustID or "UNKNOWN",
            "datein": order.DateIn or date.today(),  # Now a date object
            "daterequired": order.DateRequired,  # Already a date object or None
            "rushorder": bool(order.RushOrder),  # Now a boolean
            "firmrush": bool(order.FirmRush),  # Now a boolean
            "storagetime": order.StorageTime or 0,
            "specialinstructions": order.SpecialInstructions or "",
            "repairsneeded": order.RepairsNeeded or "",
            "clean": order.Clean,  # Date object or None (when cleaning completed)
            "treat": order.Treat,  # Date object or None (when treatment completed)
        }

        # Convert to DataFrame
        df = pd.DataFrame([data])
        df["datein"] = pd.to_datetime(df["datein"], errors="coerce")
        if df["daterequired"].iloc[0]:
            df["daterequired"] = pd.to_datetime(df["daterequired"], errors="coerce")
        else:
            df["daterequired"] = pd.NaT

        # Feature engineering
        df = MLService.engineer_features(df)
        feature_cols = model_metadata.get("feature_columns", [])
        available_cols = [col for col in feature_cols if col in df.columns]

        if not available_cols:
            return jsonify({"error": "No valid features for prediction"}), 400

        X = df[available_cols].fillna(0)

        # Predict
        prediction = current_model.predict(X)[0]
        completion_date = pd.to_datetime(order.DateIn) + pd.Timedelta(days=prediction)

        return jsonify(
            {
                "work_order": work_order_no,
                "predicted_days": round(float(prediction)),
                "estimated_completion": completion_date.strftime("%Y-%m-%d"),
                "confidence_interval": {
                    "lower": round(float(prediction) - 1.5, 2),
                    "upper": round(float(prediction) + 1.5, 2),
                },
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ml_bp.route("/status")
@login_required
def status():
    """Get current model status"""
    # Use cached model (fixes #93 race condition)
    current_model, model_metadata = get_current_model()

    return jsonify(
        {
            "trained": current_model is not None,
            "metadata": model_metadata,
            "available_configs": list(MODEL_CONFIGS.keys()),
        }
    )


@ml_bp.route("/predict_daily", methods=["POST"])
@login_required
def predict_daily():
    """Generate and save daily predictions for all open work orders (requires login)"""
    model, metadata = get_current_model()

    if model is None:
        return jsonify({"error": "No model loaded"}), 400

    try:
        df = MLService.generate_daily_predictions(model, metadata)

        if df.empty:
            return jsonify({"message": "No open work orders to predict"}), 200

        key = save_daily_prediction_file(df)

        return jsonify({
            "message": "Daily predictions saved",
            "records": len(df),
            "s3_key": key,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ml_bp.route("/cron/predict_daily", methods=["POST"])
def cron_predict_daily():
    """Cron endpoint for daily predictions (uses secret token instead of login)"""
    # Simple security: check for a secret key
    secret = request.headers.get("X-Cron-Secret") or (request.json or {}).get("secret")
    expected_secret = os.getenv("CRON_SECRET", "your-secret-key")

    if secret != expected_secret:
        return jsonify({"error": "Unauthorized - invalid cron secret"}), 401

    model, metadata = get_current_model()

    if model is None:
        return jsonify({"error": "No model loaded"}), 400

    try:
        start_timestamp = datetime.now()
        print(f"[CRON DAILY PRED] Starting at {start_timestamp}")

        df = MLService.generate_daily_predictions(model, metadata)

        if df.empty:
            print("[CRON DAILY PRED] No open work orders to predict")
            return jsonify({
                "message": "No open work orders to predict",
                "timestamp": start_timestamp.isoformat()
            }), 200

        key = save_daily_prediction_file(df)

        end_timestamp = datetime.now()
        total_time = (end_timestamp - start_timestamp).total_seconds()

        print(f"[CRON DAILY PRED] Completed successfully in {total_time:.2f} seconds")
        print(f"[CRON DAILY PRED] Generated predictions for {len(df)} work orders")
        print(f"[CRON DAILY PRED] Saved to: {key}")

        return jsonify({
            "message": "Daily predictions saved",
            "records": len(df),
            "s3_key": key,
            "timestamp": end_timestamp.isoformat(),
            "execution_time_seconds": total_time
        })

    except Exception as e:
        error_timestamp = datetime.now()
        error_msg = str(e)
        print(f"[CRON DAILY PRED] ERROR at {error_timestamp}: {error_msg}")

        return jsonify({
            "error": error_msg,
            "timestamp": error_timestamp.isoformat()
        }), 500


@ml_bp.route("/evaluate_snapshots", methods=["GET"])
@login_required
def evaluate_snapshots():
    """Evaluate all weekly prediction snapshots against realized completion times"""
    from utils.file_upload import s3_client, AWS_S3_BUCKET
    from io import BytesIO

    try:
        # List all prediction snapshot files in S3
        response = s3_client.list_objects_v2(
            Bucket=AWS_S3_BUCKET,
            Prefix="ml_predictions/weekly_"
        )

        if "Contents" not in response:
            return jsonify({
                "message": "No prediction snapshots found",
                "evaluations": []
            })

        # Get all snapshot files, sorted by date
        snapshot_files = sorted(
            [obj for obj in response["Contents"] if obj["Key"].endswith(".csv")],
            key=lambda x: x["LastModified"],
            reverse=True
        )

        # Load current work order data
        current_df = MLService.load_work_orders()
        if current_df is None or current_df.empty:
            return jsonify({"error": "No work order data available"}), 400

        # Convert date columns
        current_df["datein"] = pd.to_datetime(current_df["datein"], errors="coerce")
        current_df["datecompleted"] = pd.to_datetime(current_df["datecompleted"], errors="coerce")

        # Filter out invalid dates (bad data like 7777-07-07, 2111-11-11, etc.)
        min_valid_date = pd.Timestamp('2000-01-01')
        max_valid_date = pd.Timestamp.now() + pd.Timedelta(days=365)

        current_df = current_df[
            (current_df["datecompleted"].isna()) |
            ((current_df["datecompleted"] >= min_valid_date) &
             (current_df["datecompleted"] <= max_valid_date))
        ].copy()

        current_df = current_df[
            (current_df["datein"].isna()) |
            ((current_df["datein"] >= min_valid_date) &
             (current_df["datein"] <= max_valid_date))
        ].copy()

        # Evaluate each snapshot
        evaluations = []
        for snapshot_obj in snapshot_files:
            try:
                # Download snapshot from S3
                snapshot_key = snapshot_obj["Key"]
                snapshot_buffer = BytesIO()
                s3_client.download_fileobj(AWS_S3_BUCKET, snapshot_key, snapshot_buffer)
                snapshot_buffer.seek(0)

                # Read snapshot CSV
                snapshot_df = pd.read_csv(snapshot_buffer)

                # Evaluate this snapshot
                eval_result = evaluate_snapshot(snapshot_df, current_df)

                if eval_result:
                    eval_result["snapshot_file"] = snapshot_key
                    eval_result["snapshot_created"] = snapshot_obj["LastModified"].isoformat()
                    evaluations.append(eval_result)

            except Exception as e:
                print(f"[EVAL] Error evaluating snapshot {snapshot_key}: {e}")
                continue

        return jsonify({
            "message": f"Evaluated {len(evaluations)} snapshots",
            "total_snapshots": len(snapshot_files),
            "evaluations": evaluations
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ml_bp.route("/performance_dashboard")
@login_required
def performance_dashboard():
    """Dashboard showing model performance over time with statistical rigor"""
    from utils.file_upload import s3_client, AWS_S3_BUCKET
    from io import BytesIO
    from scipy import stats
    import plotly.graph_objs as go
    import plotly.utils

    try:
        # List both daily and legacy weekly prediction snapshot files in S3
        daily_response = s3_client.list_objects_v2(
            Bucket=AWS_S3_BUCKET,
            Prefix="ml_predictions/daily_"
        )
        
        weekly_response = s3_client.list_objects_v2(
            Bucket=AWS_S3_BUCKET,
            Prefix="ml_predictions/weekly_"
        )

        all_contents = []
        if "Contents" in daily_response:
            all_contents.extend(daily_response["Contents"])
        if "Contents" in weekly_response:
            all_contents.extend(weekly_response["Contents"])

        if not all_contents:
            flash("No prediction snapshots found yet. Daily predictions will be generated automatically.", "info")
            return render_template("ml/performance_dashboard.html", chart_json=None, stats=None)

        # Get all snapshot files, sorted by date
        snapshot_files = sorted(
            [obj for obj in all_contents if obj["Key"].endswith(".csv")],
            key=lambda x: x["LastModified"]
        )

        # Load current work order data
        current_df = MLService.load_work_orders()
        if current_df is None or current_df.empty:
            flash("No work order data available", "error")
            return render_template("ml/performance_dashboard.html", chart_json=None, stats=None)

        # Convert workorderid to string for merge compatibility (database uses VARCHAR)
        current_df["workorderid"] = current_df["workorderid"].astype(str)

        # Convert date columns
        current_df["datein"] = pd.to_datetime(current_df["datein"], errors="coerce")
        current_df["datecompleted"] = pd.to_datetime(current_df["datecompleted"], errors="coerce")

        # Filter out invalid dates (bad data like 7777-07-07, 2111-11-11, etc.)
        min_valid_date = pd.Timestamp('2000-01-01')
        max_valid_date = pd.Timestamp.now() + pd.Timedelta(days=365)

        # Only keep work orders with valid completion dates
        current_df = current_df[
            (current_df["datecompleted"].isna()) |  # Keep open orders
            ((current_df["datecompleted"] >= min_valid_date) &
             (current_df["datecompleted"] <= max_valid_date))  # Or valid completed dates
        ].copy()

        # Also filter datein (should be reasonable)
        current_df = current_df[
            (current_df["datein"].isna()) |
            ((current_df["datein"] >= min_valid_date) &
             (current_df["datein"] <= max_valid_date))
        ].copy()

        # Evaluate each snapshot and collect detailed error data
        time_series_data = []
        for snapshot_obj in snapshot_files:
            try:
                # Download snapshot from S3
                snapshot_key = snapshot_obj["Key"]
                snapshot_buffer = BytesIO()
                s3_client.download_fileobj(AWS_S3_BUCKET, snapshot_key, snapshot_buffer)
                snapshot_buffer.seek(0)

                # Read snapshot CSV
                snapshot_df = pd.read_csv(snapshot_buffer)

                # Convert workorderid to string for merge compatibility (CSV files have integers)
                snapshot_df["workorderid"] = snapshot_df["workorderid"].astype(str)

                # Merge with current data to get actuals
                merged = snapshot_df.merge(
                    current_df[["workorderid", "datein", "datecompleted"]],
                    on="workorderid",
                    how="left"
                )

                # Calculate actual days to complete
                merged["actual_days"] = (
                    merged["datecompleted"] - merged["datein"]
                ).dt.days

                # Only evaluate orders that now have completion data
                eval_df = merged.dropna(subset=["actual_days"])

                if eval_df.empty:
                    continue

                # Calculate errors for this snapshot
                errors = eval_df["actual_days"] - eval_df["predicted_days"]
                abs_errors = np.abs(errors)

                # Statistical calculations
                n = len(eval_df)
                mae = abs_errors.mean()
                rmse = np.sqrt((errors ** 2).mean())

                # Standard error of the mean (SEM) for MAE
                # Using bootstrap-based standard error estimation
                std_error = abs_errors.std() / np.sqrt(n)

                # 95% confidence interval for MAE (t-distribution for small samples)
                if n > 1:
                    confidence_level = 0.95
                    t_critical = stats.t.ppf((1 + confidence_level) / 2, df=n-1)
                    ci_lower = mae - t_critical * std_error
                    ci_upper = mae + t_critical * std_error
                else:
                    ci_lower = mae
                    ci_upper = mae

                # Extract date from snapshot filename (handle both daily_ and weekly_ prefixes)
                date_str = snapshot_key.replace("ml_predictions/daily_", "").replace("ml_predictions/weekly_", "").replace(".csv", "")

                # Calculate completion percentage
                total_predictions = len(snapshot_df)
                completion_pct = (n / total_predictions * 100) if total_predictions > 0 else 0

                time_series_data.append({
                    "date": date_str,
                    "mae": mae,
                    "rmse": rmse,
                    "n": n,
                    "total_predictions": total_predictions,
                    "completion_pct": completion_pct,
                    "std_error": std_error,
                    "ci_lower": max(0, ci_lower),  # MAE can't be negative
                    "ci_upper": ci_upper,
                    "model_name": snapshot_df["model_name"].iloc[0] if "model_name" in snapshot_df else "unknown"
                })

            except Exception as e:
                print(f"[DASHBOARD] Error processing snapshot {snapshot_key}: {e}")
                continue

        if not time_series_data:
            flash("No completed work orders found in snapshots yet. Check back after some orders finish.", "info")
            return render_template("ml/performance_dashboard.html", chart_json=None, stats=None)

        # Create DataFrame for plotting
        ts_df = pd.DataFrame(time_series_data)
        ts_df["date"] = pd.to_datetime(ts_df["date"])
        ts_df = ts_df.sort_values("date")

        # Log dataframe for debugging
        from flask import current_app
        current_app.logger.info("--- DataFrame for Charting ---")
        current_app.logger.info(ts_df[["date", "mae", "rmse", "n"]].to_string())
        current_app.logger.info("------------------------------")

        # Create Plotly figure with error bars
        fig = go.Figure()

        # Add MAE line with confidence intervals
        fig.add_trace(go.Scatter(
            x=ts_df["date"],
            y=ts_df["mae"],
            mode='lines+markers',
            name='MAE (Mean Absolute Error)',
            line=dict(color='rgb(31, 119, 180)', width=2),
            marker=dict(size=8),
            customdata=ts_df[["n", "total_predictions", "completion_pct"]],
            hovertemplate='<b>Date:</b> %{x|%Y-%m-%d}<br>' +
                         '<b>MAE:</b> %{y:.2f} days<br>' +
                         '<b>Completed:</b> %{customdata[0]} / %{customdata[1]}<br>' +
                         '<b>Completion Rate:</b> %{customdata[2]:.1f}%<br>' +
                         '<extra></extra>'
        ))

        # Add confidence interval shading
        fig.add_trace(go.Scatter(
            x=pd.concat([ts_df["date"], ts_df["date"][::-1]]),
            y=pd.concat([ts_df["ci_upper"], ts_df["ci_lower"][::-1]]),
            fill='toself',
            fillcolor='rgba(31, 119, 180, 0.2)',
            line=dict(color='rgba(255,255,255,0)'),
            hoverinfo="skip",
            showlegend=True,
            name='95% Confidence Interval'
        ))

        # Add RMSE line
        fig.add_trace(go.Scatter(
            x=ts_df["date"],
            y=ts_df["rmse"],
            mode='lines+markers',
            name='RMSE (Root Mean Squared Error)',
            line=dict(color='rgb(255, 127, 14)', width=2, dash='dash'),
            marker=dict(size=8),
            customdata=ts_df[["n", "total_predictions", "completion_pct"]],
            hovertemplate='<b>Date:</b> %{x|%Y-%m-%d}<br>' +
                         '<b>RMSE:</b> %{y:.2f} days<br>' +
                         '<b>Completed:</b> %{customdata[0]} / %{customdata[1]}<br>' +
                         '<b>Completion Rate:</b> %{customdata[2]:.1f}%<br>' +
                         '<extra></extra>'
        ))

        # Update layout
        fig.update_layout(
            title='Model Performance Over Time (Realized Prediction Accuracy)',
            xaxis_title='Snapshot Date',
            yaxis_title='Error (days)',
            hovermode='closest',  # Show custom tooltips with completion %
            template='plotly_white',
            height=500,
            legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.8)')
        )

        # Add annotations for sample sizes
        for i, row in ts_df.iterrows():
            fig.add_annotation(
                x=row["date"],
                y=row["mae"],
                text=f"n={row['n']}",
                showarrow=False,
                yshift=15,
                font=dict(size=9, color='gray')
            )

        # === ENHANCED METRICS FOR NIGHTLY RETRAINED MODELS ===

        # 1. Performance by Model Training Date (are newer models better?)
        model_performance = {}
        all_evaluated_predictions = []

        for snapshot_obj in snapshot_files:
            try:
                snapshot_key = snapshot_obj["Key"]
                snapshot_buffer = BytesIO()
                s3_client.download_fileobj(AWS_S3_BUCKET, snapshot_key, snapshot_buffer)
                snapshot_buffer.seek(0)
                snapshot_df = pd.read_csv(snapshot_buffer)
                snapshot_df["workorderid"] = snapshot_df["workorderid"].astype(str)

                # Merge with current data
                merged = snapshot_df.merge(
                    current_df[["workorderid", "datein", "datecompleted"]],
                    on="workorderid",
                    how="left"
                )
                merged["actual_days"] = (merged["datecompleted"] - pd.to_datetime(merged["datein"])).dt.days
                eval_df = merged.dropna(subset=["actual_days"])

                if not eval_df.empty:
                    all_evaluated_predictions.append(eval_df)

                    # Track by model training date
                    if "model_trained_at" in eval_df.columns:
                        model_date = eval_df["model_trained_at"].iloc[0]
                        if model_date not in model_performance:
                            model_performance[model_date] = []
                        errors = np.abs(eval_df["actual_days"] - eval_df["predicted_days"])
                        model_performance[model_date].extend(errors.tolist())
            except Exception as e:
                continue

        # Aggregate model performance
        model_stats = []
        for model_date, errors in sorted(model_performance.items()):
            model_stats.append({
                "model_trained_at": model_date,
                "mae": round(np.mean(errors), 3),
                "n_predictions": len(errors),
                "std": round(np.std(errors), 3)
            })

        # 2. Calibration Metrics (coverage analysis)
        calibration_stats = None
        if all_evaluated_predictions:
            all_eval = pd.concat(all_evaluated_predictions, ignore_index=True)

            # Assuming ±1.5 days confidence interval (from /predict route)
            ci_width = 1.5
            all_eval["within_ci"] = np.abs(all_eval["actual_days"] - all_eval["predicted_days"]) <= ci_width

            coverage_rate = all_eval["within_ci"].mean() * 100
            mean_abs_error = np.abs(all_eval["actual_days"] - all_eval["predicted_days"]).mean()

            calibration_stats = {
                "coverage_rate_pct": round(coverage_rate, 1),
                "expected_coverage_pct": 68.0,  # ±1.5 days ~1 std dev
                "is_well_calibrated": abs(coverage_rate - 68.0) < 10,  # Within 10% of expected
                "mean_abs_error": round(mean_abs_error, 2),
                "total_predictions_evaluated": len(all_eval)
            }

        # 3. Model Staleness Analysis (if model_age_days available)
        staleness_stats = None
        if all_evaluated_predictions and any("model_age_days" in df.columns for df in all_evaluated_predictions):
            all_eval = pd.concat(all_evaluated_predictions, ignore_index=True)
            if "model_age_days" in all_eval.columns:
                all_eval["abs_error"] = np.abs(all_eval["actual_days"] - all_eval["predicted_days"])

                # Group by model age
                staleness_by_age = all_eval.groupby("model_age_days")["abs_error"].agg(["mean", "count"]).reset_index()
                staleness_by_age.columns = ["model_age_days", "mae", "n"]

                staleness_stats = {
                    "by_age": staleness_by_age.to_dict("records"),
                    "correlation": None
                }

                # Calculate correlation between model age and error
                if len(staleness_by_age) > 1:
                    from scipy.stats import pearsonr
                    corr, p_val = pearsonr(staleness_by_age["model_age_days"], staleness_by_age["mae"])
                    staleness_stats["correlation"] = {
                        "coefficient": round(corr, 3),
                        "p_value": round(p_val, 3),
                        "interpretation": "Performance degrades as model ages" if corr > 0.3 and p_val < 0.05
                                         else "No significant degradation with age"
                    }

        # Calculate convergence statistics
        if len(ts_df) >= 3:
            # Linear regression to detect trend
            x_numeric = np.arange(len(ts_df))
            slope, intercept, r_value, p_value, std_err = stats.linregress(x_numeric, ts_df["mae"])

            trend_direction = "improving" if slope < 0 else "degrading" if slope > 0 else "stable"
            is_significant = p_value < 0.05

            convergence_stats = {
                "trend_direction": trend_direction,
                "slope": round(slope, 4),
                "p_value": round(p_value, 4),
                "is_significant": is_significant,
                "r_squared": round(r_value ** 2, 4),
                "interpretation": f"MAE is {trend_direction} at {abs(slope):.3f} days per week" +
                                 (f" (statistically significant, p={p_value:.3f})" if is_significant else
                                  f" (not statistically significant, p={p_value:.3f})")
            }
        else:
            convergence_stats = {
                "trend_direction": "insufficient data",
                "interpretation": "Need at least 3 snapshots to detect trends"
            }

        # Summary statistics
        summary_stats = {
            "total_snapshots": len(ts_df),
            "latest_mae": round(ts_df.iloc[-1]["mae"], 3),
            "latest_rmse": round(ts_df.iloc[-1]["rmse"], 3),
            "latest_n": int(ts_df.iloc[-1]["n"]),
            "latest_ci": f"[{ts_df.iloc[-1]['ci_lower']:.2f}, {ts_df.iloc[-1]['ci_upper']:.2f}]",
            "mean_mae": round(ts_df["mae"].mean(), 3),
            "std_mae": round(ts_df["mae"].std(), 3),
            "convergence": convergence_stats
        }

        # Convert plot to JSON for template
        chart_json = plotly.utils.PlotlyJSONEncoder().encode(fig)

        return render_template("ml/performance_dashboard.html",
                             chart_json=chart_json,
                             stats=summary_stats,
                             time_series=ts_df.to_dict('records'))

    except Exception as e:
        print(f"[DASHBOARD] Error: {e}")
        import traceback
        traceback.print_exc()
        flash(f"Error loading dashboard: {str(e)}", "error")
        return render_template("ml/performance_dashboard.html", chart_json=None, stats=None)


# Add this route to your ml_bp blueprint


@ml_bp.route("/cron/retrain", methods=["POST"])
def cron_retrain():
    """Special endpoint for cron jobs - trains on ALL data without test holdout"""

    # Simple security: check for a secret key
    secret = request.headers.get("X-Cron-Secret") or (request.json or {}).get("secret")
    expected_secret = os.getenv("CRON_SECRET", "your-secret-key")

    if secret != expected_secret:
        return jsonify({"error": "Unauthorized - invalid cron secret"}), 401

    global current_model, model_metadata

    try:
        # Get configuration from request or use default
        request_data = request.json or {}
        config_name = request_data.get("config", "optuna_best")
        config = MODEL_CONFIGS.get(config_name, MODEL_CONFIGS["optuna_best"])

        # Log the start of training
        start_timestamp = datetime.now()
        print(f"[CRON RETRAIN] Starting at {start_timestamp}")

        # Load data using the WorkOrder model
        df = MLService.load_work_orders()
        if df is None or df.empty:
            error_msg = "No data available for training"
            print(f"[CRON RETRAIN] ERROR: {error_msg}")
            return jsonify(
                {"error": error_msg, "timestamp": start_timestamp.isoformat()}
            ), 400

        # Preprocess and engineer features
        train_df = MLService.preprocess_data(df)
        train_df = MLService.engineer_features(train_df)

        print(f"[CRON RETRAIN] Preprocessed data: {len(train_df)} samples")

        # Feature selection - NO DATA LEAKAGE (same as regular training)
        # Removed: needs_cleaning, needs_treatment (only exist after work is done)
        # Removed: storage_impact (redundant with storagetime_numeric)
        # Removed: has_special_instructions (low importance, redundant with instructions_len)
        # Removed: order_age (causes train/predict mismatch - training sees aged orders, prediction sees age=0)
        feature_cols = [
            "rushorder_binary",
            "firmrush_binary",
            "storagetime_numeric",
            # "order_age",  # REMOVED - see above
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
        ]

        # Filter available features
        feature_cols = [col for col in feature_cols if col in train_df.columns]

        if len(feature_cols) == 0:
            error_msg = "No valid features found"
            print(f"[CRON RETRAIN] ERROR: {error_msg}")
            return jsonify(
                {"error": error_msg, "timestamp": start_timestamp.isoformat()}
            ), 400

        # Calculate customer stats on FULL dataset (no data leakage concern for cron - no test set)
        # For cron retrain, we train on ALL data, so we calculate stats on the full dataset
        if "custid" in train_df.columns and train_df["custid"].nunique() > 1:
            # Calculate customer statistics from ALL training data
            cust_stats = train_df.groupby("custid")["days_to_complete"] \
                .agg(["mean", "std", "count"]) \
                .add_prefix("cust_")
            cust_stats["cust_std"] = cust_stats["cust_std"].fillna(0)

            # Merge customer stats back into train_df
            train_df = train_df.merge(cust_stats, on='custid', how='left', suffixes=('', '_new'))

            # Update the placeholder columns with real values
            train_df["cust_mean"] = train_df["cust_mean_new"].fillna(0)
            train_df["cust_std"] = train_df["cust_std_new"].fillna(0)
            train_df["cust_count"] = train_df["cust_count_new"].fillna(0)

            # Drop the temporary columns
            train_df = train_df.drop(columns=['cust_mean_new', 'cust_std_new', 'cust_count_new'])

            print(f"[CRON CUSTOMER STATS] Calculated from {len(train_df)} samples")
            print(f"[CRON CUSTOMER STATS] Unique customers: {train_df['custid'].nunique()}")
            print(f"[CRON CUSTOMER STATS] Mean completion time range: {cust_stats['cust_mean'].min():.1f} to {cust_stats['cust_mean'].max():.1f} days")

        # Prepare ALL data for training (no test holdout for cron job)
        X = train_df[feature_cols].fillna(0)
        y = train_df["days_to_complete"]

        if len(X) < 10:
            error_msg = f"Insufficient training data: only {len(X)} samples"
            print(f"[CRON RETRAIN] ERROR: {error_msg}")
            return jsonify(
                {"error": error_msg, "timestamp": start_timestamp.isoformat()}
            ), 400

        # Compute recency weights (bias toward recent completion patterns)
        # Reduced from 4.0 to 2.0 to avoid overfitting (4.0 gave 55x weight, 2.0 gives ~7x)
        sample_weights = MLService.compute_recency_weights(train_df, scale=2.0)

        print(
            f"[CRON RETRAIN] Training on ALL {len(X)} samples with {len(feature_cols)} features (recency-weighted)"
        )

        # Train model on ALL available data with recency weighting
        training_start_time = time.time()

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

        # Fit on ALL data with sample weights to emphasize recent patterns
        model.fit(X, y, sample_weight=sample_weights)
        training_time = time.time() - training_start_time

        print(f"[CRON RETRAIN] Model training completed in {training_time:.2f} seconds")

        # Calculate training metrics (on the same data used for training)
        y_pred = model.predict(X)
        mae = mean_absolute_error(y, y_pred)
        rmse = np.sqrt(mean_squared_error(y, y_pred))

        # Calculate R²
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        print(
            f"[CRON RETRAIN] Training metrics - MAE: {mae:.3f}, RMSE: {rmse:.3f}, R²: {r2:.3f}"
        )

        # Store model globally and update cache (fixes #93 race condition)
        cache = _model_cache
        current_model = model
        model_metadata = {
            "config_name": config_name,
            "training_time": round(training_time, 2),
            "mae": round(mae, 3),
            "rmse": round(rmse, 3),
            "r2": round(r2, 3),
            "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sample_count": len(X),
            "feature_columns": feature_cols,
            "training_type": "cron_full_data",  # Distinguish from regular training
            "data_version": start_timestamp.strftime("%Y%m%d_%H%M%S"),
        }

        # Update cache so this worker immediately uses new model
        cache["model"] = current_model
        cache["metadata"] = model_metadata
        cache["loaded_at"] = time.time()

        # Auto-save the model with timestamp
        model_name = f"cron_{config_name}_{start_timestamp.strftime('%Y%m%d_%H%M%S')}"
        save_metadata = model_metadata.copy()
        save_metadata["model_name"] = model_name
        save_metadata["auto_saved"] = True

        try:
            save_result = save_ml_model(current_model, save_metadata, model_name)
            print(f"[CRON RETRAIN] Model saved successfully as: {model_name}")
            save_success = True
        except Exception as save_error:
            print(f"[CRON RETRAIN] WARNING: Failed to save model: {save_error}")
            save_result = None
            save_success = False

        end_timestamp = datetime.now()
        total_time = (end_timestamp - start_timestamp).total_seconds()

        print(f"[CRON RETRAIN] Completed successfully in {total_time:.2f} seconds")

        # Return success response
        response_data = {
            "message": "Cron retrain completed successfully",
            "timestamp": end_timestamp.isoformat(),
            "config_used": config_name,
            "training_metrics": {
                "mae": mae,
                "rmse": rmse,
                "r2": r2,
                "training_time_seconds": training_time,
                "total_time_seconds": total_time,
                "samples_trained": len(X),
                "features_used": len(feature_cols),
            },
            "model_saved": save_success,
            "model_name": model_name if save_success else None,
        }

        if save_result:
            response_data["save_details"] = save_result
        
        if save_success:
            try:
                cleanup_old_s3_models(keep=5)
                print("[CRON RETRAIN] Old models cleaned up successfully.")
            except Exception as cleanup_error:
                print(f"[CRON RETRAIN] WARNING: Failed to clean up old models: {cleanup_error}")


        return jsonify(response_data)

    except Exception as e:
        error_timestamp = datetime.now()
        error_msg = str(e)
        print(f"[CRON RETRAIN] EXCEPTION at {error_timestamp}: {error_msg}")

        return jsonify(
            {
                "error": error_msg,
                "timestamp": error_timestamp.isoformat(),
                "training_type": "cron_full_data",
            }
        ), 500


def cleanup_old_s3_models(keep=5):
    """Clean up old cron models in S3, keeping the specified number of newest models."""
    from utils.file_upload import s3_client, AWS_S3_BUCKET

    print(f"[S3 CLEANUP] Starting cleanup, keeping the {keep} newest cron models.")

    # List all objects in the ml_models/ prefix
    response = s3_client.list_objects_v2(
        Bucket=AWS_S3_BUCKET,
        Prefix="ml_models/cron_"
    )

    if "Contents" not in response:
        print("[S3 CLEANUP] No cron models found to clean up.")
        return

    # Filter for .pkl files and sort by date
    cron_models = sorted(
        [obj for obj in response["Contents"] if obj["Key"].endswith(".pkl")],
        key=lambda x: x["LastModified"],
        reverse=True
    )

    if len(cron_models) <= keep:
        print(f"[S3 CLEANUP] Found {len(cron_models)} models, which is within the limit of {keep}. No cleanup needed.")
        return

    # Identify models to delete
    models_to_delete = cron_models[keep:]
    print(f"[S3 CLEANUP] Found {len(cron_models)} models. Deleting {len(models_to_delete)} old models.")

    # Create a list of objects to delete
    delete_keys = []
    for model_obj in models_to_delete:
        model_key = model_obj["Key"]
        metadata_key = model_key.replace(".pkl", "_metadata.json")
        delete_keys.extend([{"Key": model_key}, {"Key": metadata_key}])
        print(f"[S3 CLEANUP] Marking for deletion: {model_key}")

    # Batch delete the objects
    if delete_keys:
        delete_response = s3_client.delete_objects(
            Bucket=AWS_S3_BUCKET,
            Delete={'Objects': delete_keys}
        )
        if 'Errors' in delete_response:
            print(f"[S3 CLEANUP] ERROR: Failed to delete some objects: {delete_response['Errors']}")
        else:
            print(f"[S3 CLEANUP] Successfully deleted {len(models_to_delete)} models and their metadata.")


def save_daily_prediction_file(df):
    """Save daily predictions to S3
    
    Args:
        df: DataFrame with prediction results
        
    Returns:
        str: S3 key where the file was saved
    """
    from utils.file_upload import s3_client, AWS_S3_BUCKET
    import io

    date_str = datetime.now().strftime("%Y-%m-%d")
    key = f"ml_predictions/daily_{date_str}.csv"

    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)

    s3_client.put_object(
        Bucket=AWS_S3_BUCKET,
        Key=key,
        Body=buffer.getvalue(),
        ContentType="text/csv"
    )

    print(f"[DAILY PRED] Saved prediction file: {key}")
    return key


def evaluate_snapshot(snapshot_df, current_df):
    """Evaluate predictions from a snapshot against realized completion times

    Args:
        snapshot_df: DataFrame with historical predictions (from a weekly snapshot)
        current_df: DataFrame with current work order data (including completed orders)

    Returns:
        dict: Evaluation metrics or None if no completed orders to evaluate
    """
    # Merge snapshot predictions with current actual data
    merged = snapshot_df.merge(
        current_df[["workorderid", "datein", "datecompleted"]],
        on="workorderid",
        how="left"
    )

    # Calculate actual days to complete
    merged["actual_days"] = (
        merged["datecompleted"] - merged["datein"]
    ).dt.days

    # Only evaluate orders that now have completion data
    eval_df = merged.dropna(subset=["actual_days"])

    if eval_df.empty:
        return None

    mae = mean_absolute_error(eval_df["actual_days"], eval_df["predicted_days"])
    rmse = np.sqrt(mean_squared_error(eval_df["actual_days"], eval_df["predicted_days"]))

    # Calculate MAPE with protection against division by zero
    mask = eval_df["actual_days"] != 0
    if mask.sum() > 0:
        mape = np.mean(np.abs((eval_df.loc[mask, "actual_days"] - eval_df.loc[mask, "predicted_days"]) / eval_df.loc[mask, "actual_days"])) * 100
    else:
        mape = 0.0

    return {
        "snapshot_date": eval_df["prediction_date"].iloc[0],
        "records_evaluated": len(eval_df),
        "mae": round(mae, 3),
        "rmse": round(rmse, 3),
        "mape": round(mape, 3),
    }


@ml_bp.route("/check_predictions_status")
@login_required
def check_predictions_status():
    """Check if any predicted work orders have completed"""
    from utils.file_upload import s3_client, AWS_S3_BUCKET
    from io import BytesIO

    try:
        # Load prediction snapshots (both daily and weekly)
        daily_response = s3_client.list_objects_v2(
            Bucket=AWS_S3_BUCKET,
            Prefix="ml_predictions/daily_"
        )
        weekly_response = s3_client.list_objects_v2(
            Bucket=AWS_S3_BUCKET,
            Prefix="ml_predictions/weekly_"
        )

        all_contents = []
        if "Contents" in daily_response:
            all_contents.extend(daily_response["Contents"])
        if "Contents" in weekly_response:
            all_contents.extend(weekly_response["Contents"])

        if not all_contents:
            return jsonify({
                "status": "no_snapshots",
                "message": "No prediction snapshots found",
                "snapshots": 0
            })

        # Get all snapshots
        snapshot_files = [obj for obj in all_contents if obj["Key"].endswith(".csv")]

        # Load all predictions
        all_predictions = []
        snapshot_info = []

        for obj in snapshot_files:
            buffer = BytesIO()
            s3_client.download_fileobj(AWS_S3_BUCKET, obj["Key"], buffer)
            buffer.seek(0)
            df = pd.read_csv(buffer)

            snapshot_date = obj["Key"].split('/')[-1].replace("daily_", "").replace("weekly_", "").replace(".csv", "")
            df['snapshot_date'] = snapshot_date

            all_predictions.append(df)
            snapshot_info.append({
                "date": snapshot_date,
                "predictions": len(df),
                "unique_orders": df['workorderid'].nunique()
            })

        combined_predictions = pd.concat(all_predictions, ignore_index=True)

        # Ensure workorderid is string for consistency
        combined_predictions['workorderid'] = combined_predictions['workorderid'].astype(str)

        # Get unique work order IDs
        predicted_wo_ids = combined_predictions['workorderid'].unique().tolist()

        # Load current work order data
        current_df = MLService.load_work_orders()
        if current_df is None or current_df.empty:
            return jsonify({
                "status": "error",
                "message": "Could not load work order data"
            }), 500

        # Ensure workorderid is string in current_df too
        current_df['workorderid'] = current_df['workorderid'].astype(str)

        # Filter to only the predicted work orders
        current_df = current_df[current_df['workorderid'].isin(predicted_wo_ids)].copy()

        # Convert dates
        current_df['datein'] = pd.to_datetime(current_df['datein'], errors='coerce')
        current_df['datecompleted'] = pd.to_datetime(current_df['datecompleted'], errors='coerce')

        # Filter out invalid dates (bad data like 7777-07-07, 2111-11-11, etc.)
        min_valid_date = pd.Timestamp('2000-01-01')
        max_valid_date = pd.Timestamp.now() + pd.Timedelta(days=365)

        current_df = current_df[
            (current_df["datecompleted"].isna()) |
            ((current_df["datecompleted"] >= min_valid_date) &
             (current_df["datecompleted"] <= max_valid_date))
        ].copy()

        current_df = current_df[
            (current_df["datein"].isna()) |
            ((current_df["datein"] >= min_valid_date) &
             (current_df["datein"] <= max_valid_date))
        ].copy()

        # Calculate actual completion time
        current_df['actual_days'] = (current_df['datecompleted'] - current_df['datein']).dt.days

        # Split into completed and open
        completed = current_df[current_df['datecompleted'].notna()].copy()
        still_open = current_df[current_df['datecompleted'].isna()].copy()

        # Merge predictions with completion status
        merged = combined_predictions.merge(
            current_df[['workorderid', 'datein', 'datecompleted', 'actual_days']],
            on='workorderid',
            how='left'
        )

        completed_merged = merged[merged['datecompleted'].notna()].copy()

        # Build response
        result = {
            "status": "success",
            "snapshots": {
                "total": len(snapshot_files),
                "details": snapshot_info
            },
            "predictions": {
                "total": len(combined_predictions),
                "unique_orders": len(predicted_wo_ids)
            },
            "completion_status": {
                "completed_orders": len(completed),
                "still_open_orders": len(still_open),
                "completion_rate": round(len(completed) / len(predicted_wo_ids) * 100, 1) if predicted_wo_ids else 0
            }
        }

        if not completed.empty:
            # Calculate statistics for completed orders
            completed_merged['error'] = abs(completed_merged['actual_days'] - completed_merged['predicted_days'])

            # Group by snapshot
            by_snapshot = completed_merged.groupby('snapshot_date').agg({
                'error': 'mean',
                'workorderid': 'count'
            }).reset_index()
            by_snapshot.columns = ['snapshot_date', 'mae', 'n_predictions']

            # Get examples
            examples = []
            for wo_id in completed['workorderid'].unique()[:5]:
                wo_preds = completed_merged[completed_merged['workorderid'] == wo_id].sort_values('snapshot_date')
                examples.append({
                    "work_order": str(wo_id),
                    "actual_days": float(wo_preds.iloc[0]['actual_days']),
                    "completed_date": wo_preds.iloc[0]['datecompleted'].strftime('%Y-%m-%d'),
                    "predictions": [
                        {
                            "date": row['snapshot_date'],
                            "predicted_days": float(row['predicted_days']),
                            "error": abs(float(row['actual_days']) - float(row['predicted_days']))
                        }
                        for _, row in wo_preds.iterrows()
                    ]
                })

            result["dashboard_ready"] = True
            result["metrics"] = {
                "overall_mae": round(completed_merged['error'].mean(), 2),
                "total_evaluations": len(completed_merged),
                "by_snapshot": by_snapshot.to_dict('records')
            }
            result["examples"] = examples

        else:
            result["dashboard_ready"] = False
            result["message"] = "No predicted orders have completed yet. Dashboard will show data once they finish."

            # Show when predictions were made
            result["waiting_since"] = snapshot_info[0]['date'] if snapshot_info else None

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
