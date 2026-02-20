"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""
# from django.contrib import admin
# from django.urls import path
# from crm.views import generate_invoice_pdf  # Amader CRM views theke function-ta niye aslam

# urlpatterns = [
#     path('admin/', admin.site.urls),
    
#     # Invoice download korar jonno notun path
#     path('admin/invoice/<int:client_id>/', generate_invoice_pdf, name='generate_invoice'),
# ]



from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from crm.views import (
    generate_invoice_pdf, dashboard, kanban_board,
    update_kanban_item, calendar_view, calendar_events_api, quick_add_task,
    health_check
)

urlpatterns = [
    # Root Redirect
    path('', RedirectView.as_view(url='/dashboard/', permanent=True)),

    # Django Admin Panel
    path('admin/', admin.site.urls),

    # Custom Dashboard
    path('dashboard/', dashboard, name='dashboard'),

    # Calendar
    path('calendar/', calendar_view, name='calendar_view'),
    path('api/events/', calendar_events_api, name='calendar_events_api'),

    # Invoice Download
    path('invoice/<int:client_id>/', generate_invoice_pdf, name='generate_invoice_pdf'),

    # Kanban Board
    path('kanban/', kanban_board, name='kanban_board'),
    path('kanban/update/<str:item_type>/<int:item_id>/', update_kanban_item, name='update_kanban_item'),
    path('kanban/quick-add/', quick_add_task, name='quick_add_task'),
    path('health-check/', health_check, name='health_check'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)