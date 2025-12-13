#!/usr/bin/env python3
"""
Create synthetic mock ML prediction data for testing the performance dashboard

This creates completely synthetic data (doesn't need database access) to demonstrate
how the performance tracker works.
"""

import boto3
import pandas as pd
import numpy as np
from io import StringIO, BytesIO
from datetime import datetime, timedelta

# S3 setup
s3 = boto3.client('s3')
BUCKET = 'awning-cleaning-data'


def create_synthetic_completed_orders(num_orders=30):
    """Create synthetic completed work orders"""
    print("\n🔨 Creating synthetic completed work orders...")

    # Create fake work order numbers
    base_wo = 56300
    work_orders = []

    for i in range(num_orders):
        wo_no = str(base_wo + i)

        # Random completion time between 3-15 days
        actual_days = np.random.randint(3, 16)

        # Date completed: random within last 10 days
        days_ago = np.random.randint(0, 11)
        date_completed = datetime.now() - timedelta(days=days_ago)

        # Date in: calculated from completion time
        date_in = date_completed - timedelta(days=actual_days)

        work_orders.append({
            'workorderid': wo_no,
            'datein': date_in,
            'datecompleted': date_completed,
            'actual_days': actual_days
        })

    df = pd.DataFrame(work_orders)
    print(f"✅ Created {len(df)} synthetic work orders")
    print(f"   Completion range: {df['actual_days'].min()} - {df['actual_days'].max()} days")
    print(f"   Mean: {df['actual_days'].mean():.1f} days")

    return df


def create_mock_snapshots_synthetic(num_snapshots=7, test_prefix=True):
    """Create mock prediction snapshots using synthetic data"""

    prefix = "test_ml_predictions" if test_prefix else "ml_predictions"
    print(f"\n📸 Creating {num_snapshots} mock prediction snapshots...")
    print(f"   Prefix: {prefix}/ {'(TEST MODE - safe)' if test_prefix else '(PRODUCTION - careful!)'}")

    # Create synthetic completed orders
    completed_df = create_synthetic_completed_orders(num_orders=25)

    created_snapshots = []

    for i in range(num_snapshots, 0, -1):
        # Create snapshot for i days ago
        snapshot_date = datetime.now() - timedelta(days=i)
        date_str = snapshot_date.strftime("%Y-%m-%d")

        # Filter to orders that were NOT completed yet at snapshot time
        # (simulates predicting open orders)
        open_at_snapshot = completed_df[
            completed_df['datecompleted'] > snapshot_date
        ].copy()

        if open_at_snapshot.empty:
            print(f"  ⏭️  {date_str}: No open orders at this time (skipping)")
            continue

        # Create predictions with realistic error
        predictions = []
        for _, row in open_at_snapshot.iterrows():
            actual = row['actual_days']

            # Simulate prediction error that gets better closer to completion
            days_until_complete = (row['datecompleted'] - snapshot_date).days

            # Error increases with time until completion
            # Early predictions are less accurate
            base_error_pct = 0.12 + (0.15 * min(days_until_complete / 10, 1.0))

            # Add noise
            error_factor = np.random.normal(1.0, base_error_pct)
            noise = np.random.normal(0, 1.2)

            predicted_days = max(1, actual * error_factor + noise)

            predictions.append({
                'workorderid': row['workorderid'],
                'prediction_date': date_str,
                'predicted_days': round(predicted_days, 2),
                'model_name': 'optuna_best',
                'model_mae_at_train': 0.541
            })

        if predictions:
            # Create DataFrame and save to S3
            pred_df = pd.DataFrame(predictions)

            key = f"{prefix}/weekly_{date_str}.csv"
            buffer = StringIO()
            pred_df.to_csv(buffer, index=False)
            buffer.seek(0)

            s3.put_object(
                Bucket=BUCKET,
                Key=key,
                Body=buffer.getvalue(),
                ContentType='text/csv'
            )

            created_snapshots.append({
                'date': date_str,
                'key': key,
                'records': len(pred_df),
                'orders': pred_df['workorderid'].nunique()
            })

            print(f"  ✅ {date_str}: {len(pred_df)} predictions for {pred_df['workorderid'].nunique()} orders")

    print(f"\n🎉 Created {len(created_snapshots)} mock snapshots!")
    return created_snapshots


def show_example_multiple_predictions():
    """Show how multiple predictions work"""
    print("\n" + "="*80)
    print("EXAMPLE: How Multiple Predictions Work")
    print("="*80)

    try:
        # List test snapshots
        response = s3.list_objects_v2(
            Bucket=BUCKET,
            Prefix="test_ml_predictions/weekly_"
        )

        if "Contents" not in response:
            print("❌ No test snapshots found - create them first!")
            return

        snapshot_files = [obj for obj in response["Contents"] if obj["Key"].endswith(".csv")]

        # Load all snapshots
        all_predictions = []
        for obj in sorted(snapshot_files, key=lambda x: x["LastModified"]):
            buffer = BytesIO()
            s3.download_fileobj(BUCKET, obj["Key"], buffer)
            buffer.seek(0)
            df = pd.read_csv(buffer)
            all_predictions.append(df)

        if not all_predictions:
            print("❌ No data in snapshots")
            return

        combined = pd.concat(all_predictions, ignore_index=True)

        # Find an order with multiple predictions
        pred_counts = combined['workorderid'].value_counts()
        multi_pred_orders = pred_counts[pred_counts > 1]

        if multi_pred_orders.empty:
            print("❌ No orders with multiple predictions found")
            return

        # Show first order with multiple predictions
        example_order = multi_pred_orders.index[0]
        order_preds = combined[combined['workorderid'] == example_order].sort_values('prediction_date')

        print(f"\n📋 Work Order #{example_order}:")
        print(f"   Total predictions: {len(order_preds)}\n")

        for idx, pred in order_preds.iterrows():
            print(f"   {pred['prediction_date']}: Predicted {pred['predicted_days']:.1f} days")

        # Calculate how each would be evaluated
        print("\n📊 How these are evaluated:")
        print("   ✓ Each prediction is evaluated SEPARATELY when the order completes")
        print("   ✓ NO averaging across dates")
        print("   ✓ Shows model performance at different lifecycle stages")
        print("   ✓ Earlier predictions typically less accurate (more uncertainty)")

        print(f"\n📈 If this order completed at day 10:")
        print(f"   - {len(order_preds)} separate error measurements")
        print(f"   - Each contributes to MAE for its snapshot date")
        print(f"   - Dashboard shows performance trend over time")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def cleanup_test_data():
    """Delete all test snapshot files"""
    print("\n🗑️  Cleaning up test data...")

    try:
        response = s3.list_objects_v2(
            Bucket=BUCKET,
            Prefix="test_ml_predictions/"
        )

        if "Contents" not in response:
            print("   No test files to delete")
            return

        delete_keys = [{'Key': obj['Key']} for obj in response["Contents"]]

        if delete_keys:
            s3.delete_objects(
                Bucket=BUCKET,
                Delete={'Objects': delete_keys}
            )
            print(f"   ✅ Deleted {len(delete_keys)} test file(s)")

    except Exception as e:
        print(f"   ❌ Error: {e}")


def main():
    print("\n" + "="*80)
    print("SYNTHETIC MOCK ML PREDICTION DATA GENERATOR")
    print("="*80)

    print("\nThis creates synthetic prediction snapshots for testing the dashboard.")
    print("Uses fake work orders (no database required).")
    print("\n⚠️  SAFE MODE: Uses 'test_ml_predictions/' prefix")

    print("\n" + "="*80)
    print("OPTIONS")
    print("="*80)
    print("1. Create 7 days of TEST snapshots (recommended)")
    print("2. Show example of multiple predictions")
    print("3. Clean up all test data")
    print("4. Exit")

    choice = input("\nEnter choice (1-4): ").strip()

    if choice == '1':
        snapshots = create_mock_snapshots_synthetic(num_snapshots=7, test_prefix=True)

        if snapshots:
            print("\n" + "="*80)
            print("✅ SUCCESS - NEXT STEPS TO TEST")
            print("="*80)
            print("""
Mock test data created successfully!

Option A - Quick Test (Modify Dashboard Temporarily):
------------------------------------------------------
1. Edit routes/ml.py line 1056:
   FROM: Prefix="ml_predictions/weekly_"
   TO:   Prefix="test_ml_predictions/weekly_"

2. Start Flask: python app.py

3. Visit: http://localhost:5000/ml/performance_dashboard

4. You should see:
   ✓ Performance chart with MAE/RMSE over time
   ✓ Statistical analysis with confidence intervals
   ✓ Trend analysis (improving/degrading/stable)
   ✓ Multiple data points showing model performance

5. IMPORTANT: Change line 1056 back to original after testing!


Option B - Check Cron Job Status (Production):
----------------------------------------------
The actual cron job for daily predictions runs at 1:00 AM.

To check if it's running:
- SSH to EB: eb ssh
- Check logs: tail -f /var/log/ml-weekly-predict.log
- Check crontab: crontab -l | grep ml-cron

To see real data on dashboard:
- Wait for cron to run (1:00 AM daily)
- Visit: /ml/performance_dashboard
- Data appears automatically as predicted orders complete


How Multiple Predictions Work:
------------------------------
Run option 2 from this menu to see a detailed example.

Clean up when done:
------------------
Run option 3 from this menu to delete test data.
""")

            # Also show an example
            print("\n" + "="*80)
            print("SAMPLE DATA CREATED")
            print("="*80)
            for snap in snapshots:
                print(f"  📄 {snap['date']}: {snap['records']} predictions")

    elif choice == '2':
        show_example_multiple_predictions()

    elif choice == '3':
        confirm = input("\n⚠️  Delete ALL test_ml_predictions/ files? (y/n): ").strip()
        if confirm.lower() == 'y':
            cleanup_test_data()
            print("✅ Test data cleaned up")
        else:
            print("❌ Cancelled")

    elif choice == '4':
        print("👋 Exiting")

    else:
        print("❌ Invalid choice")


if __name__ == "__main__":
    main()
