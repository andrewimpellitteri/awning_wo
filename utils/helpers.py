from datetime import datetime

def format_date_from_str(date_str):
    """Attempts to parse a date string from various formats."""
    if date_str is None or date_str == "":
        return None
    try:
        return datetime.strptime(date_str, "%m/%d/%y %H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None

def safe_date_sort_key(date_obj):
    """Returns a sortable key for date objects, handling None values."""
    if date_obj is None:
        return datetime.min
    if isinstance(date_obj, str):
        return format_date_from_str(date_obj) or datetime.min
    return date_obj


from models.work_order import WorkOrder
from extensions import db

def initialize_queue_positions_for_unassigned():
    """Assigns sequential queue positions to work orders that don't have one.

    NOTE: This is a simple version for testing. The production version with
    priority handling is in routes/queue.py
    """
    with db.session.no_autoflush:
        work_orders = WorkOrder.query.all()
        max_position = -1
        for wo in work_orders:
            if wo.QueuePosition is not None and wo.QueuePosition > max_position:
                max_position = wo.QueuePosition

        for wo in work_orders:
            if wo.QueuePosition is None:
                max_position += 1
                wo.QueuePosition = max_position
        db.session.commit()

import os
import secrets
from PIL import Image
from flask import current_app

def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_uploaded_photo(form_photo, customer_id):
    """Save uploaded photo and return filename"""
    if form_photo and allowed_file(form_photo.filename):
        # Generate secure filename
        random_hex = secrets.token_hex(8)
        _, f_ext = os.path.splitext(form_photo.filename)
        photo_filename = f"customer_{customer_id}_{random_hex}{f_ext}"
        
        # Create customer photo directory
        customer_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'photos', str(customer_id))
        os.makedirs(customer_dir, exist_ok=True)
        
        photo_path = os.path.join(customer_dir, photo_filename)
        
        # Resize image to save space
        img = Image.open(form_photo)
        img.thumbnail((1200, 1200))
        img.save(photo_path)
        
        return photo_filename, photo_path
    
    return None, None

def generate_work_order_number():
    """Generate next work order number"""
    from models.work_order import WorkOrder
    
    last_wo = WorkOrder.query.order_by(WorkOrder.id.desc()).first()
    next_id = (last_wo.id + 1) if last_wo else 1
    return f"WO{next_id:06d}"

def generate_repair_order_number():
    """Generate next repair order number"""
    from models.repair_order import RepairOrder
    
    last_ro = RepairOrder.query.order_by(RepairOrder.id.desc()).first()
    next_id = (last_ro.id + 1) if last_ro else 1
    return f"RO{next_id:06d}"

def format_phone_number(phone):
    """Format phone number for display"""
    if not phone:
        return ""
    
    # Remove all non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        return phone

def calculate_days_since(date):
    """Calculate days since a given date"""
    if not date:
        return None
    
    if isinstance(date, str):
        date = datetime.strptime(date, '%Y-%m-%d').date()
    
    return (datetime.now().date() - date).days

def get_status_color(status):
    """Return Bootstrap color class for status"""
    status_colors = {
        'pending': 'warning',
        'in_progress': 'info',
        'completed': 'success',
        'cancelled': 'danger',
        'on_hold': 'secondary'
    }
    
    return status_colors.get(status.lower() if status else '', 'secondary')

def paginate_query(query, page, per_page=50):
    """Helper function for pagination"""
    return query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

def map_bool_display(value, true_text="Yes", false_text="No", default=False):
    """
    Map boolean values to display text for PDFs and other outputs.

    Args:
        value: The value to convert (bool, int, str, or None)
        true_text: Text to display for True values (default: "Yes")
        false_text: Text to display for False values (default: "No")
        default: Default boolean value if conversion fails (default: False)

    Returns:
        str: The mapped display text

    Examples:
        >>> map_bool_display(True)
        'Yes'
        >>> map_bool_display(False)
        'No'
        >>> map_bool_display("1")
        'Yes'
        >>> map_bool_display(0)
        'No'
        >>> map_bool_display(None)
        'No'
        >>> map_bool_display(True, "✓", "✗")
        '✓'
    """
    # Convert to boolean first
    is_true = safe_bool_convert(value, default=default)
    return true_text if is_true else false_text

def safe_bool_convert(value, default=False):
    """
    Safely convert various types to boolean.

    Args:
        value: The value to convert (bool, int, str, or None)
        default: Default value if conversion fails (default: False)

    Returns:
        bool: The converted boolean value

    Examples:
        >>> safe_bool_convert(True)
        True
        >>> safe_bool_convert("1")
        True
        >>> safe_bool_convert("yes")
        True
        >>> safe_bool_convert(0)
        False
        >>> safe_bool_convert(None)
        False
        >>> safe_bool_convert("invalid", default=True)
        True
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.lower() in ("true", "yes", "1", "y")
    return default
