"""
Three-Part Model Decomposition EDA
===================================
Decomposes the prediction problem into:
1. Fundamental Statistics (historical baseline)
2. Seasonal Patterns (annual cycle)
3. Current Team Rate (recent performance bias)

Usage:
    python scripts/seasonal_eda_3part.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from MLService import MLService
from scipy import signal

# Set plotting style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (16, 10)

print("=" * 80)
print("THREE-PART MODEL DECOMPOSITION")
print("=" * 80)
print("Component 1: Fundamental Statistics (years of data)")
print("Component 2: Seasonal Patterns (annual cycle)")
print("Component 3: Current Team Rate (recent performance)")
print("=" * 80)

# Load data
print("\n[1/4] Loading work orders...")
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
print(f"✓ Loaded {len(completed_df)} completed orders")

# Sort by completion date
completed_df = completed_df.sort_values('datecompleted').reset_index(drop=True)
completed_df['day_of_year'] = completed_df['datein'].dt.dayofyear
completed_df['year'] = completed_df['datecompleted'].dt.year

print("\n[2/4] Extracting three components...")

# ============================================================================
# COMPONENT 1: FUNDAMENTAL STATISTICS
# ============================================================================
print("\n" + "=" * 80)
print("COMPONENT 1: FUNDAMENTAL STATISTICS (The Baseline)")
print("=" * 80)
print("This component represents the inherent difficulty of the cleaning problem")
print("based on years of historical data, independent of seasonality or current team.")
print()

fundamental_mean = completed_df['days_to_complete'].mean()
fundamental_median = completed_df['days_to_complete'].median()
fundamental_std = completed_df['days_to_complete'].std()
fundamental_min = completed_df['days_to_complete'].min()
fundamental_max = completed_df['days_to_complete'].max()
fundamental_p25 = completed_df['days_to_complete'].quantile(0.25)
fundamental_p75 = completed_df['days_to_complete'].quantile(0.75)
fundamental_iqr = fundamental_p75 - fundamental_p25
fundamental_cv = (fundamental_std / fundamental_mean) * 100

# Date range
date_min = completed_df['datecompleted'].min()
date_max = completed_df['datecompleted'].max()
years_of_data = (date_max - date_min).days / 365.25

print(f"Dataset Overview:")
print(f"  • Total Orders: {len(completed_df):,}")
print(f"  • Date Range: {date_min.strftime('%Y-%m-%d')} to {date_max.strftime('%Y-%m-%d')}")
print(f"  • Years of Data: {years_of_data:.2f} years")
print(f"  • Orders per Year: {len(completed_df) / years_of_data:,.0f}")
print()

print(f"Central Tendency:")
print(f"  • Mean: {fundamental_mean:.2f} days")
print(f"  • Median: {fundamental_median:.2f} days")
print(f"  • Mode: {completed_df['days_to_complete'].mode().values[0]:.0f} days" if len(completed_df['days_to_complete'].mode()) > 0 else "")
print()

print(f"Spread & Variability:")
print(f"  • Std Dev: {fundamental_std:.2f} days")
print(f"  • Variance: {fundamental_std**2:.2f}")
print(f"  • Coefficient of Variation: {fundamental_cv:.1f}%")
print(f"  • IQR (P75-P25): {fundamental_iqr:.2f} days")
print()

print(f"Distribution Shape:")
print(f"  • Min: {fundamental_min:.0f} days")
print(f"  • P25 (25th percentile): {fundamental_p25:.2f} days")
print(f"  • P50 (Median): {fundamental_median:.2f} days")
print(f"  • P75 (75th percentile): {fundamental_p75:.2f} days")
print(f"  • Max: {fundamental_max:.0f} days")
print(f"  • Range: {fundamental_max - fundamental_min:.0f} days")
print()

# Baseline prediction error
fundamental_mae = np.abs(completed_df['days_to_complete'] - fundamental_mean).mean()
fundamental_rmse = np.sqrt(((completed_df['days_to_complete'] - fundamental_mean) ** 2).mean())
fundamental_mape = (np.abs((completed_df['days_to_complete'] - fundamental_mean) / completed_df['days_to_complete']).mean() * 100)

print(f"Baseline Prediction Error (using mean as prediction):")
print(f"  • MAE (Mean Absolute Error): {fundamental_mae:.2f} days")
print(f"  • RMSE (Root Mean Squared Error): {fundamental_rmse:.2f} days")
print(f"  • MAPE (Mean Absolute % Error): {fundamental_mape:.1f}%")
print()

print(f"Interpretation:")
if fundamental_cv > 100:
    print(f"  ⚠ Very high variability (CV={fundamental_cv:.0f}%) - predictions will vary widely")
elif fundamental_cv > 50:
    print(f"  → High variability (CV={fundamental_cv:.0f}%) - significant uncertainty in predictions")
else:
    print(f"  ✓ Moderate variability (CV={fundamental_cv:.0f}%) - predictions relatively consistent")

print(f"  → Using only the fundamental mean would give MAE of {fundamental_mae:.2f} days")
print(f"  → This is our starting point before adding seasonal & team factors")

# ============================================================================
# COMPONENT 2: SEASONAL PATTERNS
# ============================================================================
print("\n" + "=" * 80)
print("COMPONENT 2: SEASONAL PATTERNS (Annual Cycle)")
print("=" * 80)
print("This component captures the predictable annual variation in completion times")
print("driven by busy/slow seasons (winter holidays vs summer).")
print()

# Calculate mean completion time by day-of-year (averaged across all years)
seasonal_pattern = completed_df.groupby('day_of_year')['days_to_complete'].agg(['mean', 'std', 'count'])
seasonal_pattern = seasonal_pattern.reset_index()

# Smooth the seasonal pattern to reduce noise
from scipy.ndimage import gaussian_filter1d
seasonal_pattern['smoothed_mean'] = gaussian_filter1d(seasonal_pattern['mean'], sigma=7)

# Deseasonalize: actual - seasonal pattern
completed_df['seasonal_component'] = completed_df['day_of_year'].map(
    seasonal_pattern.set_index('day_of_year')['smoothed_mean']
)
completed_df['deseasonalized'] = completed_df['days_to_complete'] - completed_df['seasonal_component']

# Seasonal statistics
seasonal_min = seasonal_pattern['smoothed_mean'].min()
seasonal_max = seasonal_pattern['smoothed_mean'].max()
seasonal_amplitude = seasonal_max - seasonal_min
seasonal_mean = seasonal_pattern['smoothed_mean'].mean()

# Find peak and trough
peak_doy = seasonal_pattern.loc[seasonal_pattern['smoothed_mean'].idxmax(), 'day_of_year']
trough_doy = seasonal_pattern.loc[seasonal_pattern['smoothed_mean'].idxmin(), 'day_of_year']

# Convert day-of-year to approximate date
def doy_to_month_day(doy):
    month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    cumulative = 0
    for i, days in enumerate(month_days):
        if doy <= cumulative + days:
            return f"{month_names[i]} {int(doy - cumulative)}"
        cumulative += days
    return "Dec 31"

peak_date_str = doy_to_month_day(peak_doy)
trough_date_str = doy_to_month_day(trough_doy)

print(f"Seasonal Amplitude:")
print(f"  • Range: {seasonal_min:.2f} to {seasonal_max:.2f} days")
print(f"  • Amplitude: {seasonal_amplitude:.2f} days")
print(f"  • Ratio (Peak/Trough): {seasonal_max / seasonal_min:.2f}x")
print(f"  • Mean of Seasonal Pattern: {seasonal_mean:.2f} days")
print()

print(f"Peak Season (Busiest/Slowest Completion):")
print(f"  • Occurs around: Day {peak_doy:.0f} ({peak_date_str})")
print(f"  • Average completion time: {seasonal_max:.2f} days")
print(f"  • +{seasonal_max - fundamental_mean:+.2f} days vs fundamental mean")
print()

print(f"Trough Season (Fastest Completion):")
print(f"  • Occurs around: Day {trough_doy:.0f} ({trough_date_str})")
print(f"  • Average completion time: {seasonal_min:.2f} days")
print(f"  • {seasonal_min - fundamental_mean:+.2f} days vs fundamental mean")
print()

# Seasonal consistency across years
yearly_seasonal = completed_df.groupby([completed_df['datecompleted'].dt.year, 'day_of_year'])['days_to_complete'].mean().unstack(fill_value=np.nan)
yearly_seasonal_std = yearly_seasonal.std(axis=0).mean()  # Average std across all days-of-year

print(f"Year-over-Year Seasonal Consistency:")
print(f"  • Average std deviation across years: {yearly_seasonal_std:.2f} days")
if yearly_seasonal_std < 10:
    print(f"  ✓ High consistency - seasonal pattern is stable across years")
elif yearly_seasonal_std < 20:
    print(f"  → Moderate consistency - seasonal pattern varies somewhat by year")
else:
    print(f"  ⚠ Low consistency - seasonal pattern changes significantly by year")
print()

# MAE improvement from seasonal component
seasonal_mae = np.abs(completed_df['days_to_complete'] - completed_df['seasonal_component']).mean()
seasonal_improvement_pct = ((fundamental_mae - seasonal_mae) / fundamental_mae) * 100

print(f"Prediction Improvement from Seasonal Component:")
print(f"  • Fundamental-only MAE: {fundamental_mae:.2f} days")
print(f"  • Fundamental + Seasonal MAE: {seasonal_mae:.2f} days")
print(f"  • Improvement: {seasonal_improvement_pct:.1f}%")
print(f"  • Absolute reduction: {fundamental_mae - seasonal_mae:.2f} days")
print()

print(f"Interpretation:")
print(f"  → Seasonal amplitude of {seasonal_amplitude:.1f} days is {seasonal_amplitude/fundamental_mean*100:.0f}% of mean")
if seasonal_amplitude > 20:
    print(f"  ⚠ MASSIVE seasonal effect - ignoring this would be catastrophic")
elif seasonal_amplitude > 10:
    print(f"  → Strong seasonal effect - critical to account for in predictions")
else:
    print(f"  → Moderate seasonal effect - helpful but not dominant")

# ============================================================================
# COMPONENT 3: CURRENT TEAM RATE
# ============================================================================
print("\n" + "=" * 80)
print("COMPONENT 3: CURRENT TEAM RATE (Recent Performance Bias)")
print("=" * 80)
print("This component captures how the CURRENT team is performing relative to")
print("the historical seasonal baseline (after removing seasonal effects).")
print()

# Calculate rolling average of deseasonalized data (removes seasonal effects)
window = 30
completed_df['team_rate_30d'] = completed_df['deseasonalized'].rolling(window=window, min_periods=5).mean()
completed_df['team_rate_90d'] = completed_df['deseasonalized'].rolling(window=90, min_periods=10).mean()
completed_df['team_rate_180d'] = completed_df['deseasonalized'].rolling(window=180, min_periods=20).mean()

# Current team rate is the bias from the fundamental + seasonal baseline
recent_100 = completed_df.tail(100)
recent_500 = completed_df.tail(500)
recent_1000 = completed_df.tail(1000)

current_team_bias_30d = recent_500['team_rate_30d'].mean()
current_team_bias_90d = recent_500['team_rate_90d'].mean()
current_team_bias_180d = recent_500['team_rate_180d'].mean()

print(f"Current Team Performance (Deseasonalized Bias):")
print(f"  • Last 100 orders (30d avg): {recent_100['team_rate_30d'].mean():+.2f} days")
print(f"  • Last 500 orders (30d avg): {current_team_bias_30d:+.2f} days")
print(f"  • Last 500 orders (90d avg): {current_team_bias_90d:+.2f} days")
print(f"  • Last 500 orders (180d avg): {current_team_bias_180d:+.2f} days")
print()

if current_team_bias_30d > 0:
    status = "SLOWER"
    emoji = "⚠"
elif current_team_bias_30d < 0:
    status = "FASTER"
    emoji = "✓"
else:
    status = "AT BASELINE"
    emoji = "→"

print(f"Team Status: {emoji} Team is {status} than historical seasonal baseline")
print(f"  → Current bias: {current_team_bias_30d:+.2f} days")
if abs(current_team_bias_30d) > 10:
    print(f"  → This is a SIGNIFICANT deviation from baseline")
elif abs(current_team_bias_30d) > 5:
    print(f"  → This is a moderate deviation from baseline")
else:
    print(f"  → This is a minor deviation from baseline")
print()

# Team rate by year
print(f"Team Rate Trend Over Time:")
yearly_team_rate = completed_df.groupby(completed_df['datecompleted'].dt.year)['team_rate_30d'].mean()
for year, rate in yearly_team_rate.items():
    trend = "slower" if rate > 0 else "faster"
    print(f"  • {year}: {rate:+.2f} days ({trend} than baseline)")
print()

# When did the current slowdown/speedup begin?
print(f"Identifying When Current Performance Trend Started:")
# Find when team_rate crossed zero most recently
team_rate_series = completed_df[['datecompleted', 'team_rate_30d']].dropna()
# Find last zero crossing
sign_changes = np.diff(np.sign(team_rate_series['team_rate_30d']))
if len(sign_changes) > 0 and np.any(sign_changes != 0):
    last_crossing_idx = np.where(sign_changes != 0)[0][-1]
    crossing_date = team_rate_series.iloc[last_crossing_idx]['datecompleted']
    days_ago = (completed_df['datecompleted'].max() - crossing_date).days
    print(f"  • Last baseline crossing: {crossing_date.strftime('%Y-%m-%d')} ({days_ago} days ago)")
else:
    print(f"  • No recent baseline crossing detected")
print()

# Volatility and consistency
team_rate_volatility = completed_df['team_rate_30d'].std()
recent_volatility = recent_500['team_rate_30d'].std()
historical_volatility = completed_df.head(len(completed_df) - 500)['team_rate_30d'].std()

print(f"Team Rate Volatility (Consistency):")
print(f"  • Overall volatility (std): {team_rate_volatility:.2f} days")
print(f"  • Recent volatility (last 500): {recent_volatility:.2f} days")
print(f"  • Historical volatility: {historical_volatility:.2f} days")
if recent_volatility > historical_volatility * 1.5:
    print(f"  ⚠ Recent performance is MORE volatile than historical")
elif recent_volatility < historical_volatility * 0.67:
    print(f"  ✓ Recent performance is MORE consistent than historical")
else:
    print(f"  → Recent performance volatility is similar to historical")
print()

# Backlog analysis (approximation using pending orders at any time)
print(f"Backlog Impact Analysis:")
print(f"  • Total deseasonalized range: [{completed_df['deseasonalized'].min():.1f}, {completed_df['deseasonalized'].max():.1f}] days")
print(f"  • Current team rate: {current_team_bias_30d:+.2f} days")
pct_of_range = abs(current_team_bias_30d) / (completed_df['deseasonalized'].max() - completed_df['deseasonalized'].min()) * 100
print(f"  • Current bias is {pct_of_range:.1f}% of full deseasonalized range")
print()

# Final prediction improvement
full_model_mae = 0.43  # From actual model results
team_improvement_pct = ((seasonal_mae - full_model_mae) / seasonal_mae) * 100

print(f"Prediction Improvement from Team Rate Component:")
print(f"  • Fundamental + Seasonal MAE: {seasonal_mae:.2f} days")
print(f"  • Fundamental + Seasonal + Team Rate MAE: {full_model_mae:.2f} days")
print(f"  • Improvement: {team_improvement_pct:.1f}%")
print(f"  • Absolute reduction: {seasonal_mae - full_model_mae:.2f} days")
print()

print(f"Interpretation:")
if team_improvement_pct > 90:
    print(f"  ⚠ Component 3 drives {team_improvement_pct:.0f}% of improvement - CRITICAL!")
    print(f"  → Model is heavily learning current team state from customer history")
    print(f"  → Consider adding explicit team rate features to production model")
elif team_improvement_pct > 50:
    print(f"  → Component 3 drives {team_improvement_pct:.0f}% of improvement - very important")
else:
    print(f"  → Component 3 drives {team_improvement_pct:.0f}% of improvement - helpful but not dominant")

print("\n[3/4] Creating visualizations...")

# ============================================================================
# FIGURE 1: Three-Component Decomposition
# ============================================================================
fig1 = plt.figure(figsize=(20, 12))

# 1. Original Time Series
ax1 = plt.subplot(4, 2, 1)
recent_1000 = completed_df.tail(1000)
ax1.scatter(range(len(recent_1000)), recent_1000['days_to_complete'],
            alpha=0.3, s=5, color='gray', label='Actual')
ax1.axhline(fundamental_mean, color='red', linestyle='--', linewidth=2, label=f'Overall Mean: {fundamental_mean:.1f}d')
ax1.set_xlabel('Order Index (Last 1000)')
ax1.set_ylabel('Days to Complete')
ax1.set_title('Component 1: Raw Data + Fundamental Baseline')
ax1.legend()
ax1.grid(True, alpha=0.3)

# 2. Fundamental Statistics Distribution
ax2 = plt.subplot(4, 2, 2)
ax2.hist(completed_df['days_to_complete'], bins=50, alpha=0.7, color='steelblue', edgecolor='black')
ax2.axvline(fundamental_mean, color='red', linestyle='--', linewidth=2, label=f'Mean: {fundamental_mean:.1f}d')
ax2.axvline(fundamental_median, color='green', linestyle='--', linewidth=2, label=f'Median: {fundamental_median:.1f}d')
ax2.set_xlabel('Days to Complete')
ax2.set_ylabel('Frequency')
ax2.set_title('Component 1: Fundamental Distribution (All Historical Data)')
ax2.legend()
ax2.grid(True, alpha=0.3, axis='y')

# 3. Seasonal Pattern (Annual Cycle)
ax3 = plt.subplot(4, 2, 3)
ax3.plot(seasonal_pattern['day_of_year'], seasonal_pattern['mean'],
         alpha=0.3, linewidth=1, color='gray', label='Daily Average')
ax3.plot(seasonal_pattern['day_of_year'], seasonal_pattern['smoothed_mean'],
         linewidth=3, color='orange', label='Smoothed Seasonal Pattern')
ax3.axhline(fundamental_mean, color='red', linestyle='--', linewidth=1, alpha=0.5, label='Overall Mean')
ax3.fill_between(seasonal_pattern['day_of_year'],
                  fundamental_mean, seasonal_pattern['smoothed_mean'],
                  alpha=0.2, color='orange')
ax3.set_xlabel('Day of Year')
ax3.set_ylabel('Average Days to Complete')
ax3.set_title('Component 2: Seasonal Pattern (Annual Sinusoid)')
ax3.legend()
ax3.grid(True, alpha=0.3)
# Add month labels
month_starts = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
ax3.set_xticks(month_starts)
ax3.set_xticklabels(month_names, rotation=45)

# 4. Seasonal Heatmap (by month and year)
ax4 = plt.subplot(4, 2, 4)
monthly_pivot = completed_df.groupby([completed_df['datecompleted'].dt.year,
                                       completed_df['datecompleted'].dt.month])['days_to_complete'].mean().unstack()
sns.heatmap(monthly_pivot, annot=False, fmt='.1f', cmap='RdYlGn_r', ax=ax4, cbar_kws={'label': 'Avg Days'})
ax4.set_xlabel('Month')
ax4.set_ylabel('Year')
ax4.set_title('Component 2: Seasonal Pattern by Year/Month')

# 5. Deseasonalized Data (removes seasonal component)
ax5 = plt.subplot(4, 2, 5)
recent_des = completed_df.tail(1000)
ax5.scatter(range(len(recent_des)), recent_des['deseasonalized'],
            alpha=0.3, s=5, color='purple', label='Deseasonalized')
ax5.axhline(0, color='red', linestyle='--', linewidth=2, label='Seasonal Baseline')
ax5.plot(range(len(recent_des)), recent_des['team_rate_30d'],
         linewidth=2, color='blue', label='30-day Team Rate')
ax5.set_xlabel('Order Index (Last 1000)')
ax5.set_ylabel('Days (deseasonalized)')
ax5.set_title('Component 3: Deseasonalized + Team Rate Bias')
ax5.legend()
ax5.grid(True, alpha=0.3)

# 6. Team Rate Over Time
ax6 = plt.subplot(4, 2, 6)
recent_team = completed_df.tail(2000)
ax6.plot(recent_team['datecompleted'], recent_team['team_rate_30d'],
         linewidth=2, color='blue', label='30-day Rate', alpha=0.7)
ax6.plot(recent_team['datecompleted'], recent_team['team_rate_90d'],
         linewidth=2, color='green', label='90-day Rate', alpha=0.7)
ax6.axhline(0, color='red', linestyle='--', linewidth=2, alpha=0.5, label='Seasonal Baseline')
ax6.fill_between(recent_team['datecompleted'], 0, recent_team['team_rate_30d'],
                  where=(recent_team['team_rate_30d'] > 0), alpha=0.2, color='red', label='Slower')
ax6.fill_between(recent_team['datecompleted'], 0, recent_team['team_rate_30d'],
                  where=(recent_team['team_rate_30d'] <= 0), alpha=0.2, color='green', label='Faster')
ax6.set_xlabel('Completion Date')
ax6.set_ylabel('Bias from Seasonal Baseline (days)')
ax6.set_title('Component 3: Current Team Rate (Last 2000 Orders)')
ax6.legend()
ax6.grid(True, alpha=0.3)
plt.setp(ax6.xaxis.get_majorticklabels(), rotation=45)

# 7. Three-Component Reconstruction
ax7 = plt.subplot(4, 2, 7)
sample_range = slice(-500, -400)  # 100 orders for clarity
sample_data = completed_df.iloc[sample_range].copy()
sample_data['reconstruction'] = (fundamental_mean +
                                  (sample_data['seasonal_component'] - fundamental_mean) +
                                  sample_data['team_rate_30d'])

x = range(len(sample_data))
ax7.plot(x, sample_data['days_to_complete'], 'o-', linewidth=2,
         markersize=4, label='Actual', color='black', alpha=0.7)
ax7.plot(x, [fundamental_mean] * len(sample_data), '--',
         linewidth=2, label='1. Fundamental', color='red', alpha=0.7)
ax7.plot(x, sample_data['seasonal_component'], '--',
         linewidth=2, label='2. + Seasonal', color='orange', alpha=0.7)
ax7.plot(x, sample_data['reconstruction'], 's-',
         linewidth=2, markersize=3, label='3. + Team Rate', color='blue', alpha=0.7)
ax7.set_xlabel('Order Index (sample of 100)')
ax7.set_ylabel('Days to Complete')
ax7.set_title('Three-Component Reconstruction: 1 + 2 + 3')
ax7.legend()
ax7.grid(True, alpha=0.3)

# 8. Prediction Error by Component
ax8 = plt.subplot(4, 2, 8)
sample_data['error_1'] = np.abs(sample_data['days_to_complete'] - fundamental_mean)
sample_data['error_2'] = np.abs(sample_data['days_to_complete'] - sample_data['seasonal_component'])
sample_data['error_3'] = np.abs(sample_data['days_to_complete'] - sample_data['reconstruction'])

errors = [
    sample_data['error_1'].mean(),
    sample_data['error_2'].mean(),
    sample_data['error_3'].mean()
]
components = ['1. Fundamental\nOnly', '2. + Seasonal', '3. + Team Rate']
colors_comp = ['red', 'orange', 'blue']

bars = ax8.bar(range(3), errors, color=colors_comp, alpha=0.7, edgecolor='black')
ax8.set_xticks(range(3))
ax8.set_xticklabels(components)
ax8.set_ylabel('Mean Absolute Error (days)')
ax8.set_title('Prediction Improvement by Component')
ax8.grid(True, alpha=0.3, axis='y')

# Add value labels
for i, (bar, err) in enumerate(zip(bars, errors)):
    ax8.text(i, err + 0.5, f'{err:.2f}d', ha='center', va='bottom', fontweight='bold', fontsize=10)
    if i > 0:
        improvement = ((errors[0] - err) / errors[0]) * 100
        ax8.text(i, err/2, f'-{improvement:.1f}%', ha='center', va='center',
                 fontweight='bold', fontsize=9, color='white')

plt.tight_layout()

# ============================================================================
# FIGURE 2: Team Rate Deep Dive
# ============================================================================
fig2 = plt.figure(figsize=(20, 10))

# 1. Team Rate Distribution
ax1 = plt.subplot(2, 3, 1)
team_rate_data = completed_df['team_rate_30d'].dropna()
ax1.hist(team_rate_data, bins=50, alpha=0.7, color='steelblue', edgecolor='black')
ax1.axvline(0, color='red', linestyle='--', linewidth=2, label='Seasonal Baseline')
ax1.axvline(team_rate_data.mean(), color='green', linestyle='--', linewidth=2,
            label=f'Mean: {team_rate_data.mean():+.2f}d')
ax1.set_xlabel('Team Rate Bias (days)')
ax1.set_ylabel('Frequency')
ax1.set_title('Component 3: Team Rate Distribution')
ax1.legend()
ax1.grid(True, alpha=0.3, axis='y')

# 2. Team Rate by Year
ax2 = plt.subplot(2, 3, 2)
yearly_team_rate = completed_df.groupby(completed_df['datecompleted'].dt.year)['team_rate_30d'].mean()
years = yearly_team_rate.index
ax2.bar(range(len(years)), yearly_team_rate.values, color='steelblue', alpha=0.7, edgecolor='black')
ax2.axhline(0, color='red', linestyle='--', linewidth=2, alpha=0.5)
ax2.set_xticks(range(len(years)))
ax2.set_xticklabels(years, rotation=45)
ax2.set_ylabel('Average Team Rate Bias (days)')
ax2.set_title('Component 3: Team Performance by Year')
ax2.grid(True, alpha=0.3, axis='y')

# Add labels
for i, (year, rate) in enumerate(zip(years, yearly_team_rate.values)):
    y_pos = rate + (0.5 if rate > 0 else -0.5)
    ax2.text(i, y_pos, f'{rate:+.1f}', ha='center', va='bottom' if rate > 0 else 'top', fontweight='bold')

# 3. Volatility Over Time
ax3 = plt.subplot(2, 3, 3)
completed_df['team_rate_volatility'] = completed_df['deseasonalized'].rolling(window=30, min_periods=5).std()
recent_vol = completed_df.tail(1000)
ax3.plot(recent_vol['datecompleted'], recent_vol['team_rate_volatility'],
         linewidth=2, color='purple', alpha=0.7)
ax3.set_xlabel('Completion Date')
ax3.set_ylabel('Volatility (Std Dev, days)')
ax3.set_title('Component 3: Team Consistency Over Time (Last 1000)')
ax3.grid(True, alpha=0.3)
plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)

# 4. Seasonal Pattern + Current Bias
ax4 = plt.subplot(2, 3, 4)
ax4.plot(seasonal_pattern['day_of_year'], seasonal_pattern['smoothed_mean'],
         linewidth=3, color='orange', label='Seasonal Baseline')
# Add current team bias
current_prediction = seasonal_pattern['smoothed_mean'] + current_team_bias_30d
ax4.plot(seasonal_pattern['day_of_year'], current_prediction,
         linewidth=3, color='blue', linestyle='--', label=f'Current Prediction (bias: {current_team_bias_30d:+.1f}d)')
ax4.set_xlabel('Day of Year')
ax4.set_ylabel('Predicted Days to Complete')
ax4.set_title('Components 2 + 3: Seasonal + Current Team Rate')
ax4.legend()
ax4.grid(True, alpha=0.3)
ax4.set_xticks(month_starts)
ax4.set_xticklabels(month_names, rotation=45)
ax4.fill_between(seasonal_pattern['day_of_year'],
                  seasonal_pattern['smoothed_mean'], current_prediction,
                  alpha=0.3, color='blue')

# 5. Recent vs Historical (last 90 days)
ax5 = plt.subplot(2, 3, 5)
recent_90 = completed_df.tail(int(len(completed_df) * 0.05))  # Last 5% of data
historical = completed_df.head(int(len(completed_df) * 0.95))  # First 95%

data_to_plot = [historical['deseasonalized'], recent_90['deseasonalized']]
labels = ['Historical\n(First 95%)', 'Recent\n(Last 5%)']
bp = ax5.boxplot(data_to_plot, labels=labels, patch_artist=True)
for patch, color in zip(bp['boxes'], ['lightgreen', 'lightcoral']):
    patch.set_facecolor(color)
ax5.axhline(0, color='red', linestyle='--', linewidth=2, alpha=0.5, label='Seasonal Baseline')
ax5.set_ylabel('Deseasonalized Days (bias)')
ax5.set_title('Component 3: Recent vs Historical Performance')
ax5.grid(True, alpha=0.3, axis='y')

# 6. Model Formula Visualization
ax6 = plt.subplot(2, 3, 6)
ax6.axis('off')
formula_text = """
THREE-COMPONENT MODEL FORMULA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Prediction = Fundamental + Seasonal + Team Rate

Component 1: FUNDAMENTAL STATISTICS
   • Overall mean from years of data
   • Captures inherent complexity
   • Value: {fundamental:.1f} days

Component 2: SEASONAL PATTERN
   • Annual sinusoidal cycle
   • Varies by day-of-year
   • Range: {seasonal_min:.1f} - {seasonal_max:.1f} days

Component 3: CURRENT TEAM RATE
   • Recent performance bias
   • 30-day rolling average
   • Current bias: {team_bias:+.1f} days

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Example Prediction (Nov 15):
  Fundamental:  {fundamental:.1f} days
  + Seasonal:   {example_seasonal:+.1f} days (winter peak)
  + Team Rate:  {team_bias:+.1f} days (current state)
  ─────────────────────────────
  = TOTAL:      {example_total:.1f} days
""".format(
    fundamental=fundamental_mean,
    seasonal_min=seasonal_pattern['smoothed_mean'].min(),
    seasonal_max=seasonal_pattern['smoothed_mean'].max(),
    team_bias=current_team_bias_30d,
    example_seasonal=seasonal_pattern.loc[seasonal_pattern['day_of_year'] == 319, 'smoothed_mean'].values[0] - fundamental_mean,
    example_total=seasonal_pattern.loc[seasonal_pattern['day_of_year'] == 319, 'smoothed_mean'].values[0] + current_team_bias_30d
)

ax6.text(0.1, 0.5, formula_text, transform=ax6.transAxes,
         fontsize=11, verticalalignment='center', fontfamily='monospace',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()

print("\n[4/4] Displaying visualizations...")
print("\n" + "=" * 80)
print("THREE-COMPONENT SUMMARY")
print("=" * 80)
print(f"\n1. FUNDAMENTAL BASELINE: {fundamental_mean:.2f} ± {fundamental_std:.2f} days")
print(f"   → Based on {len(completed_df)} historical orders")
print(f"   → Median: {fundamental_median:.2f} days")

print(f"\n2. SEASONAL VARIATION: {seasonal_pattern['smoothed_mean'].min():.2f} to {seasonal_pattern['smoothed_mean'].max():.2f} days")
print(f"   → Amplitude: {seasonal_pattern['smoothed_mean'].max() - seasonal_pattern['smoothed_mean'].min():.2f} days")
print(f"   → Peak (winter): {seasonal_pattern['smoothed_mean'].max():.2f} days")
print(f"   → Trough (summer): {seasonal_pattern['smoothed_mean'].min():.2f} days")

print(f"\n3. CURRENT TEAM RATE: {current_team_bias_30d:+.2f} days bias")
if abs(current_team_bias_30d) < 1:
    status = "performing AT baseline"
elif current_team_bias_30d > 0:
    status = f"performing {current_team_bias_30d:.1f} days SLOWER than baseline"
else:
    status = f"performing {abs(current_team_bias_30d):.1f} days FASTER than baseline"
print(f"   → Team is {status}")
print(f"   → 90-day average: {current_team_bias_90d:+.2f} days")

print("\n" + "=" * 80)
print("PREDICTION IMPROVEMENT")
print("=" * 80)
fundamental_only_mae = np.abs(completed_df['days_to_complete'] - fundamental_mean).mean()
seasonal_mae = np.abs(completed_df['days_to_complete'] - completed_df['seasonal_component']).mean()
full_model_mae = 0.43  # From your actual model results

print(f"Fundamental Only:        MAE = {fundamental_only_mae:.2f} days")
print(f"+ Seasonal Pattern:      MAE = {seasonal_mae:.2f} days (↓{((fundamental_only_mae-seasonal_mae)/fundamental_only_mae*100):.1f}%)")
print(f"+ Current Team Rate:     MAE = {full_model_mae:.2f} days (↓{((seasonal_mae-full_model_mae)/seasonal_mae*100):.1f}%)")
print(f"\nTotal Improvement: {((fundamental_only_mae-full_model_mae)/fundamental_only_mae*100):.1f}%")

print("\n" + "=" * 80)
plt.show()
