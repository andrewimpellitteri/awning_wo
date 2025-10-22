from flask import Blueprint, render_template, jsonify
from flask_login import login_required
import pandas as pd
from extensions import db, cache
from datetime import datetime, timedelta
from sqlalchemy import text
from decorators import role_required
import numpy as np
from scipy import stats
from scipy.stats import percentileofscore

# Import data processing utilities
from utils.data_processing import (
    clean_numeric_string,
    clean_square_footage,
    parse_work_order_items,
)

analytics_bp = Blueprint("analytics", __name__)


# -----------------------------
# Data Loading
# -----------------------------


def load_work_orders(db_engine):
    """Load and process all work order data."""
    try:
        print("[DEBUG] Loading work orders...")

        # Load work order details
        query = """
        SELECT
            workorderno,
            custid,
            datein,
            datecompleted,
            quote,
            rushorder,
            firmrush
        FROM tblcustworkorderdetail
        """
        df = pd.read_sql(query, db_engine)

        # Parse dates
        df["datein"] = pd.to_datetime(df["datein"], errors="coerce")
        df["datecompleted"] = pd.to_datetime(df["datecompleted"], errors="coerce")

        valid_start = pd.to_datetime("2001-01-01")
        valid_end = pd.to_datetime("2025-12-31")

        # For datein: Keep NaT or valid range
        df = df[
            (df["datein"].isna())
            | ((df["datein"] >= valid_start) & (df["datein"] <= valid_end))
        ]

        # For datecompleted: Keep NaT or valid range
        df = df[
            (df["datecompleted"].isna())
            | (
                (df["datecompleted"] >= valid_start)
                & (df["datecompleted"] <= valid_end)
            )
        ]

        # NEW DEBUG: Post-filter stats
        print(
            "[DEBUG] Post-filter datein min/max/NaT count:",
            df["datein"].min(),
            df["datein"].max(),
            df["datein"].isna().sum(),
        )
        print(
            "[DEBUG] Post-filter datecompleted min/max/NaT count:",
            df["datecompleted"].min(),
            df["datecompleted"].max(),
            df["datecompleted"].isna().sum(),
        )
        print("[DEBUG] Rows after date filter:", len(df))
        # Optional: Log removed bad years for audit

        # pre_filter_rows = len(df) + (df['datecompleted'].isna().sum() + df['datein'].isna().sum())  # Rough, but adjust if needed

        # print(f"[DEBUG] Approx rows removed by filter: {original_rows - len(df)}")  # Set original_rows = len(df) before filter

        # Load order items
        items_query = (
            "SELECT workorderno, custid, qty, sizewgt, price FROM tblorddetcustawngs"
        )
        items = pd.read_sql(items_query, db_engine)

        # Parse items using new utility function (excludes sails from sqft calculation)
        items = parse_work_order_items(items)

        # Aggregate by work order
        totals = (
            items.groupby("workorderno")
            .agg({"sqft": "sum", "price_numeric": "sum"})
            .reset_index()
        )
        totals.columns = ["workorderno", "totalsize", "totalprice"]

        # Merge with work orders
        df = df.merge(totals, on="workorderno", how="left")
        df["totalsize"] = df["totalsize"].fillna(0)
        df["totalprice"] = df["totalprice"].fillna(0)

        # Merge product type information
        product_types = items[["workorderno", "product_type"]].drop_duplicates()
        df = df.merge(product_types, on="workorderno", how="left")

        print(f"[DEBUG] Loaded {len(df)} work orders")
        return df

    except Exception as e:
        print(f"[ERROR] Error loading work orders: {e}")
        import traceback

        traceback.print_exc()
        return pd.DataFrame()


# -----------------------------
# Analytics Calculations
# -----------------------------


def calculate_kpis(df):
    """Calculate key performance indicators."""
    if df.empty:
        return {
            "total_orders": 0,
            "completed_orders": 0,
            "open_orders": 0,
            "completion_rate": 0,
            "total_revenue": 0,
            "avg_revenue": 0,
            "total_sqft_completed": 0,
            "avg_throughput_7d": 0,
            "unique_customers": 0,
        }

    total_orders = len(df)
    completed_orders = df["datecompleted"].notna().sum()
    open_orders = total_orders - completed_orders
    completion_rate = (
        round((completed_orders / total_orders * 100), 1) if total_orders > 0 else 0
    )

    total_revenue = df["totalprice"].sum()
    avg_revenue = df["totalprice"].mean() if total_orders > 0 else 0

    unique_customers = df["custid"].nunique()

    # Throughput calculations
    completed_df = df[df["datecompleted"].notna()].copy()
    total_sqft_completed = completed_df["totalsize"].sum()

    # Last 7 days throughput
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_completed = completed_df[completed_df["datecompleted"] >= seven_days_ago]
    avg_throughput_7d = (
        recent_completed["totalsize"].sum() / 7 if len(recent_completed) > 0 else 0
    )

    return {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "open_orders": open_orders,
        "completion_rate": completion_rate,
        "total_revenue": total_revenue,
        "avg_revenue": avg_revenue,
        "total_sqft_completed": total_sqft_completed,
        "avg_throughput_7d": round(avg_throughput_7d, 1),
        "unique_customers": unique_customers,
    }


def get_monthly_trends(df):
    """Get monthly order trends."""
    if df.empty or "datein" not in df.columns:
        return pd.DataFrame(
            columns=["month", "order_count", "completed_count", "total_sqft"]
        )

    df_clean = df[df["datein"].notna()].copy()
    df_clean["month"] = df_clean["datein"].dt.to_period("M")

    monthly = (
        df_clean.groupby("month")
        .agg(
            {
                "workorderno": "count",
                "datecompleted": lambda x: x.notna().sum(),
                "totalsize": "sum",
            }
        )
        .reset_index()
    )

    monthly.columns = ["month", "order_count", "completed_count", "total_sqft"]
    monthly["month"] = monthly["month"].astype(str)

    return monthly.tail(48)  # Last 12 months


def get_daily_throughput(df, window=7):
    """Calculate daily throughput with rolling average, excluding outliers."""
    if df.empty:
        return pd.DataFrame(columns=["date", "daily_sqft", "rolling_avg"])

    completed = df[df["datecompleted"].notna()].copy()
    if completed.empty:
        return pd.DataFrame(columns=["date", "daily_sqft", "rolling_avg"])

    # Aggregate total sq ft cleaned per day
    daily = (
        completed.groupby(completed["datecompleted"].dt.date)
        .agg({"totalsize": "sum"})
        .reset_index()
    )
    daily.columns = ["date", "daily_sqft"]

    # --- Outlier removal using IQR ---
    Q1 = daily["daily_sqft"].quantile(0.25)
    Q3 = daily["daily_sqft"].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR

    before_count = len(daily)
    daily = daily[
        (daily["daily_sqft"] >= lower_bound) & (daily["daily_sqft"] <= upper_bound)
    ]
    after_count = len(daily)

    print(
        f"[DEBUG] Removed {before_count - after_count} outliers from daily throughput"
    )

    # --- Rolling average ---
    daily["rolling_avg"] = (
        daily["daily_sqft"].rolling(window=window, min_periods=1).mean()
    )
    daily["date"] = daily["date"].astype(str)

    return daily


def get_backlog_data(df):
    """Calculate backlog over time."""
    if df.empty:
        return pd.DataFrame(columns=["date", "backlog_sqft"])

    # Create events for incoming and completed orders
    incoming = df[df["datein"].notna()][["datein", "totalsize"]].copy()
    incoming.columns = ["date", "change"]
    incoming["change"] = incoming["change"]  # Positive change

    outgoing = df[df["datecompleted"].notna()][["datecompleted", "totalsize"]].copy()
    outgoing.columns = ["date", "change"]
    outgoing["change"] = -outgoing["change"]  # Negative change

    # Combine and sort
    events = pd.concat([incoming, outgoing]).sort_values("date")
    events["backlog_sqft"] = events["change"].cumsum()

    # Daily aggregation
    daily_backlog = (
        events.groupby(events["date"].dt.date)
        .agg({"backlog_sqft": "last"})
        .reset_index()
    )
    daily_backlog["date"] = daily_backlog["date"].astype(str)

    return daily_backlog


def get_revenue_by_product_type(df):
    """Get revenue by product type."""
    if df.empty:
        return {}

    revenue_by_type = df.groupby("product_type")["totalprice"].sum().to_dict()
    return {k: round(v, 2) for k, v in revenue_by_type.items()}


def get_weekly_sq_ft_cleaned_kde(df):
    """
    Calculates the KDE distribution of weekly square footage cleaned and
    the current week's total square footage cleaned.
    """

    if df.empty:
        return {"kde_values": [], "kde_densities": [], "this_week_sq_ft": 0}

    # Ensure 'datecompleted' is datetime and 'totalsize' is numeric
    df_cleaned = df[df["datecompleted"].notna()].copy()
    df_cleaned["datecompleted"] = pd.to_datetime(df_cleaned["datecompleted"])
    df_cleaned["totalsize"] = pd.to_numeric(
        df_cleaned["totalsize"], errors="coerce"
    ).fillna(0)

    # Group by week and sum 'totalsize'
    weekly_sq_ft = (
        df_cleaned.groupby(pd.Grouper(key="datecompleted", freq="W"))["totalsize"]
        .sum()
        .reset_index()
    )
    weekly_sq_ft.columns = ["week", "total_sq_ft"]

    # Filter out weeks with 0 sq ft cleaned if they are not representative
    weekly_sq_ft = weekly_sq_ft[weekly_sq_ft["total_sq_ft"] > 0]

    if weekly_sq_ft.empty:
        return {"kde_values": [], "kde_densities": [], "this_week_sq_ft": 0}

    # Calculate KDE
    data = weekly_sq_ft["total_sq_ft"].values
    if len(data) < 2:  # KDE requires at least 2 data points
        return {
            "kde_values": data.tolist(),
            "kde_densities": [1.0 / len(data)] * len(data) if len(data) > 0 else [],
            "this_week_sq_ft": 0,
        }

    kde = stats.gaussian_kde(data)
    # Generate values for the KDE plot
    x_values = np.linspace(data.min(), data.max(), 500)
    kde_densities = kde(x_values)

    # Get this week's square footage
    today = datetime.now()
    this_week_start = today - timedelta(days=today.weekday())  # Monday as start of week
    this_week_end = this_week_start + timedelta(days=6)

    this_week_data = df_cleaned[
        (df_cleaned["datecompleted"] >= this_week_start)
        & (df_cleaned["datecompleted"] <= this_week_end)
    ]
    this_week_sq_ft = this_week_data["totalsize"].sum()

    percentile = float(percentileofscore(data, this_week_sq_ft, kind="rank"))
    return {
        "kde_values": x_values.tolist(),
        "kde_densities": kde_densities.tolist(),
        "this_week_sq_ft": float(this_week_sq_ft),
        "mean": float(np.mean(data)),
        "median": float(np.median(data)),
        "percentiles": np.percentile(data, [25, 75]).tolist(),
        "percentile_rank": percentile,  # ← new
    }


# -----------------------------
# Routes
# -----------------------------


@analytics_bp.route("/")
@login_required
@role_required("admin", "manager")
@cache.cached(timeout=300, key_prefix="analytics_dashboard")
def analytics_dashboard():
    """Main analytics dashboard."""
    try:
        df = load_work_orders(db.engine)
        kpis = calculate_kpis(df)

        return render_template("analytics/dashboard.html", kpis=kpis)

    except Exception as e:
        print(f"[ERROR] Dashboard error: {e}")
        import traceback

        traceback.print_exc()
        return render_template(
            "analytics/dashboard.html", kpis={}, error_message=str(e)
        )


@analytics_bp.route("/api/data")
@login_required
@role_required("admin", "manager")
@cache.cached(timeout=300, key_prefix="analytics_api_data")
def get_analytics_data():
    """API endpoint for chart data."""
    try:
        df = load_work_orders(db.engine)

        monthly_trends = get_monthly_trends(df)
        daily_throughput = get_daily_throughput(df)
        backlog = get_backlog_data(df)
        revenue_by_product = get_revenue_by_product_type(df)

        weekly_kde_data = get_weekly_sq_ft_cleaned_kde(df)
        print(
            f"[DEBUG] Analytics data prepared for jsonify: monthly_trends={len(monthly_trends)}, daily_throughput={len(daily_throughput)}, backlog={len(backlog)}, revenue_by_product={revenue_by_product}, weekly_kde_data_points={len(weekly_kde_data['kde_values'])}, this_week_sq_ft={weekly_kde_data['this_week_sq_ft']}"
        )

        return jsonify(
            {
                "monthly_trends": monthly_trends.to_dict("records"),
                "daily_throughput": daily_throughput.to_dict("records"),
                "backlog": backlog.to_dict("records"),
                "revenue_by_product": revenue_by_product,
                "weekly_sq_ft_cleaned_kde": weekly_kde_data["kde_values"],
                "weekly_sq_ft_cleaned_densities": weekly_kde_data["kde_densities"],
                "this_week_sq_ft_cleaned": weekly_kde_data["this_week_sq_ft"],
                "weekly_sq_ft_cleaned_percentile": weekly_kde_data["percentile_rank"],
                "weekly_sq_ft_cleaned_mean": weekly_kde_data["mean"],
                "weekly_sq_ft_cleaned_median": weekly_kde_data["median"],
            }
        )

    except Exception as e:
        print(f"[ERROR] API error: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
