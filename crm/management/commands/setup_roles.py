from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from crm.models import Lead, Client, Project, Task, Interaction, Transaction

class Command(BaseCommand):
    help = 'Setup User Roles (Manager & Sales Agent)'

    def handle(self, *args, **kwargs):
        # 1. Create Groups
        manager_group, created = Group.objects.get_or_create(name='Manager')
        agent_group, created = Group.objects.get_or_create(name='Sales Agent')
        
        self.stdout.write(self.style.SUCCESS("Groups 'Manager' and 'Sales Agent' ensure created."))

        # 2. Assign Permissions to Sales Agent
        # They should convert Leads, Manage Clients, Projects, Tasks
        # BUT we only give them basic permissions here. RLS (Row Level Security) 
        # will handle "WHICH" data they see in admin.py
        
        models_to_grant = [Lead, Client, Project, Task, Interaction, Transaction]
        
        permissions = []
        for model in models_to_grant:
            content_type = ContentType.objects.get_for_model(model)
            # Fetch View, Add, Change permissions (Exclude Delete if we want strictness)
            perms = Permission.objects.filter(
                content_type=content_type,
                codename__in=[
                    f'view_{model._meta.model_name}',
                    f'add_{model._meta.model_name}',
                    f'change_{model._meta.model_name}',
                ]
            )
            permissions.extend(perms)

        agent_group.permissions.set(permissions)
        self.stdout.write(self.style.SUCCESS(f"Assigned {len(permissions)} permissions to 'Sales Agent' group."))

        # 3. Manager gets ALL permissions
        # (Simply granting is_staff + superuser status is easier for managers, 
        # but if we want strict group, we give all perms)
        all_perms = Permission.objects.all()
        manager_group.permissions.set(all_perms)
        self.stdout.write(self.style.SUCCESS("Assigned ALL permissions to 'Manager' group."))

        self.stdout.write(self.style.SUCCESS("Role setup completed successfully!"))
