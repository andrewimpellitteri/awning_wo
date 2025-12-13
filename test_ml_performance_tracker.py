#!/usr/bin/env python3
"""
Test script for ML performance tracker

This script:
1. Checks if prediction snapshots exist in S3
2. Creates mock prediction snapshots for testing (without overwriting real data)
3. Shows how the dashboard handles orders with multiple predictions
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO, StringIO

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db
from models.work_order import WorkOrder
from utils.file_upload import s3_client, AWS_S3_BUCKET


def check_existing_snapshots():
    """Check what prediction snapshots already exist in S3"""
    print("\n" + "="*80)
    print("CHECKING EXISTING PREDICTION SNAPSHOTS IN S3")
    print("="*80)

    try:
        response = s3_client.list_objects_v2(
            Bucket=AWS_S3_BUCKET,
            Prefix="ml_predictions/weekly_"
        )

        if "Contents" not in response:
            print("❌ No prediction snapshots found in S3")
            return []

        snapshot_files = [obj for obj in response["Contents"] if obj["Key"].endswith(".csv")]

        print(f"✅ Found {len(snapshot_files)} prediction snapshot(s):\n")
        for obj in sorted(snapshot_files, key=lambda x: x["LastModified"], reverse=True):
            # Download and peek at the file
            buffer = BytesIO()
            s3_client.download_fileobj(AWS_S3_BUCKET, obj["Key"], buffer)
            buffer.seek(0)
            df = pd.read_csv(buffer)

            print(f"  📄 {obj['Key']}")
            print(f"     Created: {obj['LastModified']}")
            print(f"     Records: {len(df)} work orders")
            print(f"     Columns: {', '.join(df.columns.tolist())}")
            print()

        return snapshot_files

    except Exception as e:
        print(f"❌ Error checking S3: {e}")
        return []


def analyze_completed_orders():
    """Analyze completed work orders to understand what data we have"""
    print("\n" + "="*80)
    print("ANALYZING COMPLETED WORK ORDERS")
    print("="*80)

    with app.app_context():
        # Get all completed orders from the last 90 days
        cutoff_date = datetime.now() - timedelta(days=90)
        completed = WorkOrder.query.filter(
            WorkOrder.DateCompleted.isnot(None),
            WorkOrder.DateCompleted >= cutoff_date
        ).all()

        print(f"✅ Found {len(completed)} completed orders in last 90 days\n")

        if completed:
            # Calculate actual completion times
            completion_times = []
            for wo in completed:
                if wo.DateIn and wo.DateCompleted:
                    days = (wo.DateCompleted - pd.to_datetime(wo.DateIn)).days
                    completion_times.append(days)

            if completion_times:
                print(f"Completion time statistics:")
                print(f"  Mean: {np.mean(completion_times):.1f} days")
                print(f"  Median: {np.median(completion_times):.1f} days")
                print(f"  Min: {np.min(completion_times):.1f} days")
                print(f"  Max: {np.max(completion_times):.1f} days")
                print(f"  Std: {np.std(completion_times):.1f} days")

        # Get currently open orders
        open_orders = WorkOrder.query.filter(
            WorkOrder.DateCompleted.is_(None)
        ).count()

        print(f"\n📊 Currently open orders: {open_orders}")

        return completed, open_orders


def create_mock_prediction_snapshots(num_snapshots=5, test_mode=True):
    """
    Create mock prediction snapshots for testing

    Args:
        num_snapshots: Number of daily snapshots to create (default 5)
        test_mode: If True, saves to test_ml_predictions/ prefix instead of ml_predictions/
    """
    print("\n" + "="*80)
    print("CREATING MOCK PREDICTION SNAPSHOTS")
    print("="*80)

    if test_mode:
        print("🧪 TEST MODE: Saving to 'test_ml_predictions/' prefix (won't affect real data)")
    else:
        print("⚠️  PRODUCTION MODE: Will save to 'ml_predictions/' prefix")

    with app.app_context():
        # Get some completed orders to use as test data
        completed = WorkOrder.query.filter(
            WorkOrder.DateCompleted.isnot(None)
        ).order_by(WorkOrder.DateCompleted.desc()).limit(20).all()

        if not completed:
            print("❌ No completed orders found - cannot create mock data")
            return

        print(f"✅ Using {len(completed)} completed orders for mock data\n")

        # Create snapshots for the past N days
        snapshots_created = []
        for i in range(num_snapshots, 0, -1):
            snapshot_date = datetime.now() - timedelta(days=i)
            date_str = snapshot_date.strftime("%Y-%m-%d")

            # Create predictions for a random subset of orders
            # Simulate the scenario where orders complete at different times
            num_orders = min(len(completed), np.random.randint(5, 15))
            sample_orders = np.random.choice(completed, size=num_orders, replace=False)

            predictions = []
            for wo in sample_orders:
                # Calculate actual completion time
                if wo.DateIn and wo.DateCompleted:
                    actual_days = (wo.DateCompleted - pd.to_datetime(wo.DateIn)).days

                    # Create a prediction with some error
                    # Add realistic error: ±20% with some noise
                    error_factor = np.random.normal(1.0, 0.2)
                    predicted_days = max(1, actual_days * error_factor + np.random.normal(0, 2))

                    predictions.append({
                        "workorderid": wo.WorkOrderNo,
                        "prediction_date": date_str,
                        "predicted_days": round(predicted_days, 2),
                        "model_name": "optuna_best",
                        "model_mae_at_train": 0.541  # From the config
                    })

            if predictions:
                # Create DataFrame
                df = pd.DataFrame(predictions)

                # Save to S3
                prefix = "test_ml_predictions" if test_mode else "ml_predictions"
                key = f"{prefix}/weekly_{date_str}.csv"

                buffer = StringIO()
                df.to_csv(buffer, index=False)
                buffer.seek(0)

                s3_client.put_object(
                    Bucket=AWS_S3_BUCKET,
                    Key=key,
                    Body=buffer.getvalue(),
                    ContentType="text/csv"
                )

                snapshots_created.append({
                    "date": date_str,
                    "key": key,
                    "records": len(df)
                })

                print(f"  ✅ Created snapshot: {key} ({len(df)} predictions)")

        print(f"\n🎉 Created {len(snapshots_created)} mock snapshots")

        return snapshots_created


def demonstrate_multiple_predictions():
    """
    Demonstrate how the dashboard handles orders with multiple predictions
    """
    print("\n" + "="*80)
    print("HOW MULTIPLE PREDICTIONS ARE HANDLED")
    print("="*80)

    print("""
Current Behavior:
-----------------
1. Daily Snapshot Creation (1:00 AM):
   - Creates ONE prediction per open work order
   - Saves to: ml_predictions/weekly_YYYY-MM-DD.csv

2. When an Order Completes:
   - The order may have been predicted on multiple days (multiple snapshots)
   - Example: Order #12345 predicted on:
     * 2024-12-01: predicted 5 days
     * 2024-12-02: predicted 4 days
     * 2024-12-03: predicted 6 days
     * Completed on 2024-12-05: actual 5 days

3. Dashboard Evaluation (Current Implementation):
   - Each snapshot is evaluated INDEPENDENTLY
   - The 3 predictions above would appear as 3 separate data points
   - Each contributes to the overall MAE calculation for that snapshot
   - NO AVERAGING across predictions for the same order

4. Recommendation:
   - The current approach is CORRECT for time-series performance tracking
   - It shows model performance at different stages (early vs late prediction)
   - If you want to see "last prediction before completion", you could filter
     to only the most recent prediction per order

5. To View Individual Order Performance:
   - Currently not implemented
   - Would require a new endpoint to show:
     * All predictions for a specific work order
     * How accuracy changed as the order progressed
     * When the prediction was most accurate
""")


def main():
    """Main test function"""
    print("\n" + "="*80)
    print("ML PERFORMANCE TRACKER TEST SCRIPT")
    print("="*80)

    # Check existing snapshots
    existing = check_existing_snapshots()

    # Analyze completed orders
    completed, open_count = analyze_completed_orders()

    # Explain how multiple predictions work
    demonstrate_multiple_predictions()

    # Offer to create mock data
    print("\n" + "="*80)
    print("CREATE MOCK DATA FOR TESTING?")
    print("="*80)

    if len(existing) > 0:
        print("⚠️  WARNING: Real prediction snapshots already exist!")
        print("   We will create TEST snapshots with 'test_ml_predictions/' prefix")
        print("   These won't affect your real data.\n")

    response = input("Create 5 days of mock prediction snapshots? (y/n): ")

    if response.lower() == 'y':
        # Always use test mode to avoid overwriting real data
        create_mock_prediction_snapshots(num_snapshots=5, test_mode=True)

        print("\n" + "="*80)
        print("NEXT STEPS")
        print("="*80)
        print("""
1. View the mock data in S3:
   Prefix: test_ml_predictions/weekly_*

2. To test the dashboard with mock data:
   - Temporarily modify routes/ml.py performance_dashboard()
   - Change line 1056: Prefix="test_ml_predictions/weekly_"
   - Visit /ml/performance_dashboard
   - Remember to change it back!

3. To see real data on the dashboard:
   - Wait for the cron job to run (1:00 AM daily)
   - Or manually trigger: POST /ml/cron/predict_weekly
   - Visit /ml/performance_dashboard after some orders complete

4. The dashboard updates automatically as orders complete
   - No action needed once snapshots exist
   - Performance tracking happens retroactively
""")
    else:
        print("\nSkipping mock data creation.")

        if len(existing) == 0:
            print("\n⚠️  No prediction snapshots found!")
            print("   The cron job should create them daily at 1:00 AM")
            print("   Or manually trigger with: POST /ml/cron/predict_weekly")


if __name__ == "__main__":
    main()