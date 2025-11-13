from extensions import db
from datetime import datetime

class EmailReminder(db.Model):
    """Track cleaning reminder emails sent to customers."""
    __tablename__ = 'email_reminders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    custid = db.Column(db.String, db.ForeignKey('tblcustomers.custid'), nullable=False)
    email_address = db.Column(db.String(255), nullable=False)
    date_sent = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    message_id = db.Column(db.String(255))  # SES Message ID for tracking
    status = db.Column(db.String(50), default='sent')  # sent, failed, bounced
    error_message = db.Column(db.Text)  # Store error if failed
    last_work_order_date = db.Column(db.Date)  # Date of last completed work order when reminder was sent

    # Relationship to Customer
    customer = db.relationship('Customer', backref=db.backref('email_reminders', lazy='dynamic'))

    def __repr__(self):
        return f'<EmailReminder {self.id}: {self.email_address} on {self.date_sent}>'
