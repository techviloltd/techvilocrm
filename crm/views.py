import os
import datetime
import json

from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Count
from xhtml2pdf import pisa
import pandas as pd

from .models import Lead, Client, Project, Task, Interaction, Transaction, KPITarget

# 1. Lead Import Logic
def import_leads(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        file = request.FILES['csv_file']
        
        try:
            df = pd.read_csv(file)
            for _, row in df.iterrows():
                Lead.objects.create(
                    source=row['source'],
                    contact_info=row['contact'],
                    feedback_notes=row.get('notes', '')
                )
            messages.success(request, "Leads imported successfully!")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            
        return redirect('..')
    
    return render(request, 'admin/csv_upload.html')


# 2. Invoice Generation Logic
# 2. Invoice Generation Logic
def generate_invoice_pdf(request, client_id):
    client = Client.objects.get(id=client_id)
    # Fetch related projects (deadlines, etc)
    projects = Project.objects.filter(client=client)
    # Fetch recent payments
    payments = Transaction.objects.filter(client=client, transaction_type='INCOME').order_by('-date')[:10]

    today = datetime.date.today()
    invoice_no = f"INV-{today.strftime('%Y%m%d')}-{client.id}"

    # Logo path (Absolute path for xhtml2pdf)
    logo_path = os.path.join(settings.BASE_DIR, 'crm/static/logo.jpg').replace('\\', '/')

    context = {
        'client': client,
        'projects': projects,
        'payments': payments,
        'invoice_no': invoice_no,
        'date': today.strftime('%b %d, %Y'),
        'due_amount': client.due_amount,
        'logo': logo_path,
    }

    # Load template
    template = get_template('invoice.html') # Updated path
    html = template.render(context)

    # Create PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'filename="Invoice_{client.name}_{invoice_no}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse(f'We had some errors <pre>{html}</pre>')
    return response

from .rls_utils import get_filtered_queryset

# 3. Dashboard View
@login_required
def dashboard(request):
    # KPIs
    total_leads = get_filtered_queryset(request.user, Lead).count()
    total_clients = get_filtered_queryset(request.user, Client).count()
    active_projects = get_filtered_queryset(request.user, Project).filter(status='IN_PROGRESS').count()
    
    # Financials (Filtered)
    tx_qs = get_filtered_queryset(request.user, Transaction)
    
    total_income = tx_qs.filter(transaction_type='INCOME').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = tx_qs.filter(transaction_type='EXPENSE').aggregate(Sum('amount'))['amount__sum'] or 0
    net_profit = total_income - total_expense
    
    # Recent Activity (last 5 interactions for their leads/clients)
    # Interaction doesn't have RLS helper yet, let's filter manually or add to helper. 
    # For now, simplistic approach:
    if request.user.is_superuser or request.user.groups.filter(name='Manager').exists():
        recent_interactions = Interaction.objects.select_related('client', 'lead', 'created_by').order_by('-created_at')[:5]
    else:
        recent_interactions = Interaction.objects.filter(
            client__assigned_to=request.user
        ).select_related('client', 'lead', 'created_by').order_by('-created_at')[:5]

    
    # Upcoming Deadlines (Projects & Tasks due within 7 days)
    today = timezone.now().date()
    next_week = today + datetime.timedelta(days=7)
    
    upcoming_projects = get_filtered_queryset(request.user, Project).filter(deadline__range=[today, next_week]).order_by('deadline')
    
    # Personal filtering for Tasks
    task_qs = get_filtered_queryset(request.user, Task)
    if not (request.user.is_superuser or request.user.groups.filter(name='Manager').exists()):
        task_qs = task_qs.filter(assigned_to=request.user)

    upcoming_tasks = task_qs.filter(due_date__range=[today, next_week], is_completed=False).order_by('due_date')
    overdue_tasks = task_qs.filter(due_date__lt=today, is_completed=False).order_by('due_date')
    overdue_count = overdue_tasks.count()

    # Chart Data Preparation (using RLS)
    lead_qs = get_filtered_queryset(request.user, Lead)
    lead_status_data = list(lead_qs.values('status').annotate(count=Count('status')))
    
    # 1. Lead Status (Doughnut)
    lead_counts = {item['status']: item['count'] for item in lead_status_data}
    lead_dataset = [
        lead_counts.get('COLD', 0),
        lead_counts.get('WARM', 0),
        lead_counts.get('HOT', 0),
        lead_counts.get('CONVERTED', 0)
    ]

    # 2. Income vs Expense (Bar) - totals
    income_expense_dataset = [float(total_income), float(total_expense)]

    # 3. Sales Trend (Last 7 Days) - Line Chart
    trend_labels = []
    trend_data = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        trend_labels.append(day.strftime('%a')) # Mon, Tue...
        
        # Filter transactions for this day
        day_income = tx_qs.filter(
            transaction_type='INCOME',
            date=day
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        trend_data.append(float(day_income))

    # 4. Monthly Income vs Expense (last 6 months) — correct calendar month arithmetic
    import calendar as _cal
    monthly_labels = []
    monthly_income = []
    monthly_expense = []
    for i in range(5, -1, -1):
        # Go back i months correctly
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1

        month_start = datetime.date(year, month, 1)
        last_day = _cal.monthrange(year, month)[1]
        # For current month use today as end, else use last day of month
        month_end = today if i == 0 else datetime.date(year, month, last_day)

        inc = tx_qs.filter(
            transaction_type='INCOME',
            date__gte=month_start,
            date__lte=month_end
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        exp = tx_qs.filter(
            transaction_type='EXPENSE',
            date__gte=month_start,
            date__lte=month_end
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        monthly_labels.append(month_start.strftime("%b %y"))  # e.g. Sep 25
        monthly_income.append(float(inc))
        monthly_expense.append(float(exp))


    # 5. KPI Widget — current month's targets for this user (or all staff if manager)
    kpi_today = today
    is_manager = request.user.is_superuser or request.user.groups.filter(name='Manager').exists()

    if is_manager:
        kpi_targets_qs = KPITarget.objects.filter(
            month__year=kpi_today.year,
            month__month=kpi_today.month
        ).select_related('staff')
    else:
        kpi_targets_qs = KPITarget.objects.filter(
            staff=request.user,
            month__year=kpi_today.year,
            month__month=kpi_today.month
        ).select_related('staff')

    kpi_widget_data = []
    for kpi in kpi_targets_qs:
        kpi_widget_data.append({
            'username': kpi.staff.get_full_name() or kpi.staff.username,
            'overall_pct': kpi.overall_pct(),
            'metrics': [
                {'label': '📞 Leads', 'actual': kpi.actual_leads(), 'target': kpi.target_leads, 'pct': kpi.leads_pct()},
                {'label': '✅ Tasks', 'actual': kpi.actual_tasks(), 'target': kpi.target_tasks, 'pct': kpi.tasks_pct()},
                {'label': '💬 Comms',  'actual': kpi.actual_interactions(), 'target': kpi.target_interactions, 'pct': kpi.interactions_pct()},
                {'label': '💰 Revenue','actual': int(kpi.actual_revenue()), 'target': int(kpi.target_revenue), 'pct': kpi.revenue_pct()},
            ]
        })

    context = {
        'total_leads': total_leads,
        'total_clients': total_clients,
        'active_projects': active_projects,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'recent_interactions': recent_interactions,
        'upcoming_projects': upcoming_projects,
        'upcoming_tasks': upcoming_tasks,
        'overdue_tasks': overdue_tasks,
        'overdue_count': overdue_count,
        'is_manager': is_manager,
        'kpi_widget_data': kpi_widget_data,
        'kpi_month': kpi_today.strftime('%B %Y'),

        # Chart Data
        'lead_dataset': json.dumps(lead_dataset),
        'income_expense_dataset': json.dumps(income_expense_dataset),
        'trend_labels': json.dumps(trend_labels),
        'trend_data': json.dumps(trend_data),
        'monthly_labels': json.dumps(monthly_labels),
        'monthly_income': json.dumps(monthly_income),
        'monthly_expense': json.dumps(monthly_expense),
    }
    return render(request, 'admin/dashboard.html', context)

# 4. Kanban Board
@login_required
def kanban_board(request):
    board_type = request.GET.get('type', 'projects') # Default to projects
    
    if board_type == 'tasks':
        items = get_filtered_queryset(request.user, Task).select_related('project', 'assigned_to')
        # Kanban statuses for Tasks
        kanban_data = {
            'TODO': items.filter(status='TODO'),
            'IN_PROGRESS': items.filter(status='IN_PROGRESS'),
            'REVIEW': items.filter(status='REVIEW'),
            'DONE': items.filter(status='DONE'),
        }
    else:
        # Projects
        items = get_filtered_queryset(request.user, Project).select_related('client')
        # Kanban statuses for Projects (using Project.STATUS_CHOICES)
        kanban_data = {
            'PLANNING': items.filter(status='PLANNING'),
            'IN_PROGRESS': items.filter(status='IN_PROGRESS'),
            'REVIEW': items.filter(status='REVIEW'),
            'COMPLETED': items.filter(status='COMPLETED'),
        }
    
    projects = get_filtered_queryset(request.user, Project).only('id', 'project_name')
    today = timezone.now().date()
    
    return render(request, 'admin/kanban_board.html', {
        'kanban_data': kanban_data,
        'board_type': board_type,
        'projects': projects,
        'today': today
    })

@csrf_exempt
@login_required
def update_kanban_item(request, item_type, item_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            
            if item_type == 'task':
                item = Task.objects.get(id=item_id)
                item.status = new_status
                if new_status == 'DONE':
                    item.is_completed = True
                else:
                    item.is_completed = False
            else:
                # project
                item = Project.objects.get(id=item_id)
                item.status = new_status
                
            item.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@csrf_exempt
@login_required
def quick_add_task(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            task_name = data.get('task_name')
            project_id = data.get('project_id')
            status = data.get('status', 'TODO')
            
            if not task_name or not project_id:
                return JsonResponse({'success': False, 'error': 'Missing task name or project'})
            
            project = Project.objects.get(id=project_id)
            task = Task.objects.create(
                task_name=task_name,
                project=project,
                status=status,
                assigned_to=request.user
            )
            
            return JsonResponse({
                'success': True,
                'task_id': task.id,
                'task_name': task.task_name,
                'project_name': project.project_name,
                'assigned_to': task.assigned_to.username if task.assigned_to else "Unassigned"
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

# --- CALENDAR VIEW ---
@login_required
def calendar_view(request):
    return render(request, 'admin/calendar.html')

@login_required
def calendar_events_api(request):
    events = []

    # 1. Lead Follow-ups
    leads = get_filtered_queryset(request.user, Lead).filter(next_follow_up__isnull=False)
    for lead in leads:
        events.append({
            'title': f"📞 {lead.source} ({lead.get_status_display()})",
            'start': lead.next_follow_up.isoformat(),
            'color': '#007bff', # Blue
            'url': f'/admin/crm/lead/{lead.id}/change/'
        })

    # 2. Project Deadlines
    projects = get_filtered_queryset(request.user, Project).filter(deadline__isnull=False)
    for project in projects:
        events.append({
            'title': f"🚀 {project.project_name}",
            'start': project.deadline.isoformat(),
            'color': '#dc3545', # Red
            'url': f'/admin/crm/project/{project.id}/change/'
        })

    # 3. Task Due Dates
    tasks = get_filtered_queryset(request.user, Task).filter(due_date__isnull=False)
    for task in tasks:
        events.append({
            'title': f"✅ {task.task_name}",
            'start': task.due_date.isoformat(),
            'color': '#28a745', # Green
            'url': f'/admin/crm/project/{task.project.id}/change/' # Redirect to project for now
        })

    return JsonResponse(events, safe=False)