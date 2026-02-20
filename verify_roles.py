import os
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User, Group
from crm.models import Client, Project, Task
from crm.rls_utils import get_filtered_queryset

def run_verification():
    print("--- Verifying User Roles & Permissions ---")
    
    # 1. Setup Data
    manager_group = Group.objects.get(name='Manager')
    agent_group = Group.objects.get(name='Sales Agent')
    
    # Create Users
    manager_user, _ = User.objects.get_or_create(username='test_manager')
    manager_user.groups.add(manager_group)
    
    agent_user, _ = User.objects.get_or_create(username='test_agent')
    agent_user.groups.clear() # Ensure clean slate
    agent_user.groups.add(agent_group)
    
    # Create Data
    client_for_agent, _ = Client.objects.get_or_create(name="Client for Agent", company_name="Agent Co", services="WEB")
    client_for_agent.assigned_to.add(agent_user)
    
    client_for_other, _ = Client.objects.get_or_create(name="Client for Other", company_name="Other Co", services="SEO")
    client_for_other.assigned_to.clear() # Not assigned to agent
    
    print("Data Setup Complete.")
    
    # 2. Test Agent Access (Should only see their client)
    qs_agent = get_filtered_queryset(agent_user, Client)
    print(f"Agent sees {qs_agent.count()} clients.")
    
    if qs_agent.count() == 1 and qs_agent.first() == client_for_agent:
        print("✅ SUCCESS: Agent sees only assigned client.")
    else:
        print(f"❌ FAILURE: Agent sees incorrect data. Found: {[c.name for c in qs_agent]}")

    # 3. Test Manager Access (Should see ALL)
    qs_manager = get_filtered_queryset(manager_user, Client)
    print(f"Manager sees {qs_manager.count()} clients.")
    
    if qs_manager.count() >= 2: # At least these 2
        print("✅ SUCCESS: Manager sees all clients.")
    else:
        print("❌ FAILURE: Manager does not see all clients.")

    # 4. Test Project Access (via Client assignment)
    project_agent, _ = Project.objects.get_or_create(project_name="Agent Project", client=client_for_agent)
    project_other, _ = Project.objects.get_or_create(project_name="Other Project", client=client_for_other)
    
    qs_proj_agent = get_filtered_queryset(agent_user, Project)
    if qs_proj_agent.count() == 1 and qs_proj_agent.first() == project_agent:
        print("✅ SUCCESS: Agent sees only assigned project.")
    else:
         print(f"❌ FAILURE: Agent sees incorrect projects. Found: {[p.project_name for p in qs_proj_agent]}")

    print("--- Verification Finished ---")

if __name__ == '__main__':
    run_verification()
