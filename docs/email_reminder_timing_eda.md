# Email Reminder Timing - Exploratory Data Analysis

## Executive Summary
This document analyzes historical work order data to determine the optimal timing for sending cleaning reminder emails to customers.

## Analysis Goals
1. Determine average time between cleanings for customers
2. Identify patterns by customer segment
3. Find optimal reminder timing to maximize conversion
4. Recommend when to send reminder emails

## Data Sources
- **Work Orders**: Historical cleaning records with completion dates
- **Customers**: Customer information and segmentation
- **Geographic Data**: Location-based patterns

## Key Metrics
- **Average Time Between Cleanings**: Days between consecutive work orders for the same customer
- **Repeat Rate**: Percentage of customers who return for additional services
- **Seasonal Patterns**: Time of year impact on cleaning frequency
- **Response Window**: Optimal time before expected next cleaning

## Analysis

### 1. Customer Cleaning Frequency Distribution

**Query to analyze:**
```sql
WITH customer_orders AS (
    SELECT
        custid,
        date_completed,
        LAG(date_completed) OVER (PARTITION BY custid ORDER BY date_completed) as prev_completed
    FROM tblworkorders
    WHERE date_completed IS NOT NULL
),
time_between AS (
    SELECT
        custid,
        date_completed - prev_completed as days_between
    FROM customer_orders
    WHERE prev_completed IS NOT NULL
)
SELECT
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY days_between) as q1_days,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_between) as median_days,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY days_between) as q3_days,
    AVG(days_between) as avg_days,
    STDDEV(days_between) as stddev_days,
    COUNT(*) as total_repeat_orders
FROM time_between;
```

**Expected Insights:**
- Median time between cleanings
- Distribution spread (Q1, Q3)
- Identify if there are distinct customer segments

### 2. Customer Segmentation by Cleaning Frequency

```sql
WITH customer_frequency AS (
    SELECT
        custid,
        COUNT(*) as order_count,
        MAX(date_completed) - MIN(date_completed) as total_span_days,
        AVG(
            date_completed - LAG(date_completed)
            OVER (PARTITION BY custid ORDER BY date_completed)
        ) as avg_days_between
    FROM tblworkorders
    WHERE date_completed IS NOT NULL
    GROUP BY custid
    HAVING COUNT(*) >= 2
)
SELECT
    CASE
        WHEN avg_days_between < 180 THEN 'High Frequency (<6mo)'
        WHEN avg_days_between BETWEEN 180 AND 270 THEN 'Semi-Annual (6-9mo)'
        WHEN avg_days_between BETWEEN 270 AND 450 THEN 'Annual (9-15mo)'
        ELSE 'Low Frequency (>15mo)'
    END as segment,
    COUNT(*) as customer_count,
    AVG(avg_days_between) as avg_days,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY avg_days_between) as median_days
FROM customer_frequency
GROUP BY segment
ORDER BY avg_days;
```

**Use Cases:**
- **High Frequency**: Send reminders at 5 months
- **Semi-Annual**: Send reminders at 8 months
- **Annual**: Send reminders at 11 months
- **Low Frequency**: Send reminders at 15 months

### 3. Seasonal Patterns

```sql
SELECT
    EXTRACT(MONTH FROM date_completed) as month,
    EXTRACT(QUARTER FROM date_completed) as quarter,
    COUNT(*) as orders_completed,
    COUNT(DISTINCT custid) as unique_customers
FROM tblworkorders
WHERE date_completed IS NOT NULL
GROUP BY month, quarter
ORDER BY month;
```

**Insights:**
- Identify peak cleaning seasons
- Adjust reminder timing based on historical busy periods
- Plan capacity for expected response volume

### 4. Repeat Customer Analysis

```sql
WITH customer_stats AS (
    SELECT
        custid,
        COUNT(*) as lifetime_orders,
        MAX(date_completed) as last_order_date,
        MIN(date_completed) as first_order_date,
        CURRENT_DATE - MAX(date_completed) as days_since_last
    FROM tblworkorders
    WHERE date_completed IS NOT NULL
    GROUP BY custid
)
SELECT
    CASE
        WHEN lifetime_orders = 1 THEN 'One-time'
        WHEN lifetime_orders = 2 THEN 'Returning'
        WHEN lifetime_orders BETWEEN 3 AND 5 THEN 'Regular'
        ELSE 'Loyal'
    END as customer_tier,
    COUNT(*) as customer_count,
    AVG(days_since_last) as avg_days_since_last,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_since_last) as median_days_since
FROM customer_stats
GROUP BY customer_tier
ORDER BY
    CASE customer_tier
        WHEN 'One-time' THEN 1
        WHEN 'Returning' THEN 2
        WHEN 'Regular' THEN 3
        WHEN 'Loyal' THEN 4
    END;
```

### 5. Geographic Patterns

```sql
SELECT
    COALESCE(city, 'Unknown') as city,
    COUNT(DISTINCT wo.custid) as customer_count,
    COUNT(wo.workorderno) as total_orders,
    AVG(
        wo.date_completed - LAG(wo.date_completed)
        OVER (PARTITION BY wo.custid ORDER BY wo.date_completed)
    ) as avg_days_between
FROM tblworkorders wo
JOIN tblcustomers c ON wo.custid = c.custid
WHERE wo.date_completed IS NOT NULL
GROUP BY city
HAVING COUNT(DISTINCT wo.custid) >= 5
ORDER BY customer_count DESC
LIMIT 20;
```

## Recommended Email Reminder Strategy

### Timing Recommendations

Based on industry standards and typical awning cleaning cycles:

#### Strategy 1: Fixed Timing (Simple)
- **When to Send**: 11 months after last cleaning
- **Pros**: Easy to implement, consistent messaging
- **Cons**: Doesn't account for customer-specific patterns

#### Strategy 2: Personalized Timing (Recommended)
```python
def calculate_reminder_date(customer):
    # Get customer's average cleaning interval
    avg_interval = get_customer_avg_interval(customer)

    # Send reminder at 90% of their interval
    reminder_offset = avg_interval * 0.90

    # Default to 11 months if no history
    if not avg_interval:
        reminder_offset = 335  # ~11 months

    return last_cleaning_date + timedelta(days=reminder_offset)
```

#### Strategy 3: Seasonal Adjustment
- Adjust timing based on peak seasons
- Send earlier if approaching busy season
- Account for weather patterns (spring/fall cleaning peaks)

### Email Cadence

1. **First Reminder**: At calculated timing (e.g., 11 months)
2. **Second Reminder**: 2 weeks after first (if no response)
3. **Final Reminder**: 4 weeks after first (if no response)

**Suppression Rules:**
- Don't send if customer has scheduled service
- Don't send if reminder sent in last 60 days
- Don't send if customer opted out

### Success Metrics to Track

1. **Open Rate**: % of reminders opened
2. **Click Rate**: % who click call-to-action
3. **Conversion Rate**: % who schedule service
4. **Time to Response**: Days between email and scheduling
5. **Opt-out Rate**: % who unsubscribe

## Implementation in Code

The current implementation (in `routes/email_reminders.py`) uses:
- **Fixed Window**: 335-365 days since last cleaning
- **Suppression**: No reminders if sent in last 60 days

### Recommended Improvements

1. **Add Customer Segmentation**:
```python
def get_customer_segment(customer):
    avg_interval = calculate_avg_interval(customer)
    if avg_interval < 180:
        return 'high_frequency', 150  # 5 months
    elif avg_interval < 270:
        return 'semi_annual', 240  # 8 months
    elif avg_interval < 450:
        return 'annual', 335  # 11 months
    else:
        return 'low_frequency', 450  # 15 months
```

2. **Track Email Metrics**:
   - Add fields to `EmailReminder` model:
     - `opened_at`: When email was opened
     - `clicked_at`: When CTA was clicked
     - `converted_at`: When service was scheduled
     - `conversion_work_order`: Link to resulting work order

3. **A/B Testing**:
   - Test different reminder timings
   - Test different email content
   - Measure which performs better

## Data Collection for Ongoing Optimization

### Metrics to Collect

1. **Email Performance**:
   - Sent count
   - Open rate
   - Click-through rate
   - Unsubscribe rate

2. **Business Metrics**:
   - Conversion to scheduled service
   - Revenue attributed to reminders
   - Customer lifetime value impact

3. **Timing Analysis**:
   - Response time distribution
   - Optimal day of week to send
   - Optimal time of day to send

### Recommended Dashboard

Create an analytics view showing:
- Reminders sent this month
- Conversion rate trend
- Revenue attributed to reminders
- Optimal timing insights

## Next Steps

1. **Run Initial Analysis**: Execute SQL queries above on production data
2. **Validate Assumptions**: Check if 11-month default is optimal
3. **Implement Segmentation**: Add customer-specific timing logic
4. **Track Metrics**: Begin collecting email performance data
5. **Iterate**: Adjust timing based on real-world results

## Tools & Resources

- **Analysis**: Run queries in PostgreSQL directly or via Jupyter notebook
- **Visualization**: Use Plotly (already in stack) for charts
- **Monitoring**: Add to Analytics dashboard
- **Testing**: Use existing pytest framework for validation

## Conclusion

The current 11-month reminder timing is a reasonable starting point based on industry standards for annual awning cleaning. However, personalized timing based on each customer's historical patterns will likely improve conversion rates significantly.

Start with the fixed timing, collect data, then iterate toward personalized, segment-based timing as patterns emerge.