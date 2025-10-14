"""
Extended Throughput Features EDA
=================================
Additional visualizations and deeper analysis of throughput features.

Usage:
    python scripts/throughput_eda_extended.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from MLService import MLService
from scipy import stats

# Set plotting style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (16, 10)

print("=" * 80)
print("EXTENDED THROUGHPUT FEATURES ANALYSIS")
print("=" * 80)

# Load and prepare data
print("\n[1/3] Loading and preprocessing data...")
df = MLService.load_work_orders()
df['datein'] = pd.to_datetime(df['datein'], errors='coerce')
df['datecompleted'] = pd.to_datetime(df['datecompleted'], errors='coerce')
df['days_to_complete'] = (df['datecompleted'] - df['datein']).dt.days

completed_df = df.dropna(subset=['days_to_complete']).copy()
mean_days = completed_df['days_to_complete'].mean()
std_days = completed_df['days_to_complete'].std()
completed_df = completed_df[
    (completed_df['days_to_complete'] >= 0) &
    (completed_df['days_to_complete'] <= mean_days + 3 * std_days)
].copy()

print(f"✓ Loaded {len(completed_df)} completed orders")

print("\n[2/3] Engineering features...")
completed_df = MLService.engineer_features(completed_df)
completed_df = completed_df.sort_values('datecompleted').reset_index(drop=True)

# Add additional derived features for analysis
completed_df['month'] = completed_df['datecompleted'].dt.month
completed_df['year'] = completed_df['datecompleted'].dt.year
completed_df['quarter'] = completed_df['datecompleted'].dt.quarter
completed_df['day_of_week'] = completed_df['datecompleted'].dt.dayofweek

print("\n[3/3] Creating extended visualizations...")

# ============================================================================
# FIGURE 1: Time Series Deep Dive
# ============================================================================
fig1 = plt.figure(figsize=(20, 12))

# 1. Rolling Statistics Over Time
ax1 = plt.subplot(3, 3, 1)
window_size = 100
completed_df['rolling_mean'] = completed_df['days_to_complete'].rolling(window=window_size).mean()
completed_df['rolling_std'] = completed_df['days_to_complete'].rolling(window=window_size).std()
completed_df['upper_band'] = completed_df['rolling_mean'] + 2 * completed_df['rolling_std']
completed_df['lower_band'] = completed_df['rolling_mean'] - 2 * completed_df['rolling_std']

recent = completed_df.tail(1000)
ax1.fill_between(recent.index, recent['lower_band'], recent['upper_band'],
                  alpha=0.2, color='blue', label='±2σ Band')
ax1.plot(recent.index, recent['rolling_mean'], linewidth=2, color='blue', label='Rolling Mean')
ax1.plot(recent.index, recent['days_to_complete'], alpha=0.3, linewidth=0.5, color='gray')
ax1.set_xlabel('Order Index (Last 1000)')
ax1.set_ylabel('Days to Complete')
ax1.set_title(f'Rolling Statistics (window={window_size})')
ax1.legend()
ax1.grid(True, alpha=0.3)

# 2. Monthly Aggregated Throughput
ax2 = plt.subplot(3, 3, 2)
completed_df['year_month'] = completed_df['datecompleted'].dt.to_period('M')
monthly_agg = completed_df.groupby('year_month').agg({
    'days_to_complete': ['mean', 'median', 'count']
}).reset_index()
monthly_agg.columns = ['year_month', 'mean', 'median', 'count']
monthly_agg['year_month_str'] = monthly_agg['year_month'].astype(str)

# Plot last 24 months
recent_months = monthly_agg.tail(24)
x = range(len(recent_months))
ax2.plot(x, recent_months['mean'], marker='o', linewidth=2, label='Mean', color='red')
ax2.plot(x, recent_months['median'], marker='s', linewidth=2, label='Median', color='blue')
ax2.set_xticks(x[::3])  # Show every 3rd month
ax2.set_xticklabels(recent_months['year_month_str'].iloc[::3], rotation=45)
ax2.set_ylabel('Days to Complete')
ax2.set_title('Monthly Average Throughput (Last 24 Months)')
ax2.legend()
ax2.grid(True, alpha=0.3)

# 3. Quarterly Trends
ax3 = plt.subplot(3, 3, 3)
completed_df['year_quarter'] = completed_df['datecompleted'].dt.to_period('Q')
quarterly_agg = completed_df.groupby('year_quarter')['days_to_complete'].agg(['mean', 'count']).reset_index()
quarterly_agg['year_quarter_str'] = quarterly_agg['year_quarter'].astype(str)
recent_quarters = quarterly_agg.tail(12)

ax3_2 = ax3.twinx()
ax3.bar(range(len(recent_quarters)), recent_quarters['mean'], alpha=0.7, color='steelblue')
ax3_2.plot(range(len(recent_quarters)), recent_quarters['count'],
           marker='o', color='red', linewidth=2, label='Order Count')
ax3.set_xticks(range(len(recent_quarters)))
ax3.set_xticklabels(recent_quarters['year_quarter_str'], rotation=45)
ax3.set_ylabel('Avg Days to Complete', color='steelblue')
ax3_2.set_ylabel('Order Count', color='red')
ax3.set_title('Quarterly Throughput & Volume')
ax3.grid(True, alpha=0.3, axis='y')

# 4. Day of Week Analysis
ax4 = plt.subplot(3, 3, 4)
dow_stats = completed_df.groupby('day_of_week')['days_to_complete'].agg(['mean', 'std', 'count'])
dow_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
ax4.bar(range(7), dow_stats['mean'], yerr=dow_stats['std'],
        capsize=5, alpha=0.7, color='coral')
ax4.set_xticks(range(7))
ax4.set_xticklabels(dow_names)
ax4.set_ylabel('Avg Days to Complete')
ax4.set_title('Performance by Day of Week')
ax4.grid(True, alpha=0.3, axis='y')

# 5. Seasonal Analysis
ax5 = plt.subplot(3, 3, 5)
seasonal_stats = completed_df.groupby('month')['days_to_complete'].agg(['mean', 'std'])
month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
ax5.plot(range(1, 13), seasonal_stats['mean'], marker='o', linewidth=2, color='green')
ax5.fill_between(range(1, 13),
                  seasonal_stats['mean'] - seasonal_stats['std'],
                  seasonal_stats['mean'] + seasonal_stats['std'],
                  alpha=0.3, color='green')
ax5.set_xticks(range(1, 13))
ax5.set_xticklabels(month_names)
ax5.set_ylabel('Avg Days to Complete')
ax5.set_title('Seasonal Patterns (with ±1σ)')
ax5.grid(True, alpha=0.3)

# 6. Throughput Acceleration/Deceleration Zones
ax6 = plt.subplot(3, 3, 6)
recent_1000 = completed_df.tail(1000)
colors = ['green' if x < 0 else 'red' for x in recent_1000['throughput_trend']]
ax6.scatter(range(len(recent_1000)), recent_1000['throughput_trend'],
            c=colors, alpha=0.5, s=10)
ax6.axhline(y=0, color='black', linestyle='--', linewidth=2)
ax6.set_xlabel('Order Index (Last 1000)')
ax6.set_ylabel('Throughput Trend (7d - 90d)')
ax6.set_title('Acceleration Zones: Green=Speeding Up, Red=Slowing Down')
ax6.grid(True, alpha=0.3)

# 7. Volatility Distribution
ax7 = plt.subplot(3, 3, 7)
ax7.hist(completed_df['throughput_volatility'], bins=50, color='purple', alpha=0.7, edgecolor='black')
median_vol = completed_df['throughput_volatility'].median()
ax7.axvline(median_vol, color='red', linestyle='--', linewidth=2, label=f'Median: {median_vol:.1f}')
ax7.set_xlabel('Volatility (Std Dev of 30d window)')
ax7.set_ylabel('Frequency')
ax7.set_title('Throughput Volatility Distribution')
ax7.legend()
ax7.grid(True, alpha=0.3, axis='y')

# 8. Cumulative Orders Over Time
ax8 = plt.subplot(3, 3, 8)
completed_df['cumulative_orders'] = range(1, len(completed_df) + 1)
recent_cum = completed_df.tail(2000)
ax8.plot(recent_cum['datecompleted'], recent_cum['cumulative_orders'], linewidth=2, color='navy')
ax8.set_xlabel('Date')
ax8.set_ylabel('Cumulative Orders')
ax8.set_title('Order Completion Rate Over Time (Last 2000)')
plt.setp(ax8.xaxis.get_majorticklabels(), rotation=45)
ax8.grid(True, alpha=0.3)

# 9. Throughput Percentiles Over Time
ax9 = plt.subplot(3, 3, 9)
recent_500 = completed_df.tail(500)
window = 50
percentiles = []
for i in range(window, len(recent_500)):
    window_data = recent_500['days_to_complete'].iloc[i-window:i]
    p25, p50, p75 = np.percentile(window_data, [25, 50, 75])
    percentiles.append([p25, p50, p75])

percentiles = np.array(percentiles)
x_range = range(len(percentiles))
ax9.fill_between(x_range, percentiles[:, 0], percentiles[:, 2], alpha=0.3, color='blue')
ax9.plot(x_range, percentiles[:, 1], linewidth=2, color='blue', label='Median (P50)')
ax9.set_xlabel(f'Order Index (Last 500, window={window})')
ax9.set_ylabel('Days to Complete')
ax9.set_title('Rolling Percentiles (P25, P50, P75)')
ax9.legend()
ax9.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('throughput_extended_timeseries.png', dpi=150, bbox_inches='tight')
print("✓ Saved: throughput_extended_timeseries.png")

# ============================================================================
# FIGURE 2: Prediction Quality Analysis
# ============================================================================
fig2 = plt.figure(figsize=(20, 12))

# 1. Residual Analysis - 7d avg
ax1 = plt.subplot(3, 3, 1)
residuals_7d = completed_df['days_to_complete'] - completed_df['throughput_7d_avg']
ax1.scatter(completed_df['throughput_7d_avg'], residuals_7d, alpha=0.3, s=5)
ax1.axhline(y=0, color='red', linestyle='--', linewidth=2)
ax1.set_xlabel('7-day Average Prediction')
ax1.set_ylabel('Residual (Actual - Predicted)')
ax1.set_title('Residual Plot: 7-day Average')
ax1.grid(True, alpha=0.3)

# 2. Residual Distribution - 7d avg
ax2 = plt.subplot(3, 3, 2)
ax2.hist(residuals_7d, bins=50, color='skyblue', edgecolor='black', alpha=0.7)
ax2.axvline(0, color='red', linestyle='--', linewidth=2)
mean_resid = residuals_7d.mean()
ax2.axvline(mean_resid, color='green', linestyle='--', linewidth=2, label=f'Mean: {mean_resid:.2f}')
ax2.set_xlabel('Residual (days)')
ax2.set_ylabel('Frequency')
ax2.set_title('Residual Distribution: 7-day Average')
ax2.legend()
ax2.grid(True, alpha=0.3, axis='y')

# 3. Q-Q Plot for Residuals
ax3 = plt.subplot(3, 3, 3)
stats.probplot(residuals_7d, dist="norm", plot=ax3)
ax3.set_title('Q-Q Plot: Residual Normality Check')
ax3.grid(True, alpha=0.3)

# 4. Prediction Error by Actual Duration
ax4 = plt.subplot(3, 3, 4)
completed_df['duration_bin'] = pd.cut(completed_df['days_to_complete'], bins=10)
error_by_duration = completed_df.groupby('duration_bin').apply(
    lambda x: np.abs(x['days_to_complete'] - x['throughput_7d_avg']).mean()
)
bin_centers = [interval.mid for interval in error_by_duration.index]
ax4.plot(bin_centers, error_by_duration.values, marker='o', linewidth=2, markersize=8)
ax4.set_xlabel('Actual Duration (days)')
ax4.set_ylabel('Mean Absolute Error (days)')
ax4.set_title('Prediction Error by Duration Range')
ax4.grid(True, alpha=0.3)

# 5. Comparison: All Throughput Predictors
ax5 = plt.subplot(3, 3, 5)
mae_7d = np.abs(completed_df['days_to_complete'] - completed_df['throughput_7d_avg']).mean()
mae_30d = np.abs(completed_df['days_to_complete'] - completed_df['throughput_30d_avg']).mean()
mae_90d = np.abs(completed_df['days_to_complete'] - completed_df['throughput_90d_avg']).mean()

predictors = ['7-day\nAverage', '30-day\nAverage', '90-day\nAverage']
maes = [mae_7d, mae_30d, mae_90d]
colors_pred = ['red', 'orange', 'green']

bars = ax5.bar(range(3), maes, color=colors_pred, alpha=0.7, edgecolor='black')
ax5.set_xticks(range(3))
ax5.set_xticklabels(predictors)
ax5.set_ylabel('Mean Absolute Error (days)')
ax5.set_title('Prediction Performance Comparison')
ax5.grid(True, alpha=0.3, axis='y')

# Add value labels on bars
for i, (bar, mae) in enumerate(zip(bars, maes)):
    ax5.text(i, mae + 0.5, f'{mae:.2f}', ha='center', va='bottom', fontweight='bold')

# 6. Scatter with Trend Line - 30d
ax6 = plt.subplot(3, 3, 6)
sample = completed_df.sample(min(5000, len(completed_df)))
ax6.scatter(sample['throughput_30d_avg'], sample['days_to_complete'], alpha=0.3, s=10)
z = np.polyfit(sample['throughput_30d_avg'], sample['days_to_complete'], 1)
p = np.poly1d(z)
x_line = np.linspace(sample['throughput_30d_avg'].min(), sample['throughput_30d_avg'].max(), 100)
ax6.plot(x_line, p(x_line), "r--", linewidth=2, label=f'y={z[0]:.2f}x+{z[1]:.2f}')
ax6.plot(x_line, x_line, "g--", linewidth=2, label='Perfect (y=x)')
ax6.set_xlabel('30-day Average (days)')
ax6.set_ylabel('Actual Days to Complete')
ax6.set_title('Linear Fit: 30-day Predictor')
ax6.legend()
ax6.grid(True, alpha=0.3)

# 7. Error vs Volatility
ax7 = plt.subplot(3, 3, 7)
completed_df['abs_error_7d'] = np.abs(completed_df['days_to_complete'] - completed_df['throughput_7d_avg'])
ax7.scatter(completed_df['throughput_volatility'], completed_df['abs_error_7d'], alpha=0.3, s=5)
ax7.set_xlabel('Throughput Volatility')
ax7.set_ylabel('Absolute Prediction Error (days)')
ax7.set_title('Prediction Error vs Volatility')
ax7.grid(True, alpha=0.3)

# 8. Recent Performance Buckets
ax8 = plt.subplot(3, 3, 8)
completed_df['trend_bucket'] = pd.cut(completed_df['throughput_trend'],
                                       bins=[-np.inf, -10, -5, 5, 10, np.inf],
                                       labels=['Large Speed Up', 'Speed Up', 'Stable', 'Slow Down', 'Large Slow Down'])
trend_counts = completed_df['trend_bucket'].value_counts()
ax8.barh(range(len(trend_counts)), trend_counts.values, color='steelblue', alpha=0.7)
ax8.set_yticks(range(len(trend_counts)))
ax8.set_yticklabels(trend_counts.index)
ax8.set_xlabel('Number of Orders')
ax8.set_title('Distribution of Trend Buckets')
ax8.grid(True, alpha=0.3, axis='x')

# 9. Prediction Confidence
ax9 = plt.subplot(3, 3, 9)
completed_df['prediction_confidence'] = 1 / (1 + completed_df['throughput_volatility'] / 20)
recent_conf = completed_df.tail(500)
ax9.scatter(range(len(recent_conf)), recent_conf['prediction_confidence'],
            c=recent_conf['prediction_confidence'], cmap='RdYlGn', s=20, alpha=0.6)
ax9.set_xlabel('Order Index (Last 500)')
ax9.set_ylabel('Prediction Confidence Score')
ax9.set_title('Prediction Confidence (based on volatility)')
ax9.axhline(0.5, color='red', linestyle='--', alpha=0.5)
ax9.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('throughput_extended_prediction.png', dpi=150, bbox_inches='tight')
print("✓ Saved: throughput_extended_prediction.png")

# ============================================================================
# Print Extended Statistics
# ============================================================================
print("\n" + "=" * 80)
print("EXTENDED STATISTICS")
print("=" * 80)

print(f"\nPrediction Performance (MAE):")
print(f"  7-day average:  {mae_7d:.2f} days")
print(f"  30-day average: {mae_30d:.2f} days")
print(f"  90-day average: {mae_90d:.2f} days")
print(f"  → Best predictor: 7-day average")

print(f"\nResidual Analysis (7-day predictor):")
print(f"  Mean residual: {residuals_7d.mean():.2f} days (bias)")
print(f"  Std residual:  {residuals_7d.std():.2f} days (spread)")
print(f"  MAE:           {np.abs(residuals_7d).mean():.2f} days")

print(f"\nTrend Analysis:")
trend_dist = completed_df['trend_bucket'].value_counts()
print(trend_dist.to_string())

print(f"\nSeasonal Patterns:")
best_month = seasonal_stats['mean'].idxmin()
worst_month = seasonal_stats['mean'].idxmax()
print(f"  Fastest month: {month_names[best_month-1]} ({seasonal_stats.loc[best_month, 'mean']:.1f} days)")
print(f"  Slowest month: {month_names[worst_month-1]} ({seasonal_stats.loc[worst_month, 'mean']:.1f} days)")

print("\n" + "=" * 80)
print("EXTENDED EDA COMPLETE!")
print("=" * 80)
print("Generated:")
print("  - throughput_extended_timeseries.png (9 time series analyses)")
print("  - throughput_extended_prediction.png (9 prediction quality checks)")