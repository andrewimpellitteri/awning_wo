#!/usr/bin/env python3
"""
Simple script to check ML prediction snapshots in S3
"""

import boto3
import pandas as pd
from io import BytesIO
from datetime import datetime

# Initialize S3 client
s3 = boto3.client('s3')
BUCKET = 'awning-cleaning-data'


def check_prediction_snapshots():
    """Check prediction snapshots in S3"""
    print("\n" + "="*80)
    print("CHECKING ML PREDICTION SNAPSHOTS IN S3")
    print("="*80)

    try:
        # List all prediction files (support both new daily and legacy weekly)
        all_contents = []
        for prefix in ["ml_predictions/daily_", "ml_predictions/weekly_"]:
            res = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
            if "Contents" in res:
                all_contents.extend(res["Contents"])

        if not all_contents:
            print("\n❌ No prediction snapshots found!")
            print("\nThis means the daily cron job hasn't created any snapshots yet.")
            print("The cron job runs at 1:00 AM daily: /ml/cron/predict_daily\n")
            return False

        # Get CSV files
        snapshot_files = [obj for obj in all_contents if obj["Key"].endswith(".csv")]

        print(f"\n✅ Found {len(snapshot_files)} total prediction snapshot(s) (daily + weekly):\n")

        total_predictions = 0
        for obj in sorted(snapshot_files, key=lambda x: x["LastModified"], reverse=True):
            # Download and inspect
            buffer = BytesIO()
            s3.download_fileobj(BUCKET, obj["Key"], buffer)
            buffer.seek(0)
            df = pd.read_csv(buffer)

            print(f"📄 {obj['Key']}")
            print(f"   Created: {obj['LastModified']}")
            print(f"   Records: {len(df)} work order predictions")
            print(f"   Columns: {', '.join(df.columns.tolist())}")

            # Show sample
            if len(df) > 0:
                print(f"   Sample prediction:")
                sample = df.iloc[0]
                for col in df.columns:
                    print(f"     {col}: {sample[col]}")

            total_predictions += len(df)
            print()

        print(f"📊 Total predictions across all snapshots: {total_predictions}")
        print("\n" + "="*80)
        print("HOW THE PERFORMANCE TRACKER WORKS")
        print("="*80)
        print("""
1. Daily Snapshot Creation (1:00 AM via cron):
   - Generates predictions for ALL open work orders
   - Saves to: ml_predictions/weekly_YYYY-MM-DD.csv
   - Each row = one prediction for one work order

2. Performance Dashboard (/ml/performance_dashboard):
   - Compares predictions vs actual completion times
   - ONLY evaluates orders that have COMPLETED since the prediction
   - Calculates MAE, RMSE, confidence intervals
   - Shows trend over time

3. Multiple Predictions Per Order:
   - An open order gets predicted EVERY day until it completes
   - Example: Order #12345 might have 10 predictions over 10 days
   - Each snapshot evaluates independently - NO averaging
   - This is CORRECT behavior - shows model performance at different stages

4. When You'll See Data on the Dashboard:
   - Need: Prediction snapshots (created daily)
   - Need: Orders to COMPLETE after predictions were made
   - If snapshots exist but no completed orders → "No data available yet"
   - Dashboard updates automatically as orders complete

5. Current Status:
   - """ + str(total_predictions) + """ total predictions across """ + str(len(snapshot_files)) + """ snapshots
   - To see performance data, you need some of these predicted orders to complete
""")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_cron_models():
    """Check cron-trained models"""
    print("\n" + "="*80)
    print("CHECKING CRON-TRAINED MODELS")
    print("="*80)

    try:
        response = s3.list_objects_v2(
            Bucket=BUCKET,
            Prefix="ml_models/cron_"
        )

        if "Contents" not in response:
            print("\n❌ No cron models found")
            return

        # Get .pkl files
        model_files = [obj for obj in response["Contents"] if obj["Key"].endswith(".pkl")]

        print(f"\n✅ Found {len(model_files)} cron-trained model(s):")

        for obj in sorted(model_files, key=lambda x: x["LastModified"], reverse=True)[:5]:
            print(f"\n  📦 {obj['Key']}")
            print(f"     Created: {obj['LastModified']}")
            print(f"     Size: {obj['Size'] / 1024 / 1024:.2f} MB")

        if len(model_files) > 5:
            print(f"\n  ... and {len(model_files) - 5} more")

        print(f"\n✅ Cron retrain job is working (runs at 2:00 AM daily)")

    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("ML PERFORMANCE TRACKER STATUS CHECK")
    print("="*80)

    # Check models (proves cron retrain is working)
    check_cron_models()

    # Check prediction snapshots
    has_snapshots = check_prediction_snapshots()

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)

    if has_snapshots:
        print("""
✅ Prediction snapshots exist!

To see data on the dashboard:
1. Visit: http://localhost:5000/ml/performance_dashboard
2. If you see "No data available yet":
   - The predicted orders haven't completed yet
   - Wait for some predicted orders to finish
   - The dashboard will automatically show data once they complete

To manually trigger a new snapshot:
- POST /ml/cron/predict_daily (with X-Cron-Secret header)
- Or wait until 1:00 AM for automatic run

To test with mock data:
- We can create test snapshots that use completed orders
- This lets you see the dashboard working immediately
""")
    else:
        print("""
❌ No prediction snapshots found yet!

The cron job should create them, but it might not have run yet.

To manually create a snapshot:
curl -X POST http://localhost:5000/ml/cron/predict_weekly \\
  -H "Content-Type: application/json" \\
  -H "X-Cron-Secret: ml-retrain-secret-key-2023-secure"

Or wait until 1:00 AM for the automatic cron job.
""")