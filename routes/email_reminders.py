from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required
from models.customer import Customer
from models.work_order import WorkOrder
from models.email_reminder import EmailReminder
from services.email_service import EmailService
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from extensions import db
import os

email_reminders_bp = Blueprint('email_reminders', __name__, url_prefix='/email-reminders')

def get_customers_due_for_reminders(days_since_last=335, days_window=30):
    """
    Find customers who are due for cleaning reminders.

    Args:
        days_since_last: Number of days since last cleaning (default ~11 months)
        days_window: Window of days to look back (default 30 days)

    Returns:
        List of tuples: (Customer, last_completed_date, days_since_cleaning)
    """
    cutoff_date = datetime.now() - timedelta(days=days_since_last)
    window_start = datetime.now() - timedelta(days=days_since_last + days_window)

    # Subquery to get latest completed work order per customer
    latest_orders = db.session.query(
        WorkOrder.CustID,
        func.max(WorkOrder.DateCompleted).label('last_completed')
    ).filter(
        WorkOrder.DateCompleted.isnot(None)
    ).group_by(WorkOrder.CustID).subquery()

    # Get customers with email addresses whose last order was in the target window
    customers_due = db.session.query(
        Customer,
        latest_orders.c.last_completed
    ).join(
        latest_orders, Customer.CustID == latest_orders.c.CustID
    ).filter(
        and_(
            latest_orders.c.last_completed >= window_start,
            latest_orders.c.last_completed <= cutoff_date,
            Customer.EmailAddress.isnot(None),
            Customer.EmailAddress != ''
        )
    ).all()

    # Calculate days since cleaning and filter out those already reminded recently
    results = []
    for customer, last_date in customers_due:
        # Check if we already sent a reminder in the last 60 days
        recent_reminder = EmailReminder.query.filter(
            and_(
                EmailReminder.custid == customer.CustID,
                EmailReminder.date_sent >= datetime.now() - timedelta(days=60),
                EmailReminder.status == 'sent'
            )
        ).first()

        if not recent_reminder:
            days_since = (datetime.now() - last_date).days
            results.append((customer, last_date, days_since))

    return results


@email_reminders_bp.route('/')
@login_required
def dashboard():
    """Display dashboard with customers due for reminders."""
    customers_due = get_customers_due_for_reminders()

    # Get recent sent reminders
    recent_reminders = EmailReminder.query.order_by(
        EmailReminder.date_sent.desc()
    ).limit(50).all()

    # Calculate statistics
    total_sent_this_month = EmailReminder.query.filter(
        EmailReminder.date_sent >= datetime.now().replace(day=1)
    ).count()

    return render_template(
        'email_reminders/dashboard.html',
        customers_due=customers_due,
        recent_reminders=recent_reminders,
        total_sent_this_month=total_sent_this_month
    )


@email_reminders_bp.route('/send/<custid>', methods=['POST'])
@login_required
def send_reminder(custid):
    """Send a reminder email to a specific customer."""
    customer = Customer.query.get_or_404(custid)

    if not customer.EmailAddress:
        flash('Customer has no email address on file.', 'danger')
        return redirect(url_for('email_reminders.dashboard'))

    # Get last completed work order date
    last_order = WorkOrder.query.filter(
        and_(
            WorkOrder.CustID == custid,
            WorkOrder.DateCompleted.isnot(None)
        )
    ).order_by(WorkOrder.DateCompleted.desc()).first()

    last_date = last_order.DateCompleted if last_order else None

    # Send email
    email_service = EmailService()
    success, message = email_service.send_cleaning_reminder(customer, last_date)

    # Log the reminder
    reminder = EmailReminder(
        custid=customer.CustID,
        email_address=customer.EmailAddress,
        date_sent=datetime.utcnow(),
        message_id=message if success else None,
        status='sent' if success else 'failed',
        error_message=None if success else message,
        last_work_order_date=last_date
    )
    db.session.add(reminder)
    db.session.commit()

    if success:
        flash(f'Reminder email sent to {customer.Name}!', 'success')
    else:
        flash(f'Failed to send email: {message}', 'danger')

    return redirect(url_for('email_reminders.dashboard'))


@email_reminders_bp.route('/send-batch', methods=['POST'])
@login_required
def send_batch():
    """Send reminder emails to all customers due for reminders."""
    customers_due = get_customers_due_for_reminders()

    if not customers_due:
        flash('No customers are currently due for reminders.', 'info')
        return redirect(url_for('email_reminders.dashboard'))

    email_service = EmailService()
    sent_count = 0
    failed_count = 0

    for customer, last_date, days_since in customers_due:
        success, message = email_service.send_cleaning_reminder(customer, last_date)

        # Log the reminder
        reminder = EmailReminder(
            custid=customer.CustID,
            email_address=customer.EmailAddress,
            date_sent=datetime.utcnow(),
            message_id=message if success else None,
            status='sent' if success else 'failed',
            error_message=None if success else message,
            last_work_order_date=last_date
        )
        db.session.add(reminder)

        if success:
            sent_count += 1
        else:
            failed_count += 1

    db.session.commit()

    flash(f'Batch complete: {sent_count} sent, {failed_count} failed.', 'success' if failed_count == 0 else 'warning')
    return redirect(url_for('email_reminders.dashboard'))


@email_reminders_bp.route('/cron/send', methods=['POST'])
def cron_send_reminders():
    """
    Automated endpoint for sending reminder emails via cron job.
    Requires X-Cron-Secret header for authentication.
    """
    # Verify cron secret
    cron_secret = request.headers.get('X-Cron-Secret')
    expected_secret = os.environ.get('CRON_SECRET')

    if not expected_secret or cron_secret != expected_secret:
        return jsonify({'error': 'Unauthorized'}), 401

    customers_due = get_customers_due_for_reminders()

    if not customers_due:
        return jsonify({
            'status': 'success',
            'message': 'No customers due for reminders',
            'sent': 0,
            'failed': 0
        })

    email_service = EmailService()
    sent_count = 0
    failed_count = 0

    for customer, last_date, days_since in customers_due:
        success, message = email_service.send_cleaning_reminder(customer, last_date)

        # Log the reminder
        reminder = EmailReminder(
            custid=customer.CustID,
            email_address=customer.EmailAddress,
            date_sent=datetime.utcnow(),
            message_id=message if success else None,
            status='sent' if success else 'failed',
            error_message=None if success else message,
            last_work_order_date=last_date
        )
        db.session.add(reminder)

        if success:
            sent_count += 1
        else:
            failed_count += 1

    db.session.commit()

    return jsonify({
        'status': 'success',
        'sent': sent_count,
        'failed': failed_count,
        'total_checked': len(customers_due)
    })


@email_reminders_bp.route('/history')
@login_required
def history():
    """View complete history of sent reminders."""
    page = request.args.get('page', 1, type=int)
    per_page = 50

    reminders = EmailReminder.query.order_by(
        EmailReminder.date_sent.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'email_reminders/history.html',
        reminders=reminders
    )
