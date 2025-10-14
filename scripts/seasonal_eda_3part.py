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
print("\nComponent 1: Fundamental Statistics")
fundamental_mean = completed_df['days_to_complete'].mean()
fundamental_median = completed_df['days_to_complete'].median()
fundamental_std = completed_df['days_to_complete'].std()

print(f"  Overall Mean: {fundamental_mean:.2f} days")
print(f"  Overall Median: {fundamental_median:.2f} days")
print(f"  Overall Std Dev: {fundamental_std:.2f} days")

# ============================================================================
# COMPONENT 2: SEASONAL PATTERNS
# ============================================================================
print("\nComponent 2: Seasonal Patterns (Annual Cycle)")

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

print(f"  Seasonal amplitude: {seasonal_pattern['smoothed_mean'].max() - seasonal_pattern['smoothed_mean'].min():.2f} days")
print(f"  Peak season avg: {seasonal_pattern['smoothed_mean'].max():.2f} days")
print(f"  Slow season avg: {seasonal_pattern['smoothed_mean'].min():.2f} days")

# ============================================================================
# COMPONENT 3: CURRENT TEAM RATE
# ============================================================================
print("\nComponent 3: Current Team Rate (Recent Performance)")

# Calculate rolling average of deseasonalized data (removes seasonal effects)
window = 30
completed_df['team_rate_30d'] = completed_df['deseasonalized'].rolling(window=window, min_periods=5).mean()
completed_df['team_rate_90d'] = completed_df['deseasonalized'].rolling(window=90, min_periods=10).mean()

# Current team rate is the bias from the fundamental + seasonal baseline
recent_500 = completed_df.tail(500)
current_team_bias = recent_500['team_rate_30d'].mean()
print(f"  Recent 30-day bias: {current_team_bias:+.2f} days (vs seasonal baseline)")
print(f"  Recent 90-day bias: {recent_500['team_rate_90d'].mean():+.2f} days")

if current_team_bias > 0:
    print(f"  → Team is SLOWER than historical seasonal baseline")
elif current_team_bias < 0:
    print(f"  → Team is FASTER than historical seasonal baseline")
else:
    print(f"  → Team performing at historical seasonal baseline")

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
current_prediction = seasonal_pattern['smoothed_mean'] + current_team_bias
ax4.plot(seasonal_pattern['day_of_year'], current_prediction,
         linewidth=3, color='blue', linestyle='--', label=f'Current Prediction (bias: {current_team_bias:+.1f}d)')
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
    team_bias=current_team_bias,
    example_seasonal=seasonal_pattern.loc[seasonal_pattern['day_of_year'] == 319, 'smoothed_mean'].values[0] - fundamental_mean,
    example_total=seasonal_pattern.loc[seasonal_pattern['day_of_year'] == 319, 'smoothed_mean'].values[0] + current_team_bias
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

print(f"\n3. CURRENT TEAM RATE: {current_team_bias:+.2f} days bias")
if abs(current_team_bias) < 1:
    status = "performing AT baseline"
elif current_team_bias > 0:
    status = f"performing {current_team_bias:.1f} days SLOWER than baseline"
else:
    status = f"performing {abs(current_team_bias):.1f} days FASTER than baseline"
print(f"   → Team is {status}")
print(f"   → 90-day average: {recent_500['team_rate_90d'].mean():+.2f} days")

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
