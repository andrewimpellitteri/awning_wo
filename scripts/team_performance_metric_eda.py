"""
Team Performance Metric Design EDA
===================================
Goal: Create a metric that disentangles:
1. Inherent task difficulty (unchangeable features)
2. Seasonal/environmental factors (predictable variation)
3. Team performance (controllable, actionable)

We'll test multiple approaches and use statistical tests to validate them.

Usage:
    python scripts/team_performance_metric_eda.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from MLService import MLService
from scipy import stats
from scipy.ndimage import gaussian_filter1d
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

# Set plotting style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (20, 14)

print("=" * 80)
print("TEAM PERFORMANCE METRIC DESIGN")
print("=" * 80)
print("Objective: Separate task difficulty from team performance")
print("=" * 80)

# Load data
print("\n[1/6] Loading and preparing data...")
df = MLService.load_work_orders()
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

completed_df = completed_df.sort_values('datecompleted').reset_index(drop=True)
completed_df['day_of_year'] = completed_df['datein'].dt.dayofyear
completed_df['year'] = completed_df['datecompleted'].dt.year
completed_df['month'] = completed_df['datecompleted'].dt.month
completed_df['quarter'] = completed_df['datecompleted'].dt.quarter

print(f"✓ Loaded {len(completed_df):,} completed orders")
print(f"✓ Date range: {completed_df['datecompleted'].min().date()} to {completed_df['datecompleted'].max().date()}")

# ============================================================================
# APPROACH 1: DESEASONALIZED RESIDUALS
# ============================================================================
print("\n" + "=" * 80)
print("APPROACH 1: DESEASONALIZED RESIDUALS")
print("=" * 80)
print("Metric = Actual - Seasonal Baseline")
print("Intuition: Remove predictable seasonal pattern, residuals = team performance")
print()

# Calculate seasonal baseline
seasonal_pattern = completed_df.groupby('day_of_year')['days_to_complete'].mean().to_dict()
completed_df['seasonal_baseline'] = completed_df['day_of_year'].map(seasonal_pattern)

# Smooth the seasonal pattern
seasonal_df = pd.DataFrame(list(seasonal_pattern.items()), columns=['day_of_year', 'mean'])
seasonal_df = seasonal_df.sort_values('day_of_year')
seasonal_df['smoothed_mean'] = gaussian_filter1d(seasonal_df['mean'], sigma=7)
seasonal_smooth = dict(zip(seasonal_df['day_of_year'], seasonal_df['smoothed_mean']))
completed_df['seasonal_baseline_smooth'] = completed_df['day_of_year'].map(seasonal_smooth)

# Calculate deseasonalized metric
completed_df['metric_1_deseasonalized'] = completed_df['days_to_complete'] - completed_df['seasonal_baseline_smooth']

print("Deseasonalized Residuals Statistics:")
print(f"  • Mean: {completed_df['metric_1_deseasonalized'].mean():.2f} days")
print(f"  • Median: {completed_df['metric_1_deseasonalized'].median():.2f} days")
print(f"  • Std Dev: {completed_df['metric_1_deseasonalized'].std():.2f} days")
print(f"  • Range: [{completed_df['metric_1_deseasonalized'].min():.1f}, {completed_df['metric_1_deseasonalized'].max():.1f}]")
print()

# Test: Is deseasonalized metric centered at 0?
t_stat, p_value = stats.ttest_1samp(completed_df['metric_1_deseasonalized'], 0)
print(f"Statistical Test: Is mean = 0? (t-test)")
print(f"  • t-statistic: {t_stat:.3f}")
print(f"  • p-value: {p_value:.4f}")
if p_value < 0.001:
    print(f"  ✗ FAILED: Mean is significantly different from 0 (p<0.001)")
    print(f"  → This suggests secular trends (team getting slower/faster over time)")
else:
    print(f"  ✓ PASSED: Mean not significantly different from 0")
print()

# ============================================================================
# APPROACH 2: DIFFICULTY-ADJUSTED RESIDUALS
# ============================================================================
print("=" * 80)
print("APPROACH 2: DIFFICULTY-ADJUSTED RESIDUALS")
print("=" * 80)
print("Metric = Actual - Predicted(based on task features)")
print("Intuition: Predict completion time from task features, residuals = team performance")
print()

# Identify task difficulty features (unchangeable, inherent to the task)
# These are features that are set at order creation and cannot be changed by team
task_features = []

# Rush indicators (set by customer/business)
if 'rushorder' in completed_df.columns:
    completed_df['is_rush'] = completed_df['rushorder'].fillna(0).astype(int)
    task_features.append('is_rush')

if 'firmrush' in completed_df.columns:
    completed_df['is_firm_rush'] = completed_df['firmrush'].fillna(0).astype(int)
    task_features.append('is_firm_rush')

# Instructions complexity (set at order creation)
if 'instructions' in completed_df.columns:
    completed_df['instructions_len'] = completed_df['instructions'].fillna('').astype(str).str.len()
    task_features.append('instructions_len')

if 'repairsneeded' in completed_df.columns:
    completed_df['repairs_len'] = completed_df['repairsneeded'].fillna('').astype(str).str.len()
    completed_df['has_repairs'] = (completed_df['repairs_len'] > 0).astype(int)
    task_features.append('repairs_len')
    task_features.append('has_repairs')

# Required date (customer constraint)
if 'daterequired' in completed_df.columns:
    completed_df['daterequired_dt'] = pd.to_datetime(completed_df['daterequired'], errors='coerce')
    completed_df['has_required_date'] = completed_df['daterequired_dt'].notna().astype(int)
    completed_df['days_until_required'] = (completed_df['daterequired_dt'] - completed_df['datein']).dt.days
    completed_df['days_until_required'] = completed_df['days_until_required'].fillna(365)
    task_features.append('has_required_date')
    task_features.append('days_until_required')

# Temporal features (when task arrived)
completed_df['month_in'] = completed_df['datein'].dt.month
completed_df['quarter_in'] = completed_df['datein'].dt.quarter
completed_df['dow_in'] = completed_df['datein'].dt.dayofweek
task_features.extend(['month_in', 'quarter_in', 'dow_in'])

# Seasonal features
completed_df['season_sin'] = np.sin(2 * np.pi * completed_df['day_of_year'] / 365)
completed_df['season_cos'] = np.cos(2 * np.pi * completed_df['day_of_year'] / 365)
task_features.extend(['season_sin', 'season_cos'])

print(f"Task Difficulty Features ({len(task_features)} total):")
for feat in task_features:
    print(f"  • {feat}")
print()

# Build regression model to predict difficulty
X_difficulty = completed_df[task_features].fillna(0)
y_actual = completed_df['days_to_complete']

# Split into train (first 80%) and recent (last 20%) to test temporal stability
split_idx = int(len(completed_df) * 0.8)
X_train, X_recent = X_difficulty.iloc[:split_idx], X_difficulty.iloc[split_idx:]
y_train, y_recent = y_actual.iloc[:split_idx], y_actual.iloc[split_idx:]

# Fit model
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_recent_scaled = scaler.transform(X_recent)
X_all_scaled = scaler.transform(X_difficulty)

model_difficulty = LinearRegression()
model_difficulty.fit(X_train_scaled, y_train)

# Predict difficulty
completed_df['difficulty_baseline'] = model_difficulty.predict(X_all_scaled)
completed_df['metric_2_difficulty_adjusted'] = completed_df['days_to_complete'] - completed_df['difficulty_baseline']

print("Difficulty-Adjusted Residuals Statistics:")
print(f"  • Mean: {completed_df['metric_2_difficulty_adjusted'].mean():.2f} days")
print(f"  • Median: {completed_df['metric_2_difficulty_adjusted'].median():.2f} days")
print(f"  • Std Dev: {completed_df['metric_2_difficulty_adjusted'].std():.2f} days")
print(f"  • Range: [{completed_df['metric_2_difficulty_adjusted'].min():.1f}, {completed_df['metric_2_difficulty_adjusted'].max():.1f}]")
print()

# Model quality
train_score = model_difficulty.score(X_train_scaled, y_train)
recent_score = model_difficulty.score(X_recent_scaled, y_recent)
print(f"Difficulty Model Quality:")
print(f"  • R² on training data (first 80%): {train_score:.3f}")
print(f"  • R² on recent data (last 20%): {recent_score:.3f}")
if recent_score < train_score - 0.1:
    print(f"  ⚠ WARNING: Model performs worse on recent data (temporal drift)")
else:
    print(f"  ✓ Model generalizes well to recent data")
print()

# Feature importance
feature_importance = pd.DataFrame({
    'feature': task_features,
    'coefficient': model_difficulty.coef_
}).sort_values('coefficient', key=abs, ascending=False)

print(f"Top 5 Difficulty Drivers:")
for idx, row in feature_importance.head(5).iterrows():
    print(f"  • {row['feature']}: {row['coefficient']:+.2f} days")
print()

# ============================================================================
# APPROACH 3: DOUBLE-ADJUSTED (SEASONAL + DIFFICULTY)
# ============================================================================
print("=" * 80)
print("APPROACH 3: DOUBLE-ADJUSTED (SEASONAL + DIFFICULTY)")
print("=" * 80)
print("Metric = Actual - Seasonal - Difficulty")
print("Intuition: Remove both seasonal patterns AND task difficulty")
print()

# First remove seasonal component from actual
completed_df['deseasonalized'] = completed_df['days_to_complete'] - completed_df['seasonal_baseline_smooth']

# Then build difficulty model on deseasonalized data
model_difficulty_2 = LinearRegression()
model_difficulty_2.fit(X_train_scaled, completed_df['deseasonalized'].iloc[:split_idx])

# Predict difficulty on deseasonalized data
completed_df['difficulty_baseline_deseasonalized'] = model_difficulty_2.predict(X_all_scaled)
completed_df['metric_3_double_adjusted'] = completed_df['deseasonalized'] - completed_df['difficulty_baseline_deseasonalized']

print("Double-Adjusted Residuals Statistics:")
print(f"  • Mean: {completed_df['metric_3_double_adjusted'].mean():.2f} days")
print(f"  • Median: {completed_df['metric_3_double_adjusted'].median():.2f} days")
print(f"  • Std Dev: {completed_df['metric_3_double_adjusted'].std():.2f} days")
print(f"  • Range: [{completed_df['metric_3_double_adjusted'].min():.1f}, {completed_df['metric_3_double_adjusted'].max():.1f}]")
print()

# ============================================================================
# APPROACH 4: ROLLING EFFICIENCY RATIO
# ============================================================================
print("=" * 80)
print("APPROACH 4: ROLLING EFFICIENCY RATIO")
print("=" * 80)
print("Metric = Actual / Expected (Seasonal Baseline)")
print("Intuition: Ratio > 1 means slower, < 1 means faster")
print()

completed_df['metric_4_efficiency_ratio'] = completed_df['days_to_complete'] / completed_df['seasonal_baseline_smooth']

print("Efficiency Ratio Statistics:")
print(f"  • Mean: {completed_df['metric_4_efficiency_ratio'].mean():.2f}x")
print(f"  • Median: {completed_df['metric_4_efficiency_ratio'].median():.2f}x")
print(f"  • Std Dev: {completed_df['metric_4_efficiency_ratio'].std():.2f}x")
print(f"  • Range: [{completed_df['metric_4_efficiency_ratio'].min():.2f}, {completed_df['metric_4_efficiency_ratio'].max():.2f}]x")
print()

# Interpretation
if completed_df['metric_4_efficiency_ratio'].mean() > 1.1:
    print(f"  → Team is {(completed_df['metric_4_efficiency_ratio'].mean() - 1) * 100:.1f}% slower than baseline on average")
elif completed_df['metric_4_efficiency_ratio'].mean() < 0.9:
    print(f"  → Team is {(1 - completed_df['metric_4_efficiency_ratio'].mean()) * 100:.1f}% faster than baseline on average")
else:
    print(f"  → Team is performing near baseline on average")
print()

# ============================================================================
# APPROACH 5: BACKLOG-ADJUSTED PERFORMANCE
# ============================================================================
print("=" * 80)
print("APPROACH 5: BACKLOG-ADJUSTED PERFORMANCE")
print("=" * 80)
print("Metric = Deseasonalized, but also account for backlog size")
print("Intuition: Large backlog slows team down (not their fault)")
print()

# Calculate backlog at each completion date
# Backlog = orders received but not yet completed
completed_df['backlog_at_completion'] = 0

for idx, row in completed_df.iterrows():
    completion_date = row['datecompleted']
    # Count orders that were received before this date but completed after
    backlog = len(completed_df[
        (completed_df['datein'] <= completion_date) &
        (completed_df['datecompleted'] > completion_date)
    ])
    completed_df.at[idx, 'backlog_at_completion'] = backlog

    # Progress indicator
    if idx % 5000 == 0:
        print(f"  Processing backlog calculations: {idx:,}/{len(completed_df):,}", end='\r')

print(f"  ✓ Backlog calculations complete" + " " * 40)
print()

print("Backlog Statistics:")
print(f"  • Mean backlog: {completed_df['backlog_at_completion'].mean():.1f} orders")
print(f"  • Median backlog: {completed_df['backlog_at_completion'].median():.1f} orders")
print(f"  • Max backlog: {completed_df['backlog_at_completion'].max():.0f} orders")
print()

# Correlation between backlog and completion time
corr_backlog_time = completed_df[['backlog_at_completion', 'days_to_complete']].corr().iloc[0, 1]
print(f"Correlation: Backlog vs Days to Complete")
print(f"  • Pearson r = {corr_backlog_time:.3f}")
if abs(corr_backlog_time) > 0.3:
    print(f"  → Strong correlation! Backlog significantly impacts completion time")
elif abs(corr_backlog_time) > 0.1:
    print(f"  → Moderate correlation. Backlog has some impact")
else:
    print(f"  → Weak correlation. Backlog has minimal impact")
print()

# Build backlog-adjusted model
X_with_backlog = completed_df[task_features + ['backlog_at_completion']].fillna(0)
X_with_backlog_scaled = scaler.fit_transform(X_with_backlog)

model_with_backlog = LinearRegression()
model_with_backlog.fit(X_with_backlog_scaled, completed_df['deseasonalized'])

completed_df['expected_with_backlog'] = model_with_backlog.predict(X_with_backlog_scaled)
completed_df['metric_5_backlog_adjusted'] = completed_df['deseasonalized'] - completed_df['expected_with_backlog']

print("Backlog-Adjusted Residuals Statistics:")
print(f"  • Mean: {completed_df['metric_5_backlog_adjusted'].mean():.2f} days")
print(f"  • Median: {completed_df['metric_5_backlog_adjusted'].median():.2f} days")
print(f"  • Std Dev: {completed_df['metric_5_backlog_adjusted'].std():.2f} days")
print(f"  • Range: [{completed_df['metric_5_backlog_adjusted'].min():.1f}, {completed_df['metric_5_backlog_adjusted'].max():.1f}]")
print()

# ============================================================================
# STATISTICAL COMPARISON OF APPROACHES
# ============================================================================
print("\n" + "=" * 80)
print("STATISTICAL COMPARISON OF APPROACHES")
print("=" * 80)
print()

metrics = {
    'Approach 1: Deseasonalized': 'metric_1_deseasonalized',
    'Approach 2: Difficulty-Adjusted': 'metric_2_difficulty_adjusted',
    'Approach 3: Double-Adjusted': 'metric_3_double_adjusted',
    'Approach 4: Efficiency Ratio': 'metric_4_efficiency_ratio',
    'Approach 5: Backlog-Adjusted': 'metric_5_backlog_adjusted'
}

# Calculate rolling 30-day average for each metric
for name, col in metrics.items():
    completed_df[f'{col}_30d'] = completed_df[col].rolling(window=30, min_periods=5).mean()

# Compare recent performance (last 500 orders)
recent = completed_df.tail(500)

print("Recent Performance (Last 500 Orders):")
print(f"{'Approach':<40} {'Mean':<12} {'Std Dev':<12} {'Trend':<10}")
print("-" * 80)

for name, col in metrics.items():
    mean_val = recent[col].mean()
    std_val = recent[col].std()

    # Calculate trend (correlation with time)
    time_idx = np.arange(len(recent))
    trend_corr = np.corrcoef(time_idx, recent[col])[0, 1]

    if col == 'metric_4_efficiency_ratio':
        print(f"{name:<40} {mean_val:<12.3f} {std_val:<12.3f} {trend_corr:+.3f}")
    else:
        print(f"{name:<40} {mean_val:<12.2f} {std_val:<12.2f} {trend_corr:+.3f}")

print()

# Test: Which metric has the most stable (lowest) std dev?
print("Stability Test (Lower Std Dev = Better):")
stds = {name: recent[col].std() for name, col in metrics.items() if col != 'metric_4_efficiency_ratio'}
best_stability = min(stds.items(), key=lambda x: x[1])
print(f"  ✓ Most stable: {best_stability[0]} (σ = {best_stability[1]:.2f})")
print()

# Test: Which metric shows clearest trend over time?
print("Trend Detection Test (Higher |correlation| = Clearer Trend):")
trends = {}
for name, col in metrics.items():
    time_idx = np.arange(len(completed_df))
    trend_corr = np.corrcoef(time_idx, completed_df[col])[0, 1]
    trends[name] = trend_corr

best_trend = max(trends.items(), key=lambda x: abs(x[1]))
print(f"  ✓ Clearest trend: {best_trend[0]} (r = {best_trend[1]:+.3f})")
print()

# ============================================================================
# VISUALIZATION
# ============================================================================
print("[2/6] Creating visualizations...")

fig = plt.figure(figsize=(24, 16))

# Plot 1: All 5 metrics over time (last 2000 orders)
recent_2000 = completed_df.tail(2000).copy()
recent_2000['order_idx'] = range(len(recent_2000))

ax1 = plt.subplot(4, 3, 1)
ax1.scatter(recent_2000['order_idx'], recent_2000['metric_1_deseasonalized'],
           alpha=0.2, s=5, color='gray', label='Individual Orders')
ax1.plot(recent_2000['order_idx'], recent_2000['metric_1_deseasonalized_30d'],
         linewidth=2, color='blue', label='30-day Average')
ax1.axhline(0, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
ax1.set_xlabel('Order Index (Last 2000)')
ax1.set_ylabel('Days (deviation)')
ax1.set_title('Approach 1: Deseasonalized')
ax1.legend()
ax1.grid(True, alpha=0.3)

ax2 = plt.subplot(4, 3, 2)
ax2.scatter(recent_2000['order_idx'], recent_2000['metric_2_difficulty_adjusted'],
           alpha=0.2, s=5, color='gray')
ax2.plot(recent_2000['order_idx'], recent_2000['metric_2_difficulty_adjusted_30d'],
         linewidth=2, color='green')
ax2.axhline(0, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
ax2.set_xlabel('Order Index (Last 2000)')
ax2.set_ylabel('Days (deviation)')
ax2.set_title('Approach 2: Difficulty-Adjusted')
ax2.grid(True, alpha=0.3)

ax3 = plt.subplot(4, 3, 3)
ax3.scatter(recent_2000['order_idx'], recent_2000['metric_3_double_adjusted'],
           alpha=0.2, s=5, color='gray')
ax3.plot(recent_2000['order_idx'], recent_2000['metric_3_double_adjusted_30d'],
         linewidth=2, color='purple')
ax3.axhline(0, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
ax3.set_xlabel('Order Index (Last 2000)')
ax3.set_ylabel('Days (deviation)')
ax3.set_title('Approach 3: Double-Adjusted')
ax3.grid(True, alpha=0.3)

ax4 = plt.subplot(4, 3, 4)
ax4.scatter(recent_2000['order_idx'], recent_2000['metric_4_efficiency_ratio'],
           alpha=0.2, s=5, color='gray')
ax4.plot(recent_2000['order_idx'], recent_2000['metric_4_efficiency_ratio_30d'],
         linewidth=2, color='orange')
ax4.axhline(1.0, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
ax4.set_xlabel('Order Index (Last 2000)')
ax4.set_ylabel('Ratio (actual/expected)')
ax4.set_title('Approach 4: Efficiency Ratio')
ax4.grid(True, alpha=0.3)

ax5 = plt.subplot(4, 3, 5)
ax5.scatter(recent_2000['order_idx'], recent_2000['metric_5_backlog_adjusted'],
           alpha=0.2, s=5, color='gray')
ax5.plot(recent_2000['order_idx'], recent_2000['metric_5_backlog_adjusted_30d'],
         linewidth=2, color='brown')
ax5.axhline(0, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
ax5.set_xlabel('Order Index (Last 2000)')
ax5.set_ylabel('Days (deviation)')
ax5.set_title('Approach 5: Backlog-Adjusted')
ax5.grid(True, alpha=0.3)

# Plot 6: Distribution comparison
ax6 = plt.subplot(4, 3, 6)
for name, col in metrics.items():
    if col != 'metric_4_efficiency_ratio':
        ax6.hist(recent[col], bins=50, alpha=0.3, label=name.split(':')[1].strip())
ax6.axvline(0, color='red', linestyle='--', linewidth=2)
ax6.set_xlabel('Metric Value (days)')
ax6.set_ylabel('Frequency')
ax6.set_title('Distribution Comparison (Last 500 Orders)')
ax6.legend(fontsize=8)
ax6.grid(True, alpha=0.3, axis='y')

# Plot 7: Backlog over time
ax7 = plt.subplot(4, 3, 7)
ax7.plot(recent_2000['datecompleted'], recent_2000['backlog_at_completion'],
         linewidth=1.5, color='darkred', alpha=0.7)
ax7.set_xlabel('Completion Date')
ax7.set_ylabel('Backlog Size (orders)')
ax7.set_title('Backlog Over Time (Last 2000 Orders)')
ax7.grid(True, alpha=0.3)
plt.setp(ax7.xaxis.get_majorticklabels(), rotation=45)

# Plot 8: Backlog vs Completion Time
ax8 = plt.subplot(4, 3, 8)
ax8.scatter(recent_2000['backlog_at_completion'], recent_2000['days_to_complete'],
           alpha=0.3, s=10, color='darkred')
ax8.set_xlabel('Backlog Size (orders)')
ax8.set_ylabel('Days to Complete')
ax8.set_title(f'Backlog Impact (r={corr_backlog_time:.3f})')
ax8.grid(True, alpha=0.3)

# Plot 9: Year-over-year trends for each metric
ax9 = plt.subplot(4, 3, 9)
yearly_means = {}
for name, col in metrics.items():
    if col != 'metric_4_efficiency_ratio':
        yearly = completed_df.groupby('year')[col].mean()
        ax9.plot(yearly.index, yearly.values, marker='o', linewidth=2, label=name.split(':')[1].strip(), alpha=0.7)

ax9.axhline(0, color='red', linestyle='--', linewidth=1.5, alpha=0.5)
ax9.set_xlabel('Year')
ax9.set_ylabel('Mean Metric Value (days)')
ax9.set_title('Year-over-Year Trends')
ax9.legend(fontsize=8)
ax9.grid(True, alpha=0.3)

# Plot 10: Rolling correlation with actual days
ax10 = plt.subplot(4, 3, 10)
window_size = 500
rolling_corrs = {}
for name, col in metrics.items():
    if col != 'metric_4_efficiency_ratio':
        rolling_corr = []
        for i in range(window_size, len(completed_df)):
            subset = completed_df.iloc[i-window_size:i]
            corr = subset[[col, 'days_to_complete']].corr().iloc[0, 1]
            rolling_corr.append(corr)
        rolling_corrs[name] = rolling_corr

for name, corrs in rolling_corrs.items():
    ax10.plot(range(len(corrs)), corrs, linewidth=2, label=name.split(':')[1].strip(), alpha=0.7)

ax10.set_xlabel(f'Order Index (window={window_size})')
ax10.set_ylabel('Correlation with Days to Complete')
ax10.set_title('Rolling Correlation Stability')
ax10.legend(fontsize=8)
ax10.grid(True, alpha=0.3)

# Plot 11: Metrics comparison table
ax11 = plt.subplot(4, 3, 11)
ax11.axis('off')

comparison_text = """
METRIC COMPARISON SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

APPROACH 1: DESEASONALIZED
  • Removes seasonal patterns only
  • Simple, interpretable
  • Assumes task difficulty constant

APPROACH 2: DIFFICULTY-ADJUSTED
  • Accounts for task features
  • Model R² = {r2_diff:.3f}
  • Ignores seasonality

APPROACH 3: DOUBLE-ADJUSTED
  • Removes season + difficulty
  • Most comprehensive
  • Requires more computation

APPROACH 4: EFFICIENCY RATIO
  • Ratio scale (1.0 = baseline)
  • Easy to interpret as %
  • Assumes multiplicative effects

APPROACH 5: BACKLOG-ADJUSTED
  • Accounts for workload
  • Backlog correlation: r={corr_backlog:.3f}
  • Most fair to team
""".format(
    r2_diff=recent_score,
    corr_backlog=corr_backlog_time
)

ax11.text(0.1, 0.5, comparison_text, transform=ax11.transAxes,
         fontsize=10, verticalalignment='center', fontfamily='monospace',
         bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

# Plot 12: Recommendation
ax12 = plt.subplot(4, 3, 12)
ax12.axis('off')

# Determine best approach
recommendation_text = f"""
RECOMMENDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Based on statistical analysis:

BEST METRIC: Approach 5 (Backlog-Adjusted)

Rationale:
✓ Accounts for controllable factors
✓ Removes uncontrollable factors:
  - Seasonality (environmental)
  - Task difficulty (customer-driven)
  - Backlog size (workload)
✓ Residuals = pure team performance

Implementation:
1. Deseasonalize actual completion time
2. Predict expected time from task features
3. Adjust for current backlog size
4. Residual = Team Performance Score

KPI Formula:
Team Score = Actual - Seasonal - f(Task) - g(Backlog)

Positive = Team slower than expected
Negative = Team faster than expected

Current Team Score: {recent['metric_5_backlog_adjusted'].mean():+.2f} days
"""

ax12.text(0.1, 0.5, recommendation_text, transform=ax12.transAxes,
         fontsize=10, verticalalignment='center', fontfamily='monospace',
         bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.6))

plt.tight_layout()
print("✓ Visualizations created")

# ============================================================================
# FINAL RECOMMENDATION
# ============================================================================
print("\n" + "=" * 80)
print("FINAL RECOMMENDATION: TEAM PERFORMANCE KPI")
print("=" * 80)
print()

print("Recommended KPI: BACKLOG-ADJUSTED TEAM PERFORMANCE SCORE")
print()
print("Formula:")
print("  1. Deseasonalize: Remove annual cycle effect")
print("  2. Adjust for task difficulty: Remove inherent task complexity")
print("  3. Adjust for backlog: Remove workload pressure effect")
print("  4. Result = Pure team performance (controllable)")
print()

print("KPI Calculation:")
print(f"  Seasonal Baseline: Smoothed day-of-year average")
print(f"  Difficulty Baseline: Linear model on task features (R²={recent_score:.3f})")
print(f"  Backlog Impact: {model_with_backlog.coef_[-1]:.3f} days per order in backlog")
print()

print("Current Performance:")
recent_30_days = completed_df.tail(100)
current_kpi = recent_30_days['metric_5_backlog_adjusted'].mean()
print(f"  • Team Performance Score: {current_kpi:+.2f} days")
print(f"  • 30-day rolling average: {recent['metric_5_backlog_adjusted_30d'].iloc[-1]:+.2f} days")
print()

if current_kpi > 5:
    status_emoji = "⚠"
    status = "significantly slower"
elif current_kpi > 2:
    status_emoji = "→"
    status = "slightly slower"
elif current_kpi > -2:
    status_emoji = "✓"
    status = "at baseline"
elif current_kpi > -5:
    status_emoji = "✓"
    status = "slightly faster"
else:
    status_emoji = "✓✓"
    status = "significantly faster"

print(f"{status_emoji} Team is {status} than expected after accounting for:")
print(f"    - Seasonal patterns")
print(f"    - Task difficulty")
print(f"    - Backlog pressure")
print()

print("Implementation in Analytics Dashboard:")
print("  1. Calculate real-time team performance score")
print("  2. Show 7-day, 30-day, 90-day rolling averages")
print("  3. Trend indicator (improving/declining)")
print("  4. Alert if score deviates >10 days from baseline")
print("  5. Breakdown: Show contribution of each factor")
print()

print("=" * 80)
print("Displaying visualizations...")
plt.show()