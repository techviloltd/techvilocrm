from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Client, Project, Lead, Transaction
from .utils import send_staff_notification

def clear_dashboard_cache(instance):
    """Clear all dashboard-related caches when data changes."""
    # We use a pattern to clear relevant caches. 
    # Since locmem doesn't support clear by pattern easily, we can just clear everything
    # or specific keys if we know them. For simplicity and reliability:
    cache.clear()
    print("DEBUG: Dashboard cache cleared due to data change.")

@receiver([post_save, post_delete], sender=Client)
def on_client_change(sender, instance, **kwargs):
    clear_dashboard_cache(instance)

@receiver([post_save, post_delete], sender=Project)
def on_project_change(sender, instance, **kwargs):
    clear_dashboard_cache(instance)

@receiver([post_save, post_delete], sender=Lead)
def on_lead_change(sender, instance, **kwargs):
    clear_dashboard_cache(instance)

@receiver([post_save, post_delete], sender=Transaction)
def on_transaction_change(sender, instance, **kwargs):
    clear_dashboard_cache(instance)

@receiver(post_save, sender=Client)
def notify_new_client(sender, instance, created, **kwargs):
    if created:
        subject = f"🚀 New Client Joined: {instance.name}"
        # ... (rest of the notification logic remains the same)
        
        # Plain text fallback
        message = f"""
        New Client Added:
        Name: {instance.name}
        Company: {instance.company_name}
        Services: {instance.services}
        
        View in Admin: http://127.0.0.1:8000/admin/crm/client/{instance.id}/change/
        """
        
        # HTML Message
        html_message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <h2 style="color: #FF8C00; text-align: center;">Techvilo CRM</h2>
            <hr style="border: 0; border-top: 1px solid #eee;">
            <h3 style="color: #333;">🚀 New Client Joined!</h3>
            <p style="color: #555;">A new client has been added to the system.</p>
            
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr style="background-color: #f9f9f9;">
                    <td style="padding: 10px; font-weight: bold; width: 30%;">Name:</td>
                    <td style="padding: 10px;">{instance.name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; font-weight: bold;">Company:</td>
                    <td style="padding: 10px;">{instance.company_name}</td>
                </tr>
                <tr style="background-color: #f9f9f9;">
                    <td style="padding: 10px; font-weight: bold;">Services:</td>
                    <td style="padding: 10px;">{instance.services}</td>
                </tr>
            </table>
            
            <div style="text-align: center; margin-top: 20px;">
                <a href="http://127.0.0.1:8000/admin/crm/client/{instance.id}/change/" style="background-color: #15173D; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">View in Admin</a>
            </div>
            <p style="text-align: center; color: #999; font-size: 12px; margin-top: 30px;">This is an automated notification from Techvilo CRM.</p>
        </div>
        """
        
        send_staff_notification(subject, message, html_message=html_message)

@receiver(post_save, sender=Project)
def notify_new_project(sender, instance, created, **kwargs):
    if created:
        subject = f"🔨 New Project Started: {instance.project_name}"
        
        message = f"""
        New Project Created:
        Project: {instance.project_name}
        Client: {instance.client.name}
        Status: {instance.get_status_display()}
        
        View in Admin: http://127.0.0.1:8000/admin/crm/project/{instance.id}/change/
        """
        
        html_message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <h2 style="color: #982598; text-align: center;">Techvilo CRM</h2>
            <hr style="border: 0; border-top: 1px solid #eee;">
            <h3 style="color: #333;">🔨 New Project Started!</h3>
            <p style="color: #555;">A new project has been initiated.</p>
            
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr style="background-color: #f9f9f9;">
                    <td style="padding: 10px; font-weight: bold; width: 30%;">Project:</td>
                    <td style="padding: 10px;">{instance.project_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; font-weight: bold;">Client:</td>
                    <td style="padding: 10px;">{instance.client.name}</td>
                </tr>
                <tr style="background-color: #f9f9f9;">
                    <td style="padding: 10px; font-weight: bold;">Status:</td>
                    <td style="padding: 10px;">{instance.get_status_display()}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; font-weight: bold;">Deadline:</td>
                    <td style="padding: 10px;">{instance.deadline or 'N/A'}</td>
                </tr>
            </table>
            
            <div style="text-align: center; margin-top: 20px;">
                <a href="http://127.0.0.1:8000/admin/crm/project/{instance.id}/change/" style="background-color: #15173D; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">View in Admin</a>
            </div>
            <p style="text-align: center; color: #999; font-size: 12px; margin-top: 30px;">This is an automated notification from Techvilo CRM.</p>
        </div>
        """
        
        send_staff_notification(subject, message, html_message=html_message)
