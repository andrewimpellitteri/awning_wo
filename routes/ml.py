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
    "max_complexity": {
        "n_estimators": 2000,
        "max_depth": 25,
        "num_leaves": 255,
        "learning_rate": 0.03,
        "description": "Best overall - 5.988 MAE (41s training)",
    },
    "deep_wide": {
        "n_estimators": 1000,
        "max_depth": 15,
        "num_leaves": 127,
        "learning_rate": 0.05,
        "description": "Best practical - 6.096 MAE (10s training)",
    },
    "baseline": {
        "n_estimators": 1000,
        "max_depth": 8,
        "num_leaves": 31,
        "learning_rate": 0.05,
        "description": "Standard - 6.468 MAE (3.5s training)",
    },
}

# Global model storage
current_model = None
model_metadata = {}


def load_latest_model_from_s3():
    """Load the most recently trained model from S3 on startup"""
    global current_model, model_metadata

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
            print("[ML STARTUP] No models found in S3")
            return False

        # Find the most recent cron model
        model_files = [
            obj for obj in response["Contents"]
            if obj["Key"].endswith(".pkl") and "cron_" in obj["Key"]
        ]

        if not model_files:
            print("[ML STARTUP] No cron models found in S3")
            return False

        # Sort by last modified date, get most recent
        latest_model = sorted(model_files, key=lambda x: x["LastModified"], reverse=True)[0]
        model_name = latest_model["Key"].replace("ml_models/", "").replace(".pkl", "")

        print(f"[ML STARTUP] Loading model: {model_name}")

        # Download model from S3
        model_buffer = BytesIO()
        s3_client.download_fileobj(AWS_S3_BUCKET, latest_model["Key"], model_buffer)
        model_buffer.seek(0)
        current_model = pickle.load(model_buffer)

        # Download metadata from S3
        metadata_key = f"ml_models/{model_name}_metadata.json"
        metadata_buffer = BytesIO()
        s3_client.download_fileobj(AWS_S3_BUCKET, metadata_key, metadata_buffer)
        metadata_buffer.seek(0)
        model_metadata = json.loads(metadata_buffer.read().decode("utf-8"))

        print(f"[ML STARTUP] Model loaded successfully - MAE: {model_metadata.get('mae')}, "
              f"Trained at: {model_metadata.get('trained_at')}")

        return True

    except Exception as e:
        print(f"[ML STARTUP] Failed to load model from S3: {e}")
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
        """Preprocess the work order data"""
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

        return train_df

    @staticmethod
    def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
        """Apply feature engineering to work order data"""
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

        # --- Rush order features ---
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

        # --- Service features ---
        if "clean" in df.columns:
            df["needs_cleaning"] = (
                pd.to_datetime(df["clean"], errors="coerce").notna().astype(int)
            )
        else:
            df["needs_cleaning"] = 0

        if "treat" in df.columns:
            df["needs_treatment"] = (
                pd.to_datetime(df["treat"], errors="coerce").notna().astype(int)
            )
        else:
            df["needs_treatment"] = 0

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
        if (
            "custid" in df.columns
            and df["custid"].nunique() > 1
            and "days_to_complete" in df.columns
        ):
            le_cust = LabelEncoder()
            df["customer_encoded"] = le_cust.fit_transform(df["custid"].astype(str))

            cust_stats = (
                df.groupby("custid")["days_to_complete"]
                .agg(["mean", "std", "count"])
                .add_prefix("cust_")
            )
            df = df.merge(cust_stats, on="custid", how="left")
            df["cust_std"] = df["cust_std"].fillna(0)
        else:
            df["customer_encoded"] = 0
            df["cust_mean"] = 0
            df["cust_std"] = 0
            df["cust_count"] = 0

        # --- Storage features ---
        df["storagetime_numeric"] = MLService.convert_to_numeric(
            df.get("storagetime", pd.Series())
        )
        df["storage_impact"] = df["storagetime_numeric"]

        return df


@ml_bp.route("/")
@login_required
def dashboard():
    return render_template("ml/dashboard.html")


# Replace your existing train_model route with this updated version


@ml_bp.route("/train", methods=["POST"])
@login_required
def train_model():
    """Train a new model"""
    global current_model, model_metadata

    try:
        config_name = request.json.get("config", "baseline")
        config = MODEL_CONFIGS.get(config_name, MODEL_CONFIGS["baseline"])
        auto_save = request.json.get("auto_save", True)  # New parameter

        # Load data using the WorkOrder model
        df = MLService.load_work_orders()
        if df is None or df.empty:
            return jsonify({"error": "No data available for training"}), 400

        # Preprocess and engineer features
        train_df = MLService.preprocess_data(df)
        train_df = MLService.engineer_features(train_df)

        # Feature selection
        feature_cols = [
            "rushorder_binary",
            "firmrush_binary",
            "storagetime_numeric",
            "order_age",
            "month_in",
            "dow_in",
            "quarter_in",
            "is_weekend",
            "is_rush",
            "any_rush",
            "instructions_len",
            "has_special_instructions",
            "repairs_len",
            "has_repairs_needed",
            "has_required_date",
            "days_until_required",
            "customer_encoded",
            "cust_mean",
            "cust_std",
            "cust_count",
            "storage_impact",
        ]

        # Add optional features if they exist
        if "needs_cleaning" in train_df.columns:
            feature_cols.append("needs_cleaning")
        if "needs_treatment" in train_df.columns:
            feature_cols.append("needs_treatment")

        # Filter available features
        feature_cols = [col for col in feature_cols if col in train_df.columns]

        if len(feature_cols) == 0:
            return jsonify({"error": "No valid features found"}), 400

        X = train_df[feature_cols].fillna(0)
        y = train_df["days_to_complete"]

        if len(X) < 10:
            return jsonify({"error": "Insufficient training data"}), 400

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Train model
        start_time = time.time()

        model = lgb.LGBMRegressor(
            objective="regression",
            n_estimators=config["n_estimators"],
            learning_rate=config["learning_rate"],
            max_depth=config["max_depth"],
            num_leaves=config["num_leaves"],
            min_child_samples=20,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )

        model.fit(X_train, y_train)
        training_time = time.time() - start_time

        # Evaluate
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))

        ss_res = np.sum((y_test - y_pred) ** 2)
        ss_tot = np.sum((y_test - np.mean(y_test)) ** 2)
        r2 = 1 - (ss_res / ss_tot)

        # Store model
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
    global current_model, model_metadata

    if current_model is None:
        return jsonify({"error": "No trained model available"}), 400

    try:
        data = request.json

        # Create a minimal DataFrame for feature engineering
        df = pd.DataFrame(
            [
                {
                    "custid": data.get("custid", "UNKNOWN"),
                    "datein": data.get("datein", datetime.now().strftime("%Y-%m-%d")),
                    "daterequired": data.get("daterequired"),
                    "rushorder": data.get("rushorder", False),
                    "firmrush": data.get("firmrush", False),
                    "storagetime": data.get("storagetime", 0),
                    "specialinstructions": data.get("specialinstructions", ""),
                    "repairsneeded": data.get("repairsneeded", ""),
                    "clean": data.get("needs_cleaning", False),
                    "treat": data.get("needs_treatment", False),
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
    global current_model, model_metadata

    if current_model is None:
        return jsonify({"error": "No trained model available"}), 400

    try:
        # Get pending work orders - fix the query
        pending_orders = (
            WorkOrder.query.filter(
                (WorkOrder.DateCompleted == None)
                | (WorkOrder.DateCompleted == "")
                | (WorkOrder.DateCompleted.is_(None))
            )
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
                # Create prediction data with proper null handling
                data = {
                    "custid": order.CustID or "UNKNOWN",
                    "datein": order.DateIn or datetime.now().strftime("%Y-%m-%d"),
                    "daterequired": order.DateRequired,
                    "rushorder": order.RushOrder or False,
                    "firmrush": order.FirmRush or False,
                    "storagetime": order.StorageTime or 0,
                    "specialinstructions": order.SpecialInstructions or "",
                    "repairsneeded": order.RepairsNeeded or "",
                    "needs_cleaning": order.Clean or False,
                    "needs_treatment": order.Treat or False,
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
    global current_model, model_metadata

    if current_model is None:
        return jsonify({"error": "No trained model available"}), 400

    # Fetch the order
    order = WorkOrder.query.filter_by(WorkOrderNo=str(work_order_no)).first()
    if not order:
        return jsonify({"error": f"Work order {work_order_no} not found"}), 404

    try:
        # Build input data
        data = {
            "custid": order.CustID or "UNKNOWN",
            "datein": order.DateIn or datetime.now().strftime("%Y-%m-%d"),
            "daterequired": order.DateRequired,
            "rushorder": order.RushOrder or False,
            "firmrush": order.FirmRush or False,
            "storagetime": order.StorageTime or 0,
            "specialinstructions": order.SpecialInstructions or "",
            "repairsneeded": order.RepairsNeeded or "",
            "needs_cleaning": order.Clean or False,
            "needs_treatment": order.Treat or False,
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
    global current_model, model_metadata

    return jsonify(
        {
            "trained": current_model is not None,
            "metadata": model_metadata,
            "available_configs": list(MODEL_CONFIGS.keys()),
        }
    )


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
        config_name = request_data.get("config", "baseline")
        config = MODEL_CONFIGS.get(config_name, MODEL_CONFIGS["baseline"])

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

        # Feature selection - same as regular training
        feature_cols = [
            "rushorder_binary",
            "firmrush_binary",
            "storagetime_numeric",
            "order_age",
            "month_in",
            "dow_in",
            "quarter_in",
            "is_weekend",
            "is_rush",
            "any_rush",
            "instructions_len",
            "has_special_instructions",
            "repairs_len",
            "has_repairs_needed",
            "has_required_date",
            "days_until_required",
            "customer_encoded",
            "cust_mean",
            "cust_std",
            "cust_count",
            "storage_impact",
        ]

        # Add optional features if they exist
        if "needs_cleaning" in train_df.columns:
            feature_cols.append("needs_cleaning")
        if "needs_treatment" in train_df.columns:
            feature_cols.append("needs_treatment")

        # Filter available features
        feature_cols = [col for col in feature_cols if col in train_df.columns]

        if len(feature_cols) == 0:
            error_msg = "No valid features found"
            print(f"[CRON RETRAIN] ERROR: {error_msg}")
            return jsonify(
                {"error": error_msg, "timestamp": start_timestamp.isoformat()}
            ), 400

        # Prepare ALL data for training (no test holdout for cron job)
        X = train_df[feature_cols].fillna(0)
        y = train_df["days_to_complete"]

        if len(X) < 10:
            error_msg = f"Insufficient training data: only {len(X)} samples"
            print(f"[CRON RETRAIN] ERROR: {error_msg}")
            return jsonify(
                {"error": error_msg, "timestamp": start_timestamp.isoformat()}
            ), 400

        print(
            f"[CRON RETRAIN] Training on ALL {len(X)} samples with {len(feature_cols)} features"
        )

        # Train model on ALL available data
        training_start_time = time.time()

        model = lgb.LGBMRegressor(
            objective="regression",
            n_estimators=config["n_estimators"],
            learning_rate=config["learning_rate"],
            max_depth=config["max_depth"],
            num_leaves=config["num_leaves"],
            min_child_samples=20,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )

        # Fit on ALL data
        model.fit(X, y)
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

        # Store model globally
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
