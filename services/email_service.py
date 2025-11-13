import boto3
from botocore.exceptions import ClientError
from flask import current_app, render_template
import logging

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails via Amazon SES."""

    def __init__(self):
        """Initialize SES client with AWS credentials from config."""
        self.ses_client = boto3.client(
            'ses',
            region_name=current_app.config.get('AWS_REGION', 'us-east-1'),
            aws_access_key_id=current_app.config.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=current_app.config.get('AWS_SECRET_ACCESS_KEY')
        )
        self.from_email = current_app.config.get('FROM_EMAIL', 'reminders@yourdomain.com')

    def send_cleaning_reminder(self, customer, last_completed_date=None):
        """
        Send a cleaning reminder email to a customer.

        Args:
            customer: Customer model instance
            last_completed_date: Optional datetime of last completed work order

        Returns:
            tuple: (success: bool, message_id_or_error: str)
        """
        try:
            # Render HTML email from template
            html_body = render_template(
                'emails/cleaning_reminder.html',
                customer=customer,
                last_completed_date=last_completed_date
            )

            # Plain text fallback
            text_body = f"""Hi {customer.Name},

It's been about a year since we last cleaned your awnings. Regular cleaning helps extend
the life of your awnings, maintain their appearance, and prevent mold and mildew buildup.

We'd love to help you schedule your next cleaning!

Call us to schedule your appointment.

Thanks for your continued business!
- The Awning Cleaning Team"""

            # Send via SES
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={
                    'ToAddresses': [customer.EmailAddress]
                },
                Message={
                    'Subject': {
                        'Data': 'Time for Your Annual Awning Cleaning',
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Html': {
                            'Data': html_body,
                            'Charset': 'UTF-8'
                        },
                        'Text': {
                            'Data': text_body,
                            'Charset': 'UTF-8'
                        }
                    }
                },
                ReplyToAddresses=[self.from_email]
            )

            message_id = response['MessageId']
            logger.info(f"Email sent to {customer.EmailAddress} (Customer: {customer.Name}). MessageId: {message_id}")
            return True, message_id

        except ClientError as e:
            error_msg = e.response['Error']['Message']
            logger.error(f"Failed to send email to {customer.EmailAddress}: {error_msg}")
            return False, error_msg
        except Exception as e:
            logger.error(f"Unexpected error sending email to {customer.EmailAddress}: {str(e)}")
            return False, str(e)

    def send_batch_reminders(self, customers_with_dates):
        """
        Send reminder emails to multiple customers.

        Args:
            customers_with_dates: List of tuples (customer, last_completed_date)

        Returns:
            dict: {'sent': int, 'failed': int, 'results': list}
        """
        results = []
        sent_count = 0
        failed_count = 0

        for customer, last_date in customers_with_dates:
            success, message = self.send_cleaning_reminder(customer, last_date)

            results.append({
                'customer': customer,
                'success': success,
                'message': message
            })

            if success:
                sent_count += 1
            else:
                failed_count += 1

        return {
            'sent': sent_count,
            'failed': failed_count,
            'results': results
        }