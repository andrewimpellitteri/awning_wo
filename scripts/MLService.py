import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import LabelEncoder
import os
from sqlalchemy import create_engine

# Database connection
engine_url = os.environ.get("DATABASE_URL")
if not engine_url:
    raise ValueError("DATABASE_URL environment variable not set")

print(f"Connecting to database: {engine_url[:30]}...")
engine = create_engine(engine_url)


class MLService:
    """ML service class - synchronized with routes/ml.py"""

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
        """Load work orders directly from database"""
        try:
            # Query the database directly without using the ORM to avoid relationship issues
            query = """
                SELECT
                    workorderno,
                    custid,
                    datein,
                    datecompleted,
                    daterequired,
                    rushorder,
                    firmrush,
                    specialinstructions,
                    repairsneeded,
                    clean,
                    treat
                FROM tblcustworkorderdetail
            """
            df = pd.read_sql(query, engine)

            # Convert column names to match expected format
            column_mapping = {
                "workorderno": "workorderid",
                "custid": "custid",
                "datein": "datein",
                "datecompleted": "datecompleted",
                "daterequired": "daterequired",
                "rushorder": "rushorder",
                "firmrush": "firmrush",
                "specialinstructions": "specialinstructions",
                "repairsneeded": "repairsneeded",
                "clean": "clean",
                "treat": "treat",
            }
            df = df.rename(columns=column_mapping)

            return df
        except Exception as e:
            print(f"Error loading work orders: {e}")
            import traceback

            traceback.print_exc()
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

        # TEMPORAL AUGMENTATION: Create multiple training samples per work order
        # to simulate different stages of completion
        augmented_samples = []

        for idx, row in train_df.iterrows():
            # Stage 0: No clean or treat dates (early stage - most common in production)
            stage_0 = row.copy()
            stage_0["clean"] = pd.NaT
            stage_0["treat"] = pd.NaT
            stage_0["augmentation_stage"] = 0
            augmented_samples.append(stage_0)

            # Stage 1: Has clean date but no treat date (middle stage)
            if pd.notna(row["clean"]):
                stage_1 = row.copy()
                stage_1["treat"] = pd.NaT
                stage_1["augmentation_stage"] = 1
                augmented_samples.append(stage_1)

            # Stage 2: Has both clean and treat dates (late stage - original data)
            stage_2 = row.copy()
            stage_2["augmentation_stage"] = 2
            augmented_samples.append(stage_2)

        # Create augmented dataframe
        augmented_df = pd.DataFrame(augmented_samples).reset_index(drop=True)

        print(f"[AUGMENTATION] Original samples: {len(train_df)}")
        print(f"[AUGMENTATION] Augmented samples: {len(augmented_df)}")
        print(
            f"[AUGMENTATION] Stage 0 (no dates): {(augmented_df['augmentation_stage'] == 0).sum()}"
        )
        print(
            f"[AUGMENTATION] Stage 1 (clean only): {(augmented_df['augmentation_stage'] == 1).sum()}"
        )
        print(
            f"[AUGMENTATION] Stage 2 (both dates): {(augmented_df['augmentation_stage'] == 2).sum()}"
        )

        return augmented_df

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

        df["repairs_len"] = (
            df.get("repairsneeded", "").fillna("").astype(str).apply(len)
        )
        df["has_repairs_needed"] = (df["repairs_len"] > 0).astype(int)

        # --- Service features - REMOVED DATA LEAKAGE ---
        # Previously: used presence of clean/treat dates which leaked information
        # Now: Use business logic features that don't depend on completion dates

        # Instead of checking if dates exist, we'll use other indicators:
        # - Has repairs needed suggests more complex work
        # - Has special instructions suggests custom handling
        # These are known at work order creation and don't leak completion info

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

        return df

    @staticmethod
    def train_evaluate_lgbm(params, X_train, y_train, X_test, y_test):
        model = lgb.LGBMRegressor(
            objective="regression",
            n_estimators=params["n_estimators"],
            learning_rate=params["learning_rate"],
            max_depth=params["max_depth"],
            num_leaves=params["num_leaves"],
            min_child_samples=params.get("min_child_samples", 20),
            subsample=params.get("subsample", 0.8),
            colsample_bytree=params.get("colsample_bytree", 0.8),
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        return mae
