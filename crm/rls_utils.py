from .models import Client, Project, Lead, Task, Transaction

def get_filtered_queryset(user, model_class):
    """
    Helper to filter data based on User Role.
    Manager/Superuser -> All Data
    Sales Agent -> Assigned Data Only
    """
    qs = model_class.objects.all()
    if user.is_superuser or user.groups.filter(name='Manager').exists():
        return qs
    
    # RLS Logic
    if model_class == Client:
        return qs.filter(assigned_to=user)
    elif model_class == Project:
        return qs.filter(client__assigned_to=user)
    elif model_class == Lead:
        return qs.filter(assigned_to=user)
    elif model_class == Task:
        return qs.filter(project__client__assigned_to=user)
    elif model_class == Transaction:
        # Transactions related to their projects OR clients
        return qs.filter(client__assigned_to=user) | qs.filter(project__client__assigned_to=user)
    
    return qs
