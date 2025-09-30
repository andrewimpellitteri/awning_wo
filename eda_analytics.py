"""
EDA script for analytics dashboard
Run this to understand data structure before building dashboard
"""
import pandas as pd
from extensions import db
from app import create_app
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("=" * 80)
    print("EXPLORATORY DATA ANALYSIS - ANALYTICS DASHBOARD")
    print("=" * 80)

    # 1. Work Orders Detail
    print("\n1. WORK ORDERS DETAIL (tblcustworkorderdetail)")
    print("-" * 80)
    query = text("SELECT * FROM tblcustworkorderdetail LIMIT 10")
    df_wo = pd.read_sql(query, db.engine)
    print(f"Total rows: {len(pd.read_sql(text('SELECT * FROM tblcustworkorderdetail'), db.engine))}")
    print(f"Columns: {list(df_wo.columns)}")
    print(f"\nSample data:")
    print(df_wo.head(3))
    print(f"\nData types:")
    print(df_wo.dtypes)
    print(f"\nNull counts:")
    print(df_wo.isnull().sum())

    # 2. Order Items (Awnings)
    print("\n\n2. ORDER ITEMS - AWNINGS (tblorddetcustawngs)")
    print("-" * 80)
    query = text("SELECT * FROM tblorddetcustawngs LIMIT 10")
    df_items = pd.read_sql(query, db.engine)
    print(f"Total rows: {len(pd.read_sql(text('SELECT * FROM tblorddetcustawngs'), db.engine))}")
    print(f"Columns: {list(df_items.columns)}")
    print(f"\nSample data:")
    print(df_items.head(3))

    # 3. Date analysis
    print("\n\n3. DATE ANALYSIS")
    print("-" * 80)
    query = text("""
        SELECT
            MIN(datein) as earliest_datein,
            MAX(datein) as latest_datein,
            MIN(datecompleted) as earliest_completed,
            MAX(datecompleted) as latest_completed,
            COUNT(*) as total_orders,
            COUNT(datecompleted) as completed_orders,
            COUNT(CASE WHEN datecompleted IS NULL THEN 1 END) as pending_orders
        FROM tblcustworkorderdetail
    """)
    date_stats = pd.read_sql(query, db.engine)
    print(date_stats.T)

    # 4. Revenue analysis
    print("\n\n4. REVENUE ANALYSIS")
    print("-" * 80)
    query = text("""
        SELECT
            COUNT(*) as total_orders,
            SUM(CAST(REPLACE(REPLACE(quote, '$', ''), ',', '') AS NUMERIC)) as total_revenue,
            AVG(CAST(REPLACE(REPLACE(quote, '$', ''), ',', '') AS NUMERIC)) as avg_revenue,
            MIN(CAST(REPLACE(REPLACE(quote, '$', ''), ',', '') AS NUMERIC)) as min_revenue,
            MAX(CAST(REPLACE(REPLACE(quote, '$', ''), ',', '') AS NUMERIC)) as max_revenue
        FROM tblcustworkorderdetail
        WHERE quote IS NOT NULL AND quote != ''
    """)
    revenue_stats = pd.read_sql(query, db.engine)
    print(revenue_stats.T)

    # 5. Customer analysis
    print("\n\n5. CUSTOMER ANALYSIS")
    print("-" * 80)
    query = text("""
        SELECT
            COUNT(DISTINCT custid) as unique_customers,
            COUNT(*) as total_orders,
            CAST(COUNT(*) AS FLOAT) / COUNT(DISTINCT custid) as avg_orders_per_customer
        FROM tblcustworkorderdetail
    """)
    customer_stats = pd.read_sql(query, db.engine)
    print(customer_stats.T)

    # 6. Monthly trends
    print("\n\n6. MONTHLY ORDER TRENDS (Last 12 months)")
    print("-" * 80)
    query = text("""
        SELECT
            DATE_TRUNC('month', datein) as month,
            COUNT(*) as order_count,
            COUNT(datecompleted) as completed_count
        FROM tblcustworkorderdetail
        WHERE datein >= NOW() - INTERVAL '12 months'
        GROUP BY DATE_TRUNC('month', datein)
        ORDER BY month DESC
    """)
    monthly_trends = pd.read_sql(query, db.engine)
    print(monthly_trends)

    # 7. Throughput analysis
    print("\n\n7. DAILY THROUGHPUT ANALYSIS (Last 30 days)")
    print("-" * 80)
    query = text("""
        SELECT
            DATE(datecompleted) as completion_date,
            COUNT(*) as orders_completed
        FROM tblcustworkorderdetail
        WHERE datecompleted IS NOT NULL
        AND datecompleted >= NOW() - INTERVAL '30 days'
        GROUP BY DATE(datecompleted)
        ORDER BY completion_date DESC
    """)
    throughput = pd.read_sql(query, db.engine)
    print(throughput)

    # 8. Size/Weight analysis from items
    print("\n\n8. SIZE/WEIGHT DISTRIBUTION")
    print("-" * 80)
    query = text("""
        SELECT
            sizewgt,
            COUNT(*) as count
        FROM tblorddetcustawngs
        WHERE sizewgt IS NOT NULL
        GROUP BY sizewgt
        ORDER BY count DESC
        LIMIT 20
    """)
    size_dist = pd.read_sql(query, db.engine)
    print(size_dist)

    print("\n" + "=" * 80)
    print("EDA COMPLETE")
    print("=" * 80)
