from flask import Blueprint, render_template, jsonify
from flask_login import login_required
import pandas as pd
from extensions import db
import re
from datetime import datetime, timedelta
from sqlalchemy import text
from decorators import role_required

analytics_bp = Blueprint("analytics", __name__)


# -----------------------------
# Utility Functions
# -----------------------------

def clean_numeric_string(value):
    """Clean currency strings to float."""
    if pd.isna(value) or value in ['', None, 'Approved']:
        return 0.0
    try:
        cleaned = str(value).replace('$', '').replace(',', '').strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return 0.0


def clean_square_footage(value):
    """Parse size strings like '8x10', '8'9\"x10'2\"', or plain numbers."""
    if pd.isna(value) or value in ['', '.', 'na', 'n/a', None]:
        return 0.0

    val = str(value).strip().lower()

    # Remove currency and unit markers
    val = re.sub(r'[\$,]', '', val)
    val = re.sub(r'\s*(ea\.?|yds?\.?|yards?|pcs?|each)\s*$', '', val)

    # Handle "8'9wide=90.00 ea." style
    if '=' in val:
        right = val.split('=')[-1]
        right = re.sub(r'[^0-9.]', '', right)
        try:
            return float(right)
        except ValueError:
            pass

    # Handle dimensions like 2x5 or 8'9"x10'2"
    dims_match = re.match(r'^~?(\d+\'?\d*"?)\s*x\s*(\d+\'?\d*"?)', val)
    if dims_match:
        def convert_to_feet(dim):
            try:
                if "'" in dim:
                    feet = float(dim.split("'")[0])
                    inches = 0
                    if '"' in dim:
                        inches_str = dim.split("'")[1].replace('"', '')
                        if inches_str:
                            inches = float(inches_str) / 12
                    return feet + inches
                elif '"' in dim:
                    return float(dim.replace('"', '')) / 12
                else:
                    return float(dim)
            except:
                return 0

        length = convert_to_feet(dims_match.group(1))
        width = convert_to_feet(dims_match.group(2))
        return round(length * width, 2)

    # Try plain number
    val = val.strip("'")
    try:
        return float(val)
    except ValueError:
        return 0.0


def clean_sail_weight(value):
    """Parse sail weight strings like '95#'."""
    if pd.isna(value) or str(value).strip() in ['', '.']:
        return 0.0
    match = re.match(r'^([\d.]+)#$', str(value).strip())
    if match:
        try:
            return float(match.group(1))
        except:
            return 0.0
    return 0.0


# -----------------------------
# Data Loading
# -----------------------------

def load_work_orders():
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
        df = pd.read_sql(query, db.engine)

        # Parse dates (now proper date/datetime objects from DB, not strings)
        df['datein'] = pd.to_datetime(df['datein'], errors='coerce')
        df['datecompleted'] = pd.to_datetime(df['datecompleted'], errors='coerce')

        # Clean quote column
        df['quote_numeric'] = df['quote'].apply(clean_numeric_string)

        # Load order items
        items_query = "SELECT workorderno, custid, qty, sizewgt FROM tblorddetcustawngs"
        items = pd.read_sql(items_query, db.engine)

        # Separate awnings and sails
        items['sizewgt'] = items['sizewgt'].astype(str)
        items['is_sail'] = items['sizewgt'].str.contains('#', na=False)

        # Calculate sizes
        items['qty_numeric'] = pd.to_numeric(items['qty'], errors='coerce').fillna(0)
        items['sqft'] = items.apply(
            lambda row: row['qty_numeric'] * (
                clean_sail_weight(row['sizewgt']) if row['is_sail']
                else clean_square_footage(row['sizewgt'])
            ), axis=1
        )

        # Aggregate by work order
        totals = items.groupby('workorderno').agg({
            'sqft': 'sum'
        }).reset_index()
        totals.columns = ['workorderno', 'totalsize']

        # Merge with work orders
        df = df.merge(totals, on='workorderno', how='left')
        df['totalsize'] = df['totalsize'].fillna(0)

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
            'total_orders': 0,
            'completed_orders': 0,
            'open_orders': 0,
            'completion_rate': 0,
            'total_revenue': 0,
            'avg_revenue': 0,
            'total_sqft_completed': 0,
            'avg_throughput_7d': 0,
            'unique_customers': 0
        }

    total_orders = len(df)
    completed_orders = df['datecompleted'].notna().sum()
    open_orders = total_orders - completed_orders
    completion_rate = round((completed_orders / total_orders * 100), 1) if total_orders > 0 else 0

    total_revenue = df['quote_numeric'].sum()
    avg_revenue = df['quote_numeric'].mean() if total_orders > 0 else 0

    unique_customers = df['custid'].nunique()

    # Throughput calculations
    completed_df = df[df['datecompleted'].notna()].copy()
    total_sqft_completed = completed_df['totalsize'].sum()

    # Last 7 days throughput
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_completed = completed_df[completed_df['datecompleted'] >= seven_days_ago]
    avg_throughput_7d = recent_completed['totalsize'].sum() / 7 if len(recent_completed) > 0 else 0

    return {
        'total_orders': total_orders,
        'completed_orders': completed_orders,
        'open_orders': open_orders,
        'completion_rate': completion_rate,
        'total_revenue': total_revenue,
        'avg_revenue': avg_revenue,
        'total_sqft_completed': total_sqft_completed,
        'avg_throughput_7d': round(avg_throughput_7d, 1),
        'unique_customers': unique_customers
    }


def get_monthly_trends(df):
    """Get monthly order trends."""
    if df.empty or 'datein' not in df.columns:
        return pd.DataFrame(columns=['month', 'order_count', 'completed_count', 'total_sqft'])

    df_clean = df[df['datein'].notna()].copy()
    df_clean['month'] = df_clean['datein'].dt.to_period('M')

    monthly = df_clean.groupby('month').agg({
        'workorderno': 'count',
        'datecompleted': lambda x: x.notna().sum(),
        'totalsize': 'sum'
    }).reset_index()

    monthly.columns = ['month', 'order_count', 'completed_count', 'total_sqft']
    monthly['month'] = monthly['month'].astype(str)

    return monthly.tail(12)  # Last 12 months


def get_daily_throughput(df, window=7):
    """Calculate daily throughput with rolling average."""
    if df.empty:
        return pd.DataFrame(columns=['date', 'daily_sqft', 'rolling_avg'])

    completed = df[df['datecompleted'].notna()].copy()
    if completed.empty:
        return pd.DataFrame(columns=['date', 'daily_sqft', 'rolling_avg'])

    daily = completed.groupby(completed['datecompleted'].dt.date).agg({
        'totalsize': 'sum'
    }).reset_index()
    daily.columns = ['date', 'daily_sqft']

    # Calculate rolling average
    daily['rolling_avg'] = daily['daily_sqft'].rolling(window=window, min_periods=1).mean()
    daily['date'] = daily['date'].astype(str)

    return daily.tail(90)  # Last 90 days


def get_backlog_data(df):
    """Calculate backlog over time."""
    if df.empty:
        return pd.DataFrame(columns=['date', 'backlog_sqft'])

    # Create events for incoming and completed orders
    incoming = df[df['datein'].notna()][['datein', 'totalsize']].copy()
    incoming.columns = ['date', 'change']
    incoming['change'] = incoming['change']  # Positive change

    outgoing = df[df['datecompleted'].notna()][['datecompleted', 'totalsize']].copy()
    outgoing.columns = ['date', 'change']
    outgoing['change'] = -outgoing['change']  # Negative change

    # Combine and sort
    events = pd.concat([incoming, outgoing]).sort_values('date')
    events['backlog_sqft'] = events['change'].cumsum()

    # Daily aggregation
    daily_backlog = events.groupby(events['date'].dt.date).agg({
        'backlog_sqft': 'last'
    }).reset_index()
    daily_backlog['date'] = daily_backlog['date'].astype(str)

    return daily_backlog.tail(90)  # Last 90 days


def get_status_distribution(df):
    """Get order status distribution."""
    if df.empty:
        return {'Completed': 0, 'Pending': 0}

    completed = df['datecompleted'].notna().sum()
    pending = df['datecompleted'].isna().sum()

    return {'Completed': completed, 'Pending': pending}


# -----------------------------
# Routes
# -----------------------------

@analytics_bp.route("/")
@login_required
@role_required("admin", "manager")
def analytics_dashboard():
    """Main analytics dashboard."""
    try:
        df = load_work_orders()
        kpis = calculate_kpis(df)

        return render_template(
            "analytics/dashboard.html",
            kpis=kpis
        )

    except Exception as e:
        print(f"[ERROR] Dashboard error: {e}")
        import traceback
        traceback.print_exc()
        return render_template(
            "analytics/dashboard.html",
            kpis={},
            error_message=str(e)
        )


@analytics_bp.route("/api/data")
@login_required
@role_required("admin", "manager")
def get_analytics_data():
    """API endpoint for chart data."""
    try:
        df = load_work_orders()

        monthly_trends = get_monthly_trends(df)
        daily_throughput = get_daily_throughput(df)
        backlog = get_backlog_data(df)
        status_dist = get_status_distribution(df)

        return jsonify({
            'monthly_trends': monthly_trends.to_dict('records'),
            'daily_throughput': daily_throughput.to_dict('records'),
            'backlog': backlog.to_dict('records'),
            'status_distribution': status_dist
        })

    except Exception as e:
        print(f"[ERROR] API error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
