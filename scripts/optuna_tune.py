from sklearn.model_selection import KFold
from MLService import MLService
import optuna
import warnings
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error
import numpy as np

warnings.filterwarnings("ignore")

# --- Load, preprocess, and engineer features with temporal augmentation ---
print("=" * 80)
print("OPTUNA HYPERPARAMETER TUNING - NO DATA LEAKAGE VERSION")
print("=" * 80)

print("\n[1/4] Loading work orders from database...")
df = MLService.load_work_orders()
if df is None or df.empty:
    raise ValueError("No data available")
print(f"✓ Loaded {len(df)} work orders")

print("\n[2/4] Preprocessing data with temporal augmentation...")
print("  → This creates multiple samples per work order at different stages")
print("  → Prevents data leakage from clean/treat dates")
train_df = MLService.preprocess_data(df)
print(f"✓ Created {len(train_df)} augmented training samples")

print("\n[3/4] Engineering features...")
train_df = MLService.engineer_features(train_df)

# --- Define feature columns (NO LEAKY FEATURES) ---
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

# Verify no leaky features
if "needs_cleaning" in train_df.columns:
    print("⚠️  WARNING: needs_cleaning feature found - this causes data leakage!")
if "needs_treatment" in train_df.columns:
    print("⚠️  WARNING: needs_treatment feature found - this causes data leakage!")

feature_cols = [c for c in feature_cols if c in train_df.columns]

X = train_df[feature_cols].fillna(0)
y = train_df["days_to_complete"]

print(f"✓ Prepared {len(X)} samples with {len(feature_cols)} features")
print(f"  Features: {', '.join(feature_cols)}")

# Analyze augmentation stages
if "augmentation_stage" in train_df.columns:
    print(f"\n[4/4] Augmentation stage distribution:")
    stage_counts = train_df["augmentation_stage"].value_counts().sort_index()
    for stage, count in stage_counts.items():
        stage_name = ["Early (no dates)", "Middle (clean only)", "Late (both dates)"][int(stage)]
        pct = 100 * count / len(train_df)
        print(f"  Stage {int(stage)} - {stage_name}: {count} samples ({pct:.1f}%)")

print("\n" + "=" * 80)
print("OPTUNA OPTIMIZATION CONFIGURATION")
print("=" * 80)
print("Validation Strategy: 5-Fold Cross-Validation (prevents overfitting)")
print("Metric: Mean Absolute Error (MAE) in days")
print("Direction: Minimize MAE")
print("=" * 80 + "\n")


# --- Optuna objective with K-Fold Cross-Validation ---
def objective(trial):
    """
    Objective function using k-fold cross-validation to prevent overfitting.

    This evaluates each hyperparameter configuration across multiple train/test splits,
    providing a more robust estimate of generalization performance.
    """
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 500, 3000, step=250),
        "max_depth": trial.suggest_int("max_depth", 6, 30, step=2),
        "num_leaves": trial.suggest_int("num_leaves", 31, 255, step=16),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
        "min_child_samples": trial.suggest_int("min_child_samples", 10, 100, step=10),
        "lambda_l1": trial.suggest_float("lambda_l1", 0.0, 10.0),
        "lambda_l2": trial.suggest_float("lambda_l2", 0.0, 10.0),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.6, 1.0),
        "bagging_fraction": trial.suggest_float("bagging_fraction", 0.6, 1.0),
        "bagging_freq": trial.suggest_int("bagging_freq", 1, 10),
    }

    # 5-Fold Cross-Validation
    kfold = KFold(n_splits=5, shuffle=True, random_state=42)
    fold_maes = []

    for fold_idx, (train_idx, val_idx) in enumerate(kfold.split(X, y)):
        X_train_fold = X.iloc[train_idx]
        y_train_fold = y.iloc[train_idx]
        X_val_fold = X.iloc[val_idx]
        y_val_fold = y.iloc[val_idx]

        # Train model
        model = lgb.LGBMRegressor(
            objective="regression",
            n_estimators=params["n_estimators"],
            learning_rate=params["learning_rate"],
            max_depth=params["max_depth"],
            num_leaves=params["num_leaves"],
            min_child_samples=params["min_child_samples"],
            reg_lambda=params["lambda_l2"],
            reg_alpha=params["lambda_l1"],
            subsample=params["bagging_fraction"],
            subsample_freq=params["bagging_freq"],
            colsample_bytree=params["feature_fraction"],
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )

        model.fit(X_train_fold, y_train_fold)

        # Evaluate on validation fold
        y_pred = model.predict(X_val_fold)
        fold_mae = mean_absolute_error(y_val_fold, y_pred)
        fold_maes.append(fold_mae)

    # Return mean MAE across all folds
    mean_mae = np.mean(fold_maes)
    std_mae = np.std(fold_maes)

    # Store fold statistics as user attributes for analysis
    trial.set_user_attr("mae_std", std_mae)
    trial.set_user_attr("mae_folds", fold_maes)

    return mean_mae


if __name__ == "__main__":
    # Create or load study with a new name to distinguish from old leaky version
    study = optuna.create_study(
        direction="minimize",
        study_name="workorder_lgbm_no_leakage_v2",
        storage="sqlite:///optuna_study.db",
        load_if_exists=True,
    )

    print(f"Starting optimization with {study._storage.get_n_trials(study._study_id)} existing trials...")
    print("Press Ctrl+C to stop early (progress will be saved)\n")

    try:
        study.optimize(objective, n_trials=100, n_jobs=1, show_progress_bar=True)
    except KeyboardInterrupt:
        print("\n\n⚠️  Optimization interrupted by user")

    # Report results
    print("\n" + "=" * 80)
    print("OPTIMIZATION RESULTS")
    print("=" * 80)
    print(f"Total trials completed: {len(study.trials)}")
    print(f"Best trial: #{study.best_trial.number}")
    print(f"Best MAE (CV): {study.best_value:.4f} days")

    if "mae_std" in study.best_trial.user_attrs:
        print(f"MAE Std Dev: {study.best_trial.user_attrs['mae_std']:.4f} days")
        print(f"MAE Range: [{study.best_value - study.best_trial.user_attrs['mae_std']:.4f}, "
              f"{study.best_value + study.best_trial.user_attrs['mae_std']:.4f}]")

    print("\n" + "=" * 80)
    print("BEST HYPERPARAMETERS")
    print("=" * 80)
    for param, value in study.best_params.items():
        if isinstance(value, float):
            print(f"  {param:.<30} {value:.6f}")
        else:
            print(f"  {param:.<30} {value}")

    # Show top 5 trials
    print("\n" + "=" * 80)
    print("TOP 5 TRIALS")
    print("=" * 80)
    print(f"{'Trial':<8} {'MAE':<10} {'Std':<10} {'n_est':<8} {'depth':<8} {'leaves':<8} {'lr':<10}")
    print("-" * 80)

    sorted_trials = sorted(study.trials, key=lambda t: t.value if t.value else float('inf'))[:5]
    for trial in sorted_trials:
        if trial.value:
            mae_std = trial.user_attrs.get("mae_std", 0)
            print(f"#{trial.number:<7} {trial.value:<10.4f} {mae_std:<10.4f} "
                  f"{int(trial.params.get('n_estimators', 0)):<8} "
                  f"{int(trial.params.get('max_depth', 0)):<8} "
                  f"{int(trial.params.get('num_leaves', 0)):<8} "
                  f"{trial.params.get('learning_rate', 0):<10.6f}")

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("1. Review best hyperparameters above")
    print("2. Update MODEL_CONFIGS in routes/ml.py with these values")
    print("3. Test on actual pending work orders before deploying")
    print("4. Compare performance with old model (expect higher MAE, but better generalization)")
    print("\nNote: This MAE is from cross-validation with temporal augmentation,")
    print("      so it represents realistic performance on work orders at all stages.")
    print("=" * 80)
