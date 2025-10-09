
# Analytics Dashboard Improvement Plan

This document outlines a roadmap for enhancing the analytics dashboard. The goal is to provide deeper insights into the business performance, moving beyond the current order-centric view.

## EDA Findings

Based on an analysis of the database, here are some key findings that should inform the analytics improvements:

*   **Revenue Calculation**: The `quote` column in the `tblcustworkorderdetail` table is not a reliable source for revenue figures, as it often contains non-numeric values like "Approved". The `price` column in the `tblorddetcustawngs` table, which represents the price of individual order items, is a much more accurate source for revenue calculation. The existing "Total Revenue" KPI should be updated to sum the `price` of all items in completed work orders.
*   **Product Types**: The `sizewgt` column in `tblorddetcustawngs` contains complex strings that describe the size and weight of order items. The existing logic to differentiate between "awnings" and "sails" (based on the presence of a "#" symbol) appears to be correct. This provides a good foundation for product-level analysis.
*   **Rush Orders**: The `rushorder` and `firmrush` boolean columns in `tblcustworkorderdetail` are well-populated and can be used to analyze the frequency and impact of rush orders.

## Review of Square Footage Parsing Code

The `clean_square_footage` and `clean_sail_weight` functions, along with their usage in `load_work_orders`, have been reviewed for accuracy and robustness.

**Findings:**

*   **`clean_square_footage`**: This function is highly robust and accurate. It effectively handles a wide variety of complex input formats for awning sizes, including dimensions with feet and inches (e.g., `8'9"x10'2"`), simple `XxY` dimensions, and values with an `=` sign indicating a pre-calculated area. It also correctly strips currency and unit markers. Error handling for malformed strings is graceful, returning `0.0`.
*   **`clean_sail_weight`**: This function accurately parses sail weights in the format `95#`. It correctly extracts the numeric value and handles potential conversion errors.
*   **`load_work_orders` Integration**: The logic within `load_work_orders` to determine `product_type` (Awning vs. Sail based on `#` in `sizewgt`) and then apply the appropriate cleaning function (`clean_square_footage` or `clean_sail_weight`) is correct and efficient.

**Conclusion:**

The existing square footage parsing code is **accurate, robust, and well-implemented** for the identified data patterns. No major improvements are immediately necessary for its core functionality. The current implementation is well-suited for the task of calculating square footage from diverse input strings.

## Review of Cleaning Throughput Calculation Code

The code responsible for calculating cleaning throughput, primarily within `load_work_orders` and `get_daily_throughput`, has been reviewed for correctness.

**Findings:**

*   **`load_work_orders`**: This function accurately calculates the `sqft` for individual items by multiplying `qty_numeric` with the results from `clean_sail_weight` or `clean_square_footage` (which were previously reviewed and found to be robust). It then correctly aggregates these `sqft` values to derive `totalsize` for each work order.
*   **`get_daily_throughput`**: This function correctly filters for completed work orders using `datecompleted`. It then accurately groups these completed orders by their completion date and sums their `totalsize` to determine the `daily_sqft`. The rolling average calculation is also correctly implemented, providing a smoothed trend of throughput.

**Conclusion:**

The cleaning throughput calculation code is **correct and accurate**. It effectively processes raw data into meaningful daily and rolling average metrics. The recent change to remove the `.tail(90)` limit will ensure that the dashboard now displays the full historical data for daily cleaning throughput, providing a comprehensive view over time.

## Outlier Analysis in Daily Throughput

An initial outlier detection using the IQR method on daily throughput data revealed several dates with extremely high square footage values. These outliers are highly suggestive of data entry errors rather than legitimate production spikes. For example, some single work orders are recorded with millions of square feet, which is physically improbable.

**Examples of extreme outliers:**
*   `2011-04-27`: 1.679114e+07 sq ft
*   `2010-08-12`: 7.204018e+06 sq ft
*   `2011-02-18`: 6.003085e+06 sq ft

**Recommendations for Outlier Handling:**
1.  **Data Validation**: Investigate the raw `sizewgt` entries for the work orders contributing to these extreme outliers. This will help confirm if they are indeed data entry errors.
2.  **Data Cleaning Strategy**: Implement a strategy to handle such outliers. This could involve:
    *   **Correction**: If possible, correct the erroneous entries in the source data.
    *   **Exclusion**: Exclude extreme outliers from calculations, perhaps by setting a reasonable upper bound for `totalsize` per work order or per day.
    *   **Transformation**: Apply data transformation techniques (e.g., winsorization) to cap extreme values.
3.  **Robustness of Parsing**: While `clean_square_footage` is robust, review if specific malformed patterns in `sizewgt` are consistently leading to these extreme values, and if so, enhance the parsing logic to better handle or flag them.

## 1. Customer-Centric KPIs

The current dashboard focuses heavily on work orders. To better understand customer behavior and value, we should add the following KPIs:

*   **New vs. Returning Customers**: Track the number of new customers acquired over time versus the number of returning customers. This will help measure customer loyalty and business growth.
*   **Customer Lifetime Value (CLV)**: Calculate the total revenue generated per customer. This will help identify high-value customers.
*   **Top Customers**: A list of top customers by revenue or number of orders.

**Implementation Steps:**

1.  Modify the `load_work_orders` function to also return customer data.
2.  Create a new function `calculate_customer_kpis` to compute the new metrics.
3.  Add new KPI cards to the `dashboard.html` template.
4.  Add a new chart to visualize new vs. returning customers over time.

## 2. Product/Service Analysis

The current `sizewgt` column processing differentiates between "awnings" and "sails". We can leverage this to provide a more granular analysis of the business.

*   **Revenue by Product Type**: Break down total revenue by "awning" and "sail".
*   **Throughput by Product Type**: Analyze the square footage cleaned for each product type.
*   **Order Volume by Product Type**: Show the number of orders for each product type.

**Implementation Steps:**

1.  Modify the `load_work_orders` function to categorize each order item as "awning" or "sail".
2.  Update the KPI calculation functions to aggregate by product type.
3.  Add new charts or update existing ones to show the product type breakdown. A stacked bar chart for monthly trends could work well.

## 3. Rush Order Analysis

The `rushorder` and `firmrush` columns indicate the urgency of an order. We should analyze the impact of these orders.

*   **Rush Order Frequency**: What percentage of orders are rush orders?
*   **Rush Order Revenue**: Do rush orders generate more revenue on average?
*   **Impact on Lead Time**: Do rush orders get completed faster?

**Implementation Steps:**

1.  Incorporate the `rushorder` and `firmrush` columns into the `load_work_orders` function.
2.  Calculate KPIs related to rush orders.
3.  Add a section to the dashboard to display these insights.

## 4. Lead Time Analysis

Understanding how long it takes to complete an order is a crucial operational metric.

*   **Average Lead Time**: Calculate the average time between `datein` and `datecompleted`.
*   **Lead Time Distribution**: Show a histogram of lead times to identify outliers.
*   **Lead Time by Product Type**: Analyze if certain products take longer to complete.

**Implementation Steps:**

1.  Calculate the lead time for each completed order in the `load_work_orders` function.
2.  Create a new function to calculate lead time metrics.
3.  Add a new chart to the dashboard to visualize the lead time distribution.

## 5. Interactive Filtering

To make the dashboard more useful, we should add interactive filtering capabilities.

*   **Date Range Filter**: Allow users to select a date range to view analytics for a specific period.
*   **Product Type Filter**: Allow users to filter the data for "awnings" or "sails".
*   **Customer Filter**: Allow users to search for a specific customer and see their history.

**Implementation Steps:**

1.  Add filter controls to the `dashboard.html` template.
2.  Modify the `/api/data` endpoint to accept filter parameters.
3.  Update the backend functions to apply the filters to the data.
