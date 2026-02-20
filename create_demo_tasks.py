import os
import django
import datetime
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from crm.models import Project, Task, Client

def create_demo_data():
    # Ensure there's at least one client and project
    client, _ = Client.objects.get_or_create(
        name="TechVilo Demo", 
        company_name="TechVilo", 
        services="Internal"
    )
    
    project, _ = Project.objects.get_or_create(
        client=client,
        project_name="CRM Development v2",
        status="IN_PROGRESS",
    )
    
    tasks = [
        {"name": "Design Database Schema", "status": "DONE"},
        {"name": "Setup Django Project", "status": "DONE"},
        {"name": "Implement Lead Management", "status": "DONE"},
        {"name": "Create Interaction History", "status": "DONE"},
        {"name": "Build Dashboard UI", "status": "REVIEW"},
        {"name": "Expense Tracking Module", "status": "REVIEW"},
        {"name": "Kanban Board Drag & Drop", "status": "IN_PROGRESS"},
        {"name": "Email Notifications", "status": "TODO"},
        {"name": "Client Portal", "status": "TODO"},
        {"name": "Deploy to Production", "status": "TODO"},
    ]
    
    count = 0
    for t in tasks:
        # Check if task already exists to avoid duplicates
        if not Task.objects.filter(project=project, task_name=t["name"]).exists():
            Task.objects.create(
                project=project,
                task_name=t["name"],
                status=t["status"],
                due_date=timezone.now().date() + datetime.timedelta(days=7)
            )
            count += 1
            print(f"Created task: {t['name']} ({t['status']})")
    
    if count == 0:
        print("Demo tasks already exist.")
    else:
        print(f"\nSuccessfully created {count} demo tasks!")

if __name__ == '__main__':
    create_demo_data()
