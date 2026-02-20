from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User

def send_staff_notification(subject, message, html_message=None):
    """
    Sends an email notification to all staff members.
    """
    # Get all staff emails
    staff_emails = list(User.objects.filter(is_staff=True).exclude(email='').values_list('email', flat=True))
    
    if not staff_emails:
        print("No staff emails found to send notification.")
        return
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'crm@techvilo.com'),
            recipient_list=staff_emails,
            fail_silently=False,
            html_message=html_message
        )
        print(f"Notification sent to {len(staff_emails)} staff members.")
    except Exception as e:
        print(f"Failed to send staff notification: {e}")
