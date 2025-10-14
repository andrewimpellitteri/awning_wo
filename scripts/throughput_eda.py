"""
Throughput Features EDA Script
===============================
Analyze and visualize the new throughput features to understand
how team performance has evolved over time.

Usage:
    python scripts/throughput_eda.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from MLService import MLService

# Set plotting style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (15, 10)

print("=" * 80)
print("THROUGHPUT FEATURES - EXPLORATORY DATA ANALYSIS")
print("=" * 80)

# Load data
print("\n[1/5] Loading work orders from database...")
df = MLService.load_work_orders()
if df is None or df.empty:
    raise ValueError("No data available")
print(f"✓ Loaded {len(df)} work orders")

# Preprocess (WITHOUT augmentation for EDA - we want real data only)
print("\n[2/5] Preprocessing data...")
df['datein'] = pd.to_datetime(df['datein'], errors='coerce')
df['datecompleted'] = pd.to_datetime(df['datecompleted'], errors='coerce')
df['days_to_complete'] = (df['datecompleted'] - df['datein']).dt.days

# Filter completed orders and outliers
completed_df = df.dropna(subset=['days_to_complete']).copy()
mean_days = completed_df['days_to_complete'].mean()
std_days = completed_df['days_to_complete'].std()
completed_df = completed_df[
    (completed_df['days_to_complete'] >= 0) &
    (completed_df['days_to_complete'] <= mean_days + 3 * std_days)
].copy()
print(f"✓ Filtered to {len(completed_df)} completed orders (removed outliers)")

# Engineer features
print("\n[3/5] Engineering throughput features...")
completed_df = MLService.engineer_features(completed_df)
print(f"✓ Features engineered")

# Sort by completion date for time series
completed_df = completed_df.sort_values('datecompleted').reset_index(drop=True)

print("\n[4/5] Calculating statistics...")
# Basic statistics
print("\n" + "=" * 80)
print("THROUGHPUT FEATURE STATISTICS")
print("=" * 80)

throughput_features = [
    'throughput_7d_avg',
    'throughput_30d_avg',
    'throughput_90d_avg',
    'throughput_volatility',
    'throughput_trend'
]

stats_df = completed_df[throughput_features].describe()
print(stats_df.to_string())

print("\n" + "=" * 80)
print("CORRELATION WITH ACTUAL COMPLETION TIME")
print("=" * 80)
correlations = completed_df[throughput_features + ['days_to_complete']].corr()['days_to_complete'].drop('days_to_complete')
print(correlations.sort_values(ascending=False).to_string())

print("\n[5/5] Generating visualizations...")

# Create figure with subplots
fig = plt.figure(figsize=(20, 12))

# 1. Time Series - Throughput Evolution
ax1 = plt.subplot(3, 3, 1)
completed_df_recent = completed_df.tail(500)  # Last 500 orders
ax1.plot(completed_df_recent['datecompleted'], completed_df_recent['days_to_complete'],
         alpha=0.3, label='Actual', linewidth=1)
ax1.plot(completed_df_recent['datecompleted'], completed_df_recent['throughput_7d_avg'],
         label='7-day MA', linewidth=2, color='red')
ax1.plot(completed_df_recent['datecompleted'], completed_df_recent['throughput_30d_avg'],
         label='30-day MA', linewidth=2, color='orange')
ax1.plot(completed_df_recent['datecompleted'], completed_df_recent['throughput_90d_avg'],
         label='90-day MA', linewidth=2, color='green')
ax1.set_xlabel('Completion Date')
ax1.set_ylabel('Days to Complete')
ax1.set_title('Throughput Moving Averages Over Time (Last 500 Orders)')
ax1.legend()
ax1.grid(True, alpha=0.3)
plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

# 2. Distribution - Throughput Averages
ax2 = plt.subplot(3, 3, 2)
ax2.hist(completed_df['throughput_7d_avg'], bins=50, alpha=0.5, label='7-day', color='red')
ax2.hist(completed_df['throughput_30d_avg'], bins=50, alpha=0.5, label='30-day', color='orange')
ax2.hist(completed_df['throughput_90d_avg'], bins=50, alpha=0.5, label='90-day', color='green')
ax2.set_xlabel('Average Days to Complete')
ax2.set_ylabel('Frequency')
ax2.set_title('Distribution of Throughput Averages')
ax2.legend()
ax2.grid(True, alpha=0.3)

# 3. Volatility Over Time
ax3 = plt.subplot(3, 3, 3)
ax3.plot(completed_df_recent['datecompleted'], completed_df_recent['throughput_volatility'],
         linewidth=2, color='purple')
ax3.set_xlabel('Completion Date')
ax3.set_ylabel('Volatility (Std Dev)')
ax3.set_title('Throughput Volatility Over Time (30-day window)')
ax3.grid(True, alpha=0.3)
plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)

# 4. Trend Analysis
ax4 = plt.subplot(3, 3, 4)
ax4.plot(completed_df_recent['datecompleted'], completed_df_recent['throughput_trend'],
         linewidth=2, color='blue')
ax4.axhline(y=0, color='black', linestyle='--', alpha=0.5)
ax4.set_xlabel('Completion Date')
ax4.set_ylabel('Trend (7d - 90d avg)')
ax4.set_title('Throughput Trend: Acceleration/Deceleration')
ax4.grid(True, alpha=0.3)
plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45)

# 5. Scatter: Actual vs 7-day Average
ax5 = plt.subplot(3, 3, 5)
ax5.scatter(completed_df['throughput_7d_avg'], completed_df['days_to_complete'],
            alpha=0.3, s=10)
max_val = max(completed_df['days_to_complete'].max(), completed_df['throughput_7d_avg'].max())
ax5.plot([0, max_val], [0, max_val], 'r--', label='Perfect Prediction')
ax5.set_xlabel('7-day Average (days)')
ax5.set_ylabel('Actual Days to Complete')
ax5.set_title('Actual vs 7-day Throughput Average')
ax5.legend()
ax5.grid(True, alpha=0.3)

# 6. Scatter: Actual vs 30-day Average
ax6 = plt.subplot(3, 3, 6)
ax6.scatter(completed_df['throughput_30d_avg'], completed_df['days_to_complete'],
            alpha=0.3, s=10, color='orange')
ax6.plot([0, max_val], [0, max_val], 'r--', label='Perfect Prediction')
ax6.set_xlabel('30-day Average (days)')
ax6.set_ylabel('Actual Days to Complete')
ax6.set_title('Actual vs 30-day Throughput Average')
ax6.legend()
ax6.grid(True, alpha=0.3)

# 7. Yearly Comparison
ax7 = plt.subplot(3, 3, 7)
completed_df['year'] = completed_df['datecompleted'].dt.year
years = sorted(completed_df['year'].unique())[-3:]  # Last 3 years
yearly_means = [completed_df[completed_df['year'] == y]['throughput_30d_avg'].mean() for y in years]
ax7.bar(range(len(years)), yearly_means, color='steelblue', alpha=0.7)
ax7.set_xticks(range(len(years)))
ax7.set_xticklabels(years)
ax7.set_xlabel('Year')
ax7.set_ylabel('30-day Average (days)')
ax7.set_title('Average Throughput by Year')
ax7.grid(True, alpha=0.3, axis='y')

# 8. Correlation Heatmap
ax8 = plt.subplot(3, 3, 8)
corr_features = throughput_features + ['days_to_complete']
correlation_matrix = completed_df[corr_features].corr()
sns.heatmap(correlation_matrix, annot=True, fmt='.3f', cmap='coolwarm', center=0, ax=ax8)
ax8.set_title('Throughput Feature Correlations')

# 9. Recent vs Historical Performance
ax9 = plt.subplot(3, 3, 9)
recent_threshold = completed_df['datecompleted'].max() - pd.Timedelta(days=90)
recent_data = completed_df[completed_df['datecompleted'] >= recent_threshold]
historical_data = completed_df[completed_df['datecompleted'] < recent_threshold]

categories = ['Recent\n(Last 90 days)', 'Historical\n(Before 90 days)']
means = [recent_data['days_to_complete'].mean(), historical_data['days_to_complete'].mean()]
stds = [recent_data['days_to_complete'].std(), historical_data['days_to_complete'].std()]

x_pos = np.arange(len(categories))
ax9.bar(x_pos, means, yerr=stds, capsize=10, color=['red', 'green'], alpha=0.7)
ax9.set_xticks(x_pos)
ax9.set_xticklabels(categories)
ax9.set_ylabel('Days to Complete')
ax9.set_title('Recent vs Historical Performance')
ax9.grid(True, alpha=0.3, axis='y')

# Add value labels
for i, (mean, std) in enumerate(zip(means, stds)):
    ax9.text(i, mean + std + 0.5, f'{mean:.1f}±{std:.1f}',
             ha='center', va='bottom', fontweight='bold')

plt.tight_layout()
plt.savefig('throughput_features_eda.png', dpi=150, bbox_inches='tight')
print("✓ Visualization saved to: throughput_features_eda.png")

# Key insights
print("\n" + "=" * 80)
print("KEY INSIGHTS")
print("=" * 80)

recent_trend = completed_df.tail(100)['throughput_trend'].mean()
if recent_trend > 0:
    print(f"SLOWING DOWN: Recent trend = +{recent_trend:.2f} days")
elif recent_trend < 0:
    print(f"SPEEDING UP: Recent trend = {recent_trend:.2f} days")
else:
    print(f"STABLE: Recent trend ≈ 0")

recent_perf = recent_data['days_to_complete'].mean()
historical_perf = historical_data['days_to_complete'].mean()
improvement_pct = ((historical_perf - recent_perf) / historical_perf) * 100
print(f"Performance change: {improvement_pct:+.1f}% vs historical")

print("\n" + "=" * 80)
print("EDA COMPLETE - Review throughput_features_eda.png")
print("=" * 80)
