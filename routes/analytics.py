from flask import Blueprint, render_template
from flask_login import login_required
import polars as pl
import plotly.graph_objects as go
from extensions import db
import numpy as np
import re
from datetime import datetime
from sqlalchemy import text
import json

analytics_bp = Blueprint("analytics", __name__)

# -----------------------------
# Data Loading & Cleaning
# -----------------------------


def load_work_orders():
    """Load work orders from Postgres with Polars."""
    try:
        query = "SELECT * FROM tblcustworkorderdetail"
        print("[DEBUG] Loading work orders with query:", query)
        df = pl.read_database(query, db.engine, infer_schema_length=1000)
        print(f"[DEBUG] Loaded {len(df)} work orders with columns: {df.columns}")
        return df
    except Exception as e:
        print(f"[ERROR] Error loading work orders: {e}")
        return pl.DataFrame(
            {
                "WorkOrderNo": [],
                "CustID": [],
                "datein": [],
                "DateCompleted": [],
                "Quote": [],
                "RushOrder": [],
                "FirmRush": [],
            }
        )


def clean_sail_weight(value):
    if value is None or str(value).strip() in ["", "."]:
        return None
    match = re.match(r"^([\d.]+)#$", str(value).strip())
    if match:
        try:
            return float(match.group(1))
        except Exception as e:
            print(f"[WARN] Failed to convert sail weight '{value}': {e}")
            return None
    return None


def clean_awning_expr(column_name):
    return pl.col(column_name).map_elements(
        clean_square_footage, return_dtype=pl.Float64
    )


def clean_sail_expr(column_name):
    return pl.col(column_name).map_elements(clean_sail_weight, return_dtype=pl.Float64)


def convert_to_feet(dim):
    try:
        if "'" in dim:
            feet_part = float(dim.split("'")[0])
            inches_part = 0
            if '"' in dim:
                inches_str = dim.split("'")[1].replace('"', "")
                if inches_str:
                    inches_part = float(inches_str) / 12
            return feet_part + inches_part
        elif '"' in dim:
            return float(dim.replace('"', "")) / 12
        else:
            return float(dim)
    except Exception as e:
        print(f"[WARN] Failed to convert dimension '{dim}' to feet: {e}")
        return None


def clean_square_footage(value):
    if value is None:
        return None
    val = str(value).strip().lower()

    # Ignore placeholders
    if val in ["", ".", "na", "n/a"]:
        return None

    # Remove $ , and unit suffixes like ea, yds, yards, pcs
    val = re.sub(r"[\$,]", "", val)
    val = re.sub(r"\s*(ea\.?|yds?\.?|yards?|pcs?|each)\s*$", "", val)

    # Handle "8'9wide=90.00 ea." style
    if "=" in val:
        right = val.split("=")[-1]
        right = re.sub(r"[^0-9.]", "", right)
        try:
            return float(right)
        except ValueError:
            pass

    # Handle dimensions like 2x5 or 8'9"
    dims_match = re.match(r'^~?(\d+\'?\d*"?)\s*x\s*(\d+\'?\d*"?)', val)
    if dims_match:
        length = convert_to_feet(dims_match.group(1))
        width = convert_to_feet(dims_match.group(2))
        if length is not None and width is not None:
            return round(length * width, 2)

    val = val.strip("'")

    # Fallback numeric
    try:
        return float(val)
    except ValueError:
        # print(f"[WARN] Unparsed size/weight: '{value}'")
        return None


def inspect_orders():
    try:
        print("[DEBUG] --- Starting inspect_orders ---")

        # Load order details
        print("[DEBUG] Querying tblcustworkorderdetail...")
        query = """
        SELECT
            "workorderno",
            "custid",
            CAST("datein" AS TEXT) AS "datein",
            CAST("datecompleted" AS TEXT) AS "datecompleted",
            "quote",
            "rushorder",
            "firmrush"
        FROM tblcustworkorderdetail
        """
        wo_detail = pl.read_database(query, db.engine)
        print(
            f"[DEBUG] Loaded wo_detail: {len(wo_detail)} rows, columns: {wo_detail.columns}"
        )

        # Lowercase columns
        wo_detail = wo_detail.rename({c: c.lower() for c in wo_detail.columns})

        # --- Robust Date Parsing ---
        print("[DEBUG] Parsing date columns with strict=False (auto-infer format)...")
        for col in ["datein", "datecompleted"]:
            if col in wo_detail.columns:
                # Strip whitespace and replace any stray newlines
                wo_detail = wo_detail.with_columns(
                    pl.col(col)
                    .str.replace_all(r"\s+", " ")  # collapse spaces/newlines
                    .str.strip_chars()  # remove leading/trailing
                    .str.strptime(pl.Datetime, format="%m/%d/%y %H:%M:%S", strict=False)
                    .alias(f"{col}_parsed")
                )
                total = len(wo_detail)
                nulls = wo_detail[f"{col}_parsed"].is_null().sum()
                print(
                    f"[DEBUG] {col}: total={total}, null={nulls}, non-null={total - nulls}"
                )
                print(wo_detail.select([col, f"{col}_parsed"]).head(10))

        # Replace original date columns with parsed versions
        wo_detail = wo_detail.with_columns(
            [
                pl.col("datein_parsed").alias("datein"),
                pl.col("datecompleted_parsed").alias("datecompleted"),
            ]
        ).drop(["datein_parsed", "datecompleted_parsed"])

        # Load order items
        print("[DEBUG] Querying tblorddetcustawngs...")
        wo_items_query = "SELECT * FROM tblorddetcustawngs"
        wo_items = pl.read_database(wo_items_query, db.engine)
        print(
            f"[DEBUG] Loaded wo_items: {len(wo_items)} rows, columns: {wo_items.columns}"
        )
        wo_items = wo_items.rename({c: c.lower() for c in wo_items.columns})

        # --- Split awning vs sail items ---
        print("[DEBUG] Filtering awning and sail items...")
        awning_items = wo_items.filter(
            wo_items["sizewgt"].is_not_null() & ~wo_items["sizewgt"].str.contains("#")
        )
        sail_items = wo_items.filter(
            wo_items["sizewgt"].is_not_null() & wo_items["sizewgt"].str.contains("#")
        )
        print(
            f"[DEBUG] Awning items: {len(awning_items)}, Sail items: {len(sail_items)}"
        )

        # --- Compute totals ---
        print("[DEBUG] Calculating awning totals...")
        awning_items = awning_items.with_columns(
            (
                pl.col("qty").cast(pl.Float64, strict=False)
                * clean_awning_expr("sizewgt")
            ).alias("totalsize")
        )
        print(
            f"[DEBUG] Sample awning totals:\n{awning_items.select(['workorderno', 'totalsize']).head(5)}"
        )

        print("[DEBUG] Calculating sail totals...")
        sail_items = sail_items.with_columns(
            (
                pl.col("qty").cast(pl.Float64, strict=False)
                * clean_sail_expr("sizewgt")
            ).alias("totalweight")
        )
        print(
            f"[DEBUG] Sample sail totals:\n{sail_items.select(['workorderno', 'totalweight']).head(5)}"
        )

        # --- Aggregate totals ---
        print("[DEBUG] Aggregating awning totals...")
        awning_totals = awning_items.group_by("workorderno").agg(
            pl.sum("totalsize").alias("totalsize")
        )
        print(f"[DEBUG] Aggregated awning totals:\n{awning_totals.head(5)}")

        print("[DEBUG] Aggregating sail totals...")
        sail_totals = sail_items.group_by("workorderno").agg(
            pl.sum("totalweight").alias("totalweight")
        )
        print(f"[DEBUG] Aggregated sail totals:\n{sail_totals.head(5)}")

        # --- Join totals with orders ---
        print("[DEBUG] Joining totals with order details...")
        order_totals = awning_totals.join(
            sail_totals, on="workorderno", how="outer"
        ).fill_null(0)
        order_totals = order_totals.with_columns(
            (pl.col("totalsize") + pl.col("totalweight")).alias("combinedtotal")
        )
        print(f"[DEBUG] Sample order_totals after join:\n{order_totals.head(5)}")

        wo_detail = wo_detail.join(
            order_totals, on="workorderno", how="left"
        ).fill_null(0)
        print(f"[DEBUG] Sample merged wo_detail:\n{wo_detail.head(5)}")

        print(f"[DEBUG] --- Finished inspect_orders, total rows: {len(wo_detail)} ---")
        return wo_detail

    except Exception as e:
        import traceback

        print(f"[ERROR] inspect_orders failed: {e}")
        traceback.print_exc()
        return pl.DataFrame()


def calculate_kpis(df):
    print("[DEBUG] --- Starting calculate_kpis ---")
    print(f"[DEBUG] Columns in df: {df.columns}, total rows: {len(df)}")

    # Initialize default values
    total_orders = len(df)
    completed_orders = 0
    total_revenue = 0
    avg_revenue = 0
    unique_customers = 0

    if "datecompleted" in df.columns:
        completed_orders = len(df.filter(pl.col("datecompleted").is_not_null()))

    completion_rate = (
        round(completed_orders / total_orders * 100, 1) if total_orders > 0 else 0
    )

    if "quote" in df.columns:
        print("[DEBUG] Cleaning 'quote' column...")
        df = df.with_columns(
            pl.col("quote")
            .cast(pl.Utf8)
            .str.replace_all(r"[\$,]", "")
            .cast(pl.Float64, strict=False)
            .fill_null(0)
            .alias("quote")
        )
        print(f"[DEBUG] Sample quotes: {df['quote'].head(5).to_list()}")
        total_revenue = float(df["quote"].sum())
        avg_revenue = float(df["quote"].mean()) if total_orders > 0 else 0

    if "custid" in df.columns:
        unique_customers = df["custid"].n_unique()

    print(
        f"[DEBUG] KPIs calculated: total_orders={total_orders}, completed_orders={completed_orders}, total_revenue={total_revenue}"
    )
    return {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "completion_rate": completion_rate,
        "total_revenue": total_revenue,
        "avg_revenue": avg_revenue,
        "unique_customers": unique_customers,
    }


def get_throughput(df, window_size=7):
    print("[DEBUG] Computing throughput...")
    df = (
        df.filter(pl.col("datecompleted").is_not_null())
        if "datecompleted" in df.columns
        else pl.DataFrame()
    )
    if len(df) == 0:
        print("[DEBUG] No completed orders for throughput")
        return pl.DataFrame()
    daily = (
        df.group_by(pl.col("datecompleted").dt.date())
        .agg(pl.sum("totalsize").alias("totalsize"))
        .sort("datecompleted")
    )
    daily = daily.with_columns(
        pl.col("totalsize").rolling_mean(window_size).alias("Smoothing"),
        pl.col("totalsize").cum_sum().alias("CumulativeSize"),
    )
    return daily


def get_cumulative_uncleaned(df: pl.DataFrame) -> pl.DataFrame:
    print("[DEBUG] Computing cumulative uncleaned square footage...")

    # Incoming orders
    if "datein_parsed" in df.columns and "combinedtotal" in df.columns:
        df_in = df.select(["datein_parsed", "combinedtotal"]).rename(
            {"datein_parsed": "date", "combinedtotal": "size_change"}
        )
    else:
        df_in = pl.DataFrame(schema={"date": pl.Datetime, "size_change": pl.Float64})

    # Completed orders (negative)
    if "datecompleted_parsed" in df.columns and "combinedtotal" in df.columns:
        df_out = df.select(["datecompleted_parsed", "combinedtotal"]).rename(
            {"datecompleted_parsed": "date", "combinedtotal": "size_change"}
        )
        # Negate the size_change series directly
        df_out = df_out.with_columns(
            pl.Series("size_change", -df_out["size_change"].fill_null(0))
        )
    else:
        df_out = pl.DataFrame(schema={"date": pl.Datetime, "size_change": pl.Float64})

    # Combine
    changes = (
        pl.concat([df_in, df_out]).sort("date")
        if len(df_in) + len(df_out) > 0
        else pl.DataFrame()
    )

    # Compute cumulative sum on Series
    if len(changes) > 0:
        changes = changes.with_columns(
            pl.Series(
                "cumulative_uncleaned_sqft",
                changes["size_change"].fill_null(0).cum_sum(),
            )
        )

    return changes


def create_monthly_trend_chart(df):
    print("[DEBUG] Creating monthly trend chart...")
    if len(df) == 0 or "datein" not in df.columns:
        print("[WARN] Empty DataFrame or missing 'datein' column")
        return {}
    df = df.filter(pl.col("datein").is_not_null())
    monthly = (
        df.with_columns(pl.col("datein").dt.truncate("1mo").alias("month"))
        .group_by("month")
        .agg(pl.count().alias("order_count"))
        .sort("month")
    )
    fig = go.Figure(
        go.Scatter(
            x=monthly["month"].dt.strftime("%Y-%m").to_list(),
            y=monthly["order_count"].to_list(),
            mode="lines+markers",
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


def create_status_pie_chart(df):
    print("[DEBUG] Creating status pie chart...")
    if len(df) == 0:
        print("[WARN] Empty DataFrame for status chart")
        return {}
    completed = (
        len(df.filter(pl.col("datecompleted").is_not_null()))
        if "datecompleted" in df.columns
        else 0
    )
    pending = len(df) - completed
    fig = go.Figure(
        go.Pie(
            labels=["Completed", "Pending"],
            values=[completed, pending],
            hole=0.3,
            marker_colors=["#2ecc71", "#f39c12"],
        )
    )
    fig.update_layout(
        title="Order Status Distribution", template="plotly_white", height=400
    )
    return fig.to_json()


@analytics_bp.route("/")
@login_required
def analytics_dashboard():
    try:
        print("[DEBUG] Loading analytics dashboard...")
        df_orders = inspect_orders()
        print(f"[DEBUG] Orders inspected: {len(df_orders)} rows")
        kpis = calculate_kpis(df_orders)
        monthly_chart = create_monthly_trend_chart(df_orders)
        status_chart = create_status_pie_chart(df_orders)
        throughput = get_throughput(df_orders)
        cumulative = get_cumulative_uncleaned(df_orders)

        return render_template(
            "analytics/dashboard.html",
            kpis=kpis,
            monthly_chart=monthly_chart if monthly_chart else json.dumps({}),
            status_chart=status_chart if status_chart else json.dumps({}),
            total_records=len(df_orders),
            throughput=throughput.to_dicts() if not throughput.is_empty() else [],
            cumulative=cumulative.to_dicts() if not cumulative.is_empty() else [],
        )

    except Exception as e:
        print(f"[ERROR] Dashboard error: {e}")
        return render_template(
            "analytics/dashboard.html",
            kpis={},
            monthly_chart={},
            status_chart={},
            total_records=0,
            error_message=str(e),
            throughput=[],
            cumulative=[],
        )
