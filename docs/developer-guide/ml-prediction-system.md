# ML Prediction System

## Overview

The ML prediction system uses a **LightGBM gradient boosting model** to predict work order completion times. The system automatically retrains daily with new data and generates daily prediction snapshots to track real-world performance.

**Key Features:**
- Automated daily retraining (2:00 AM)
- Daily prediction snapshots (1:00 AM)
- Performance tracking dashboard with statistical metrics
- Model caching with TTL for multi-worker deployment
- S3-based model storage and snapshot archival

## Architecture

### Components

**ML Service (`routes/ml.py`):**
- `MLService` class: Data loading, preprocessing, feature engineering
- `train_model()`: Interactive training endpoint with train/test split
- `cron_retrain()`: Automated daily retraining on full dataset
- `cron_predict_daily()`: Generate daily predictions for open work orders
- `performance_dashboard()`: Real-world performance tracking with statistical analysis

**Cron Jobs (`.platform/hooks/postdeploy/01_setup_ml_cron.sh`):**
- **1:00 AM**: Daily predictions (saves snapshots to S3)
- **2:00 AM**: Daily model retraining (trains on all historical data)
- **3:00 AM**: Health check (verifies cron jobs are running)

**Storage:**
- **S3 Bucket**: `awning-cleaning-data`
  - `ml_models/cron_*.pkl` - Trained model files
  - `ml_models/cron_*_metadata.json` - Model metadata (MAE, features, timestamp)
  - `ml_predictions/daily_*.csv` - Daily prediction snapshots

**Model Cache:**
- 5-minute TTL per worker
- Automatic reload from S3 on cache expiration
- Handles multi-worker race conditions (#93)

### Data Flow

```
Work Order DB
     ↓
  Load Data
     ↓
Preprocess (augmentation, outlier filtering)
     ↓
Feature Engineering (19 features)
     ↓
Train/Test Split (20% test) OR Full Dataset (cron)
     ↓
Customer Stats Calculation (ONLY on training data)
     ↓
LightGBM Training (recency-weighted samples)
     ↓
Save Model to S3
     ↓
Cache in Memory (5 min TTL)
     ↓
Generate Daily Predictions
     ↓
Save Snapshot to S3
     ↓
Performance Dashboard (compare predictions vs actuals)
```

## Feature Engineering

### Features (19 total)

**Temporal Features (7):**
- `month_in`: Month work order received (1-12)
- `dow_in`: Day of week received (0-6)
- `quarter_in`: Quarter received (1-4)
- `is_weekend`: Weekend flag (0/1)
- `has_required_date`: Has required completion date (0/1)
- `days_until_required`: Days until required date (999 if no date)

**Rush Order Features (4):**
- `rushorder_binary`: Rush order flag (0/1)
- `firmrush_binary`: Firm rush order flag (0/1)
- `is_rush`: Rush intensity (0, 1, or 2)
- `any_rush`: Any rush flag (0/1)

**Customer Features (4):**
- `customer_encoded`: Label-encoded customer ID
- `cust_mean`: Average days for this customer (historical)
- `cust_std`: Standard deviation for this customer
- `cust_count`: Number of completed orders for this customer

**Work Order Features (4):**
- `storagetime_numeric`: Storage time in days
- `instructions_len`: Length of special instructions text
- `repairs_len`: Length of repairs needed text
- `has_repairs_needed`: Has repairs flag (0/1)

**Removed Features (prevented leakage or caused distribution mismatch):**
- ❌ `needs_cleaning`: Only available AFTER work is done (data leakage)
- ❌ `needs_treatment`: Only available AFTER work is done (data leakage)
- ❌ `order_age`: Train/predict distribution mismatch
- ❌ `storage_impact`: Redundant with `storagetime_numeric`
- ❌ `has_special_instructions`: Low importance, redundant

### Feature Engineering Pipeline

**1. Temporal Augmentation (Stage 0 Only)**
- **Purpose**: Match prediction scenario where clean/treat dates are unknown
- **Method**: Set `clean=NULL` and `treat=NULL` for all training samples
- **Previously**: Used 3 stages (0, 1, 2) but diluted training signal
- **Fix (Dec 2024)**: Use only Stage 0 to match real prediction conditions

**2. Customer Stats Calculation**
- **Critical Fix (Dec 2024)**: Calculate ONLY on training data after train/test split
- **Previous Bug**: Calculated on entire dataset, causing 50x MAE inflation
- **train_model()**: Uses only training split to calculate stats
- **cron_retrain()**: Uses full dataset (acceptable since no test set)

**3. Recency Weighting**
- **Purpose**: Bias model toward recent completion patterns
- **Method**: Exponential weighting `exp(recency * scale)`
- **Scale**: 2.0 (reduced from 4.0 to avoid overfitting)
- **Effect**: Recent data weighted ~7x higher than oldest data

**4. Outlier Filtering**
- Remove completion times > mean + 3 standard deviations
- Remove negative completion times

## Model Configuration

### Optuna Best (Production)

```python
{
    "n_estimators": 3000,
    "max_depth": 30,
    "num_leaves": 223,
    "learning_rate": 0.0935,
    "min_child_samples": 10,
    "lambda_l1": 1.726,
    "lambda_l2": 1.244,
    "subsample": 0.846,
    "bagging_freq": 9,
    "colsample_bytree": 0.760
}
```

**Validation Performance (5-fold CV):** 0.541 MAE

### Other Configurations

**max_complexity:** 2000 estimators, depth 25, 1.824 MAE (~46s training)
**deep_wide:** 1000 estimators, depth 15, 3.201 MAE (~12s training)
**baseline:** 1000 estimators, depth 8, 5.367 MAE (~4s training)

## Performance Tracking

### Daily Prediction Snapshots

Every day at 1:00 AM, the system:
1. Loads the current model from S3
2. Generates predictions for all open work orders
3. Saves a CSV snapshot to S3 with:
   - `workorderid`
   - `prediction_date`
   - `predicted_days`
   - `model_name`
   - `model_mae_at_train`
   - `model_trained_at`
   - `model_age_days`

### Performance Dashboard

**Route:** `/ml/performance_dashboard`

**Metrics Displayed:**
- **MAE (Mean Absolute Error)**: Average prediction error in days
- **RMSE (Root Mean Squared Error)**: Penalizes large errors more
- **95% Confidence Intervals**: Using t-distribution for small samples
- **Completion Rate**: Percentage of predicted orders now completed
- **Trend Analysis**: Linear regression to detect improving/degrading performance
- **Sample Size Annotations**: Number of completions per snapshot

**Statistical Features:**
- Standard error calculation
- Confidence interval visualization
- Hover tooltips with completion percentages
- Model staleness tracking

**Dashboard URL:** `https://your-app.com/ml/performance_dashboard`

## Critical Fixes (December 2024)

### Issue #1: Customer Stats Data Leakage (HIGH IMPACT)

**Problem:** Customer statistics (mean, std, count) were calculated on the ENTIRE dataset before train/test split, allowing the model to "see" test data completion times during training.

**Impact:** 50x MAE inflation (validation showed 0.541 days, production showed 26-33 days)

**Fix:**
- `train_model()`: Calculate customer stats ONLY on training data after split
- `cron_retrain()`: Calculate on full dataset (no test set, so no leakage)

**Code Location:** [routes/ml.py:568-599](../routes/ml.py#L568-L599)

### Issue #2: order_age Feature Mismatch (MEDIUM IMPACT)

**Problem:** During training, `order_age` shows aged orders (e.g., 30-180 days old). During prediction, `order_age` is always 0-1 days (newly created orders). This creates a distribution mismatch.

**Impact:** Model learned incorrect patterns based on order age that don't apply at prediction time.

**Fix:** Removed `order_age` from feature list in both `train_model()` and `cron_retrain()`

**Code Location:** [routes/ml.py:530](../routes/ml.py#L530)

### Issue #3: Recency Weight Too Aggressive (LOW-MEDIUM IMPACT)

**Problem:** Scale=4.0 gave 55x weight ratio between newest and oldest data, causing overfitting to very recent patterns.

**Impact:** Model too sensitive to recent noise, poor generalization.

**Fix:** Reduced scale from 4.0 to 2.0 (~7x weight ratio)

**Code Location:** [routes/ml.py:561](../routes/ml.py#L561), [routes/ml.py:1510](../routes/ml.py#L1510)

### Issue #4: Temporal Augmentation Dilution (MEDIUM IMPACT)

**Problem:** Using 3 augmentation stages (Stage 0, 1, 2) diluted the training signal and didn't match prediction scenario.

**Impact:** Model trained on unrealistic data (knowing clean/treat dates).

**Fix:** Use only Stage 0 (no clean/treat dates) to match prediction time

**Code Location:** [routes/ml.py:267-285](../routes/ml.py#L267-L285)

### Expected Improvement

With these fixes, we expect:
- **Real-world MAE**: Drop from 26-33 days to ~2-5 days
- **Validation/Production Gap**: Reduce from 50x to <4x
- **Consistency**: More stable predictions across different time periods

## API Endpoints

### Training Endpoints

**POST `/ml/train`** (requires login)
- Train new model with train/test split
- Parameters: `config` (model config name), `auto_save` (boolean)
- Returns: MAE, RMSE, R², training time

**POST `/ml/cron/retrain`** (requires X-Cron-Secret)
- Automated daily retraining on full dataset
- Saves model to S3 with timestamp
- Cleans up old models (keeps 5 newest)

### Prediction Endpoints

**POST `/ml/predict`** (requires login)
- Single work order prediction
- Input: work order details (custid, datein, rushorder, etc.)
- Returns: predicted_days, confidence_interval, estimated_completion

**GET `/ml/batch_predict`** (requires login)
- Predict for up to 50 pending orders
- Returns: Array of predictions with work order details

**GET `/ml/predict/<work_order_no>`** (requires login)
- Predict for specific work order by ID

**POST `/ml/cron/predict_daily`** (requires X-Cron-Secret)
- Generate daily predictions for all open orders
- Saves snapshot to S3

### Status & Analytics

**GET `/ml/status`** (requires login)
- Current model status and metadata

**GET `/ml/performance_dashboard`** (requires login)
- Interactive performance tracking dashboard

**GET `/ml/evaluate_snapshots`** (requires login)
- Evaluate all snapshots against completed orders

**GET `/ml/check_predictions_status`** (requires login)
- Check completion status of predicted orders

## Deployment

### Environment Variables

```bash
# Required for cron authentication
CRON_SECRET=your-secret-key

# AWS credentials (for S3 storage)
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_S3_BUCKET=awning-cleaning-data
AWS_REGION=us-east-1
```

### Cron Configuration

Cron jobs are automatically installed during EB deployment via postdeploy hook:

**File:** `.platform/hooks/postdeploy/01_setup_ml_cron.sh`

**Schedule:**
- 1:00 AM: Daily predictions
- 2:00 AM: Daily retrain
- 3:00 AM: Health check

**Logs:**
- `/var/log/ml-daily-predict.log`
- `/var/log/ml-retrain.log`
- `/var/log/ml-cron-health.log`

### Manual Deployment

```bash
# Deploy code changes
eb deploy

# SSH to check cron status
eb ssh
crontab -l
tail -f /var/log/ml-retrain.log

# Manually trigger retrain
curl -X POST http://localhost/ml/cron/retrain \
  -H "X-Cron-Secret: your-secret" \
  -H "Content-Type: application/json"

# Manually trigger daily predictions
curl -X POST http://localhost/ml/cron/predict_daily \
  -H "X-Cron-Secret: your-secret"
```

## Testing

### Unit Tests

```bash
# Run ML-specific tests
pytest test/test_ml_routes.py -v

# Run with coverage
pytest test/test_ml_routes.py --cov=routes.ml --cov-report=html
```

### Manual Testing

**1. Train a model:**
```bash
curl -X POST http://localhost:5000/ml/train \
  -H "Content-Type: application/json" \
  -b "session=your-session-cookie" \
  -d '{"config": "optuna_best", "auto_save": true}'
```

**2. Make a prediction:**
```bash
curl -X POST http://localhost:5000/ml/predict \
  -H "Content-Type: application/json" \
  -b "session=your-session-cookie" \
  -d '{
    "custid": "CUST001",
    "datein": "2024-12-19",
    "rushorder": false,
    "firmrush": false,
    "storagetime": 5
  }'
```

**3. Check performance dashboard:**
```bash
open http://localhost:5000/ml/performance_dashboard
```

## Monitoring

### Key Metrics to Monitor

**Model Performance:**
- MAE trend on performance dashboard
- Completion rate of predictions
- Gap between validation MAE and production MAE

**System Health:**
- Cron job execution (check logs)
- Model cache hit rate
- S3 storage usage (auto-cleanup keeps 5 models)
- Prediction snapshot frequency

**Data Quality:**
- Number of training samples
- Feature distribution changes
- Outlier rate (should be <5%)

### Alerts to Set Up

1. **MAE > 10 days** for 3 consecutive snapshots → investigate model drift
2. **Cron job failure** → check logs and authentication
3. **No new snapshots** for 48 hours → check cron health
4. **Model age > 7 days** → retrain cron may be failing

## Troubleshooting

### "No trained model available" Error

**Cause:** Model cache empty and no model in S3

**Fix:**
```bash
# Train a new model via UI or API
curl -X POST http://localhost/ml/train \
  -H "Content-Type: application/json" \
  -b "session=cookie" \
  -d '{"config": "optuna_best"}'
```

### Cron Jobs Not Running

**Check 1:** Verify cron files exist
```bash
ls -la /etc/cron.d/ml-cron-*
```

**Check 2:** Verify scripts are executable
```bash
ls -la /usr/local/bin/ml-cron-*.sh
```

**Check 3:** Check cron service status
```bash
service crond status
```

**Fix:** Redeploy to trigger postdeploy hook
```bash
eb deploy
```

### High MAE (> 10 days)

**Possible Causes:**
1. Data leakage (check customer stats calculation)
2. Distribution shift (check recent vs old data)
3. Model staleness (check last retrain timestamp)
4. Feature mismatch (check prediction vs training features)

**Diagnostic Steps:**
1. Check performance dashboard for trend
2. Review training logs for warnings
3. Compare feature distributions (training vs prediction)
4. Manually test predictions on known orders

### S3 Connection Errors

**Check:** AWS credentials are set correctly
```bash
eb printenv | grep AWS
```

**Fix:** Update environment variables
```bash
eb setenv AWS_ACCESS_KEY_ID=xxx AWS_SECRET_ACCESS_KEY=xxx
```

## Next Steps & Future Improvements

### High-Priority Improvements

**1. Add Work Order Item Features (MEDIUM IMPACT)**

Currently, we don't use work order item data (WorkOrderItem table). Adding item-level features could significantly improve predictions:

**Potential Features:**
- `item_count`: Number of items in the order
- `total_qty`: Total quantity across all items
- `avg_item_complexity`: Average complexity score per item (if available)
- `has_large_items`: Flag for oversized items (>X square feet)
- `material_diversity`: Number of unique materials in order

**Implementation:**
```python
# In engineer_features()
items = db.query(WorkOrderItem).filter(WorkOrderItem.WorkOrderNo.in_(workorder_ids)).all()
item_counts = items.groupby('WorkOrderNo').size()
df['item_count'] = df['workorderid'].map(item_counts).fillna(0)
```

**Expected Impact:** 10-20% MAE reduction (items correlate with complexity)

**2. Add Seasonal/Holiday Features (LOW-MEDIUM IMPACT)**

Work completion times may vary by season and around holidays:

**Potential Features:**
- `is_summer`: Summer months (Jun-Aug) flag
- `days_until_holiday`: Days until nearest major holiday
- `is_holiday_season`: Nov-Dec flag (busy season)
- `week_of_year`: 1-52 (captures annual cycles)

**Expected Impact:** 5-10% MAE reduction for seasonal patterns

**3. Implement Time-Series Cross-Validation (MEDIUM IMPACT)**

Current validation uses random split, but time-series CV would better simulate production:

**Method:**
- Use `TimeSeriesSplit` from sklearn
- Train on past data, validate on future data
- 5-fold expanding window

**Expected Impact:** More realistic validation metrics, better hyperparameter tuning

### Medium-Priority Improvements

**4. Add Customer Historical Features (MEDIUM IMPACT)**

Beyond average completion time, track customer behavior patterns:

**Potential Features:**
- `customer_rush_rate`: % of orders that are rush for this customer
- `customer_avg_items`: Average item count per order
- `days_since_last_order`: Recency of customer activity
- `customer_seasonal_pattern`: Does customer have seasonal peaks?

**5. Implement Model Ensemble (MEDIUM-HIGH IMPACT)**

Combine multiple models for better predictions:

**Approach:**
- Train LightGBM, XGBoost, and Random Forest
- Use weighted average or stacking
- Ensemble reduces variance and overfitting

**Expected Impact:** 15-25% MAE reduction

**6. Add Workload Features (MEDIUM IMPACT)**

Current workload affects completion times:

**Potential Features:**
- `queue_depth`: Number of pending orders when this order arrives
- `avg_queue_time`: Average time in queue for recent orders
- `staff_utilization`: Estimated % of capacity used (if available)

**Implementation Challenge:** Requires snapshot of queue state at order creation time

### Low-Priority (Nice-to-Have) Improvements

**7. Confidence Interval Calibration**

Currently using fixed ±1.5 days interval. Implement proper uncertainty estimation:

**Methods:**
- Quantile regression for prediction intervals
- Conformal prediction for distribution-free intervals
- Bootstrap aggregation for variance estimation

**8. Automated Model Selection**

Instead of using fixed "optuna_best" config:
- Run nightly Optuna hyperparameter optimization
- Compare new config to current production model
- Auto-deploy if MAE improves by >5%

**9. Explainability Dashboard**

Add SHAP values to explain individual predictions:
- Why was this order predicted to take 15 days?
- Which features contributed most?
- Compare to similar historical orders

**10. Real-Time Retraining on Completion**

Instead of daily batch retraining:
- Trigger incremental training when orders complete
- Use online learning or warm-start from existing model
- Reduces staleness from 24 hours to <1 hour

**11. A/B Testing Framework**

Test new model versions before full rollout:
- Route 10% of predictions to challenger model
- Compare performance over 2 weeks
- Auto-promote if challenger wins

### Implementation Roadmap

**Phase 1 (Next 1-2 months):**
1. Add work order item features
2. Implement time-series CV
3. Add seasonal/holiday features

**Phase 2 (3-4 months):**
4. Customer historical features
5. Model ensemble
6. Workload features

**Phase 3 (6+ months):**
7. Confidence interval calibration
8. Automated model selection
9. Explainability dashboard

**Future (if needed):**
10. Real-time retraining
11. A/B testing framework

### Performance Goals

**Current State (Post-Fixes):**
- Validation MAE: ~0.5-2 days
- Production MAE: ~2-5 days (estimated)
- Gap: <4x

**Target State (After Improvements):**
- Validation MAE: ~0.3-1 day
- Production MAE: ~1-3 days
- Gap: <3x
- 95% CI coverage: 90-95%

## References

**Code Files:**
- Main ML logic: `routes/ml.py`
- Cron setup: `.platform/hooks/postdeploy/01_setup_ml_cron.sh`
- Cron scripts: `.platform/files/usr/local/bin/ml-cron-*.sh`

**Related Documentation:**
- [AWS Deployment](../deployment/aws-eb.md)
- [Database Schema](database-schema.md)
- [Testing Guide](testing.md)

**External Resources:**
- [LightGBM Documentation](https://lightgbm.readthedocs.io/)
- [scikit-learn API](https://scikit-learn.org/stable/modules/classes.html)
- [Optuna Hyperparameter Tuning](https://optuna.org/)