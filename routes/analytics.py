from flask import Blueprint, render_template, request
from flask_login import login_required
import polars as pl
import plotly.graph_objects as go
from extensions import db
from datetime import datetime, timedelta
import json

analytics_bp = Blueprint("analytics", __name__)


def load_work_orders():
    """Fetch work orders from database with robust data handling"""
    try:
        engine = db.engine
        query = "SELECT * FROM tblcustworkorderdetail"

        # Read with minimal processing to avoid type conflicts
        df = pl.read_database(
            query,
            engine,
            infer_schema_length=1000,  # Increase schema inference
        )

        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        # Return empty dataframe with basic schema
        return pl.DataFrame(
            {
                "custid": [],
                "datein": [],
                "datecompleted": [],
                "quote": [],
                "rushorder": [],
                "firmrush": [],
                "storage": [],
                "clean": [],
                "treat": [],
                "repairsneeded": [],
            }
        )


def safe_date_parse(df, column_name):
    """Safely parse date columns with multiple formats"""
    if column_name not in df.columns:
        return df

    try:
        # First, handle null/empty values
        df = df.with_columns(
            pl.when(
                pl.col(column_name).is_null()
                | (pl.col(column_name).str.strip_chars() == "")
            )
            .then(None)
            .otherwise(pl.col(column_name))
            .alias(column_name)
        )

        # Try to parse as date, fallback to null if fails
        df = df.with_columns(
            pl.col(column_name)
            .str.strptime(pl.Date, "%Y-%m-%d", strict=False)
            .alias(column_name)
        )
    except Exception as e:
        print(f"Date parsing error for {column_name}: {e}")
        # If parsing fails, set all to null
        df = df.with_columns(pl.lit(None).alias(column_name))

    return df


def calculate_kpis(df):
    """Calculate basic KPIs from the dataframe"""
    if len(df) == 0:
        return {
            "total_orders": 0,
            "completed_orders": 0,
            "completion_rate": 0,
            "total_revenue": 0,
            "avg_revenue": 0,
            "unique_customers": 0,
        }

    try:
        total_orders = len(df)

        # Count completed orders (where datecompleted is not null)
        completed_orders = df.filter(pl.col("datecompleted").is_not_null()).height
        completion_rate = (
            round((completed_orders / total_orders * 100), 1) if total_orders > 0 else 0
        )

        # Revenue calculations
        revenue_col = "quote" if "quote" in df.columns else None
        if revenue_col and df[revenue_col].dtype in [
            pl.Float64,
            pl.Float32,
            pl.Int64,
            pl.Int32,
        ]:
            total_revenue = df[revenue_col].sum() or 0
            avg_revenue = df[revenue_col].mean() or 0
        else:
            total_revenue = 0
            avg_revenue = 0

        # Customer count
        unique_customers = df["custid"].n_unique() if "custid" in df.columns else 0

        return {
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "completion_rate": completion_rate,
            "total_revenue": float(total_revenue),
            "avg_revenue": float(avg_revenue),
            "unique_customers": unique_customers,
        }
    except Exception as e:
        print(f"KPI calculation error: {e}")
        return {
            "total_orders": len(df),
            "completed_orders": 0,
            "completion_rate": 0,
            "total_revenue": 0,
            "avg_revenue": 0,
            "unique_customers": 0,
        }


def create_monthly_trend_chart(df):
    """Create a simple monthly orders trend chart"""
    if len(df) == 0 or "datein" not in df.columns:
        return json.dumps({})

    try:
        # Filter out null dates and group by month
        monthly_data = (
            df.filter(pl.col("datein").is_not_null())
            .with_columns(pl.col("datein").dt.truncate("1mo").alias("month"))
            .group_by("month")
            .agg(pl.count().alias("order_count"))
            .sort("month")
        )

        if len(monthly_data) == 0:
            return json.dumps({})

        months = monthly_data["month"].dt.strftime("%Y-%m").to_list()
        counts = monthly_data["order_count"].to_list()

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=months,
                y=counts,
                mode="lines+markers",
                name="Orders",
                line=dict(color="#3498db", width=3),
                marker=dict(size=8),
            )
        )

        fig.update_layout(
            title="Monthly Orders Trend",
            xaxis_title="Month",
            yaxis_title="Number of Orders",
            template="plotly_white",
            height=400,
        )

        return fig.to_json()
    except Exception as e:
        print(f"Chart creation error: {e}")
        return json.dumps({})


def create_status_pie_chart(df):
    """Create order status pie chart"""
    if len(df) == 0:
        return json.dumps({})

    try:
        completed = df.filter(pl.col("datecompleted").is_not_null()).height
        pending = len(df) - completed

        fig = go.Figure(
            data=[
                go.Pie(
                    labels=["Completed", "Pending"],
                    values=[completed, pending],
                    hole=0.3,
                    marker_colors=["#2ecc71", "#f39c12"],
                )
            ]
        )

        fig.update_layout(
            title="Order Status Distribution", template="plotly_white", height=400
        )

        return fig.to_json()
    except Exception as e:
        print(f"Pie chart error: {e}")
        return json.dumps({})


@analytics_bp.route("/")
@login_required
def analytics_dashboard():
    try:
        # Load and process data
        df_orders = load_work_orders()

        # Parse dates safely
        df_orders = safe_date_parse(df_orders, "datein")
        df_orders = safe_date_parse(df_orders, "datecompleted")

        # Calculate KPIs
        kpis = calculate_kpis(df_orders)

        # Create charts
        monthly_chart = create_monthly_trend_chart(df_orders)
        status_chart = create_status_pie_chart(df_orders)

        return render_template(
            "analytics/dashboard.html",
            kpis=kpis,
            monthly_chart=monthly_chart,
            status_chart=status_chart,
            total_records=len(df_orders),
        )

    except Exception as e:
        print(f"Dashboard error: {e}")
        # Return dashboard with error state
        return render_template(
            "analytics/dashboard.html",
            kpis={
                "total_orders": 0,
                "completed_orders": 0,
                "completion_rate": 0,
                "total_revenue": 0,
                "avg_revenue": 0,
                "unique_customers": 0,
            },
            monthly_chart=json.dumps({}),
            status_chart=json.dumps({}),
            total_records=0,
            error_message=str(e),
        )
