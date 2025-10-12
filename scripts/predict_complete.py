import pandas as pd
from sqlalchemy import create_engine
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import LabelEncoder
import numpy as np
import time
import warnings

warnings.filterwarnings("ignore")

# Load and prepare data (same as before)
engine = create_engine("postgresql:///Clean_Repair")
df = pd.read_sql("SELECT * FROM tblcustworkorderdetail;", engine)

# Data preprocessing (condensed from previous script)
date_cols = ["datein", "datecompleted", "daterequired", "clean", "treat"]
for col in date_cols:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

df["days_to_complete"] = (df["datecompleted"] - df["datein"]).dt.days
train_df = df.dropna(subset=["days_to_complete"]).copy()

# Filter outliers
mean_days = train_df["days_to_complete"].mean()
std_days = train_df["days_to_complete"].std()
train_df = train_df[
    (train_df["days_to_complete"] >= 0)
    & (train_df["days_to_complete"] <= mean_days + 3 * std_days)
].copy()

# Feature engineering (condensed)
today = pd.Timestamp.today()


def convert_to_binary(series):
    if series.dtype == "object":
        return (
            series.fillna("")
            .astype(str)
            .str.lower()
            .isin(["true", "t", "1", "yes", "y"])
            .astype(int)
        )
    else:
        return series.fillna(0).astype(bool).astype(int)


def convert_to_numeric(series):
    if series.dtype == "object":
        return pd.to_numeric(series, errors="coerce").fillna(0)
    else:
        return series.fillna(0)


# All feature engineering
train_df["order_age"] = (today - train_df["datein"]).dt.days.fillna(0)
train_df["month_in"] = train_df["datein"].dt.month.fillna(0).astype(int)
train_df["dow_in"] = train_df["datein"].dt.dayofweek.fillna(0).astype(int)
train_df["quarter_in"] = train_df["datein"].dt.quarter.fillna(0).astype(int)
train_df["is_weekend"] = (train_df["dow_in"] >= 5).astype(int)

train_df["rushorder_binary"] = convert_to_binary(train_df["rushorder"])
train_df["firmrush_binary"] = convert_to_binary(train_df["firmrush"])
train_df["is_rush"] = train_df["rushorder_binary"] + train_df["firmrush_binary"]
train_df["any_rush"] = (train_df["is_rush"] > 0).astype(int)

train_df["instructions_len"] = train_df["specialinstructions"].fillna("").apply(len)
train_df["has_special_instructions"] = (train_df["instructions_len"] > 0).astype(int)
train_df["repairs_len"] = train_df["repairsneeded"].fillna("").apply(len)
train_df["has_repairs_needed"] = (train_df["repairs_len"] > 0).astype(int)

if "clean" in train_df.columns:
    train_df["needs_cleaning"] = train_df["clean"].notna().astype(int)
if "treat" in train_df.columns:
    train_df["needs_treatment"] = train_df["treat"].notna().astype(int)

train_df["has_required_date"] = train_df["daterequired"].notna().astype(int)
train_df["days_until_required"] = (
    train_df["daterequired"] - train_df["datein"]
).dt.days.fillna(999)

# Customer features
if train_df["custid"].nunique() > 1:
    le_cust = LabelEncoder()
    train_df["customer_encoded"] = le_cust.fit_transform(train_df["custid"].astype(str))
    cust_stats = (
        train_df.groupby("custid")["days_to_complete"]
        .agg(["mean", "std", "count"])
        .add_prefix("cust_")
    )
    train_df = train_df.merge(cust_stats, on="custid", how="left")
    train_df["cust_std"] = train_df["cust_std"].fillna(0)

train_df["storagetime_numeric"] = convert_to_numeric(train_df["storagetime"])
train_df["storage_impact"] = train_df["storagetime_numeric"]

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

if "needs_cleaning" in train_df.columns:
    feature_cols.append("needs_cleaning")
if "needs_treatment" in train_df.columns:
    feature_cols.append("needs_treatment")

feature_cols = [col for col in feature_cols if col in train_df.columns]

X = train_df[feature_cols].copy().fillna(0)
y = train_df["days_to_complete"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

print(
    f"Dataset ready: {X_train.shape[0]} training samples, {len(feature_cols)} features"
)
print("=" * 80)

# Define hyperparameter configurations to test
configs = [
    # Current baseline
    {
        "name": "Current Baseline",
        "n_estimators": 1000,
        "max_depth": 8,
        "num_leaves": 31,
        "learning_rate": 0.05,
    },
    # More trees, same complexity
    {
        "name": "More Trees",
        "n_estimators": 2000,
        "max_depth": 8,
        "num_leaves": 31,
        "learning_rate": 0.05,
    },
    {
        "name": "Many Trees",
        "n_estimators": 5000,
        "max_depth": 8,
        "num_leaves": 31,
        "learning_rate": 0.03,
    },
    # Deeper trees
    {
        "name": "Deeper Trees",
        "n_estimators": 1000,
        "max_depth": 15,
        "num_leaves": 31,
        "learning_rate": 0.05,
    },
    {
        "name": "Very Deep",
        "n_estimators": 1000,
        "max_depth": 25,
        "num_leaves": 31,
        "learning_rate": 0.05,
    },
    # More leaves (wider trees)
    {
        "name": "More Leaves",
        "n_estimators": 1000,
        "max_depth": 8,
        "num_leaves": 63,
        "learning_rate": 0.05,
    },
    {
        "name": "Many Leaves",
        "n_estimators": 1000,
        "max_depth": 8,
        "num_leaves": 127,
        "learning_rate": 0.05,
    },
    {
        "name": "Huge Leaves",
        "n_estimators": 1000,
        "max_depth": 8,
        "num_leaves": 255,
        "learning_rate": 0.05,
    },
    # Combined high complexity
    {
        "name": "Deep + Wide",
        "n_estimators": 1000,
        "max_depth": 15,
        "num_leaves": 127,
        "learning_rate": 0.05,
    },
    {
        "name": "Max Complexity",
        "n_estimators": 2000,
        "max_depth": 25,
        "num_leaves": 255,
        "learning_rate": 0.03,
    },
    # Different learning rates
    {
        "name": "Slow Learning",
        "n_estimators": 3000,
        "max_depth": 8,
        "num_leaves": 31,
        "learning_rate": 0.01,
    },
    {
        "name": "Fast Learning",
        "n_estimators": 500,
        "max_depth": 8,
        "num_leaves": 31,
        "learning_rate": 0.1,
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
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
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
