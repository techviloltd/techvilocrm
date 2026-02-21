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
    import time
    start_time = time.time()
    def log_time(label):
        print(f"DEBUG: {label} took {time.time() - start_time:.4f}s")

    # 1. Base counts
    total_leads = get_filtered_queryset(request.user, Lead).count()
    total_clients = get_filtered_queryset(request.user, Client).count()
    active_projects = get_filtered_queryset(request.user, Project).filter(status='IN_PROGRESS').count()
    log_time("Base counts")
    
    # 2. Financials & Recent Activity
    tx_qs = get_filtered_queryset(request.user, Transaction)
    tx_totals = tx_qs.values('transaction_type').annotate(total=Sum('amount'))
    total_income = 0
    total_expense = 0
    for item in tx_totals:
        if item['transaction_type'] == 'INCOME': total_income = item['total'] or 0
        if item['transaction_type'] == 'EXPENSE': total_expense = item['total'] or 0
    net_profit = total_income - total_expense
    log_time("Financials")
    
    if request.user.is_superuser or request.user.groups.filter(name='Manager').exists():
        recent_interactions = Interaction.objects.select_related('client', 'lead', 'created_by').order_by('-created_at')[:5]
    else:
        recent_interactions = Interaction.objects.filter(
            client__assigned_to=request.user
        ).select_related('client', 'lead', 'created_by').order_by('-created_at')[:5]
    log_time("Interactions")

    # 3. Deadlines
    today = timezone.now().date()
    next_week = today + datetime.timedelta(days=7)
    upcoming_projects = get_filtered_queryset(request.user, Project).filter(deadline__range=[today, next_week]).order_by('deadline')
    
    task_qs = get_filtered_queryset(request.user, Task)
    if not (request.user.is_superuser or request.user.groups.filter(name='Manager').exists()):
        task_qs = task_qs.filter(assigned_to=request.user)

    upcoming_tasks = task_qs.filter(due_date__range=[today, next_week], is_completed=False).order_by('due_date')
    overdue_tasks = task_qs.filter(due_date__lt=today, is_completed=False).order_by('due_date')
    overdue_count = overdue_tasks.count()
    log_time("Deadlines")

    # 4. Chart Data Preparation (Bulk)
    # Lead Status
    lead_qs = get_filtered_queryset(request.user, Lead)
    lead_status_data = lead_qs.values('status').annotate(count=Count('id'))
    lead_counts = {item['status']: item['count'] for item in lead_status_data}
    lead_dataset = [lead_counts.get('COLD', 0), lead_counts.get('WARM', 0), lead_counts.get('HOT', 0), lead_counts.get('CONVERTED', 0)]

    # Sales Trend (Last 7 Days)
    trend_labels = []
    trend_data_map = { (today - datetime.timedelta(days=i)): 0 for i in range(7) }
    trend_qs = tx_qs.filter(transaction_type='INCOME', date__gte=today - datetime.timedelta(days=6)).values('date').annotate(total=Sum('amount'))
    for item in trend_qs:
        if item['date'] in trend_data_map:
            trend_data_map[item['date']] = float(item['total'] or 0)
    
    trend_data = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        trend_labels.append(day.strftime('%a'))
        trend_data.append(trend_data_map[day])
    log_time("Charts Part 1")

    # Monthly Progress (Last 6 Months)
    import calendar as _cal
    monthly_labels, monthly_income, monthly_expense = [], [], []
    for i in range(5, -1, -1):
        month = today.month - i
        year = today.year
        while month <= 0: month += 12; year -= 1
        m_start = datetime.date(year, month, 1)
        m_end = datetime.date(year, month, _cal.monthrange(year, month)[1])
        if i == 0: m_end = today
        
        m_tx = tx_qs.filter(date__gte=m_start, date__lte=m_end).values('transaction_type').annotate(total=Sum('amount'))
        inc, exp = 0, 0
        for item in m_tx:
            if item['transaction_type'] == 'INCOME': inc = item['total'] or 0
            if item['transaction_type'] == 'EXPENSE': exp = item['total'] or 0
        
        monthly_labels.append(m_start.strftime("%b %y"))
        monthly_income.append(float(inc))
        monthly_expense.append(float(exp))
    log_time("Charts Part 2")

    # 5. KPI Data (Optimized)
    is_manager = request.user.is_superuser or request.user.groups.filter(name='Manager').exists()
    kpi_month_start = today.replace(day=1)
    kpi_month_end = today.replace(day=_cal.monthrange(today.year, today.month)[1])
    
    kpi_targets = KPITarget.objects.filter(month=kpi_month_start)
    if not is_manager:
        kpi_targets = kpi_targets.filter(staff=request.user)
    kpi_targets = kpi_targets.select_related('staff')

    # Prep actuals in bulk for the month
    staff_ids = [k.staff_id for k in kpi_targets]
    
    # Actuals mapping (Using RANGE queries instead of slow __month/__year)
    m_start = today.replace(day=1)
    m_end_plus = (m_start + datetime.timedelta(days=32)).replace(day=1)

    def get_actuals_map(model, date_field, user_field, is_count=True):
        filters = { f"{date_field}__gte": m_start, f"{date_field}__lt": m_end_plus, f"{user_field}__in": staff_ids }
        if model == Lead: filters['status'] = 'CONVERTED'
        if model == Task: filters['is_completed'] = True
        if model == Transaction: filters['transaction_type'] = 'INCOME'
        
        qs = model.objects.filter(**filters).values(user_field)
        if is_count: res = qs.annotate(val=Count('id'))
        else: res = qs.annotate(val=Sum('amount'))
        return { item[user_field]: item['val'] for item in res }

    leads_map = get_actuals_map(Lead, 'converted_at', 'assigned_to')
    tasks_map = get_actuals_map(Task, 'due_date', 'assigned_to')
    interactions_map = get_actuals_map(Interaction, 'created_at', 'created_by')
    revenue_map = get_actuals_map(Transaction, 'date', 'created_by', is_count=False)
    log_time("KPI Maps")

    kpi_widget_data = []
    for kpi in kpi_targets:
        uid = kpi.staff_id
        act_l, act_t, act_i, act_r = leads_map.get(uid, 0), tasks_map.get(uid, 0), interactions_map.get(uid, 0), float(revenue_map.get(uid, 0))
        
        def calc_pct(a, t): 
            if not t: return 100 if a else 0
            return min(int((a / float(t)) * 100), 100)
        
        m_leads = {'label': '📞 Leads', 'actual': act_l, 'target': kpi.target_leads, 'pct': calc_pct(act_l, kpi.target_leads)}
        m_tasks = {'label': '✅ Tasks', 'actual': act_t, 'target': kpi.target_tasks, 'pct': calc_pct(act_t, kpi.target_tasks)}
        m_comms = {'label': '💬 Comms', 'actual': act_i, 'target': kpi.target_interactions, 'pct': calc_pct(act_i, kpi.target_interactions)}
        m_rev   = {'label': '💰 Revenue', 'actual': int(act_r), 'target': int(kpi.target_revenue), 'pct': calc_pct(act_r, kpi.target_revenue)}
        
        overall = int((m_leads['pct'] + m_tasks['pct'] + m_comms['pct'] + m_rev['pct']) / 4)
        
        kpi_widget_data.append({
            'username': kpi.staff.get_full_name() or kpi.staff.username,
            'overall_pct': overall,
            'metrics': [m_leads, m_tasks, m_comms, m_rev]
        })
    log_time("KPI Loop")

    context = {
        'total_leads': total_leads, 'total_clients': total_clients, 'active_projects': active_projects,
        'total_income': total_income, 'total_expense': total_expense, 'net_profit': net_profit,
        'recent_interactions': recent_interactions, 'upcoming_projects': upcoming_projects,
        'upcoming_tasks': upcoming_tasks, 'overdue_tasks': overdue_tasks, 'overdue_count': overdue_count,
        'is_manager': is_manager, 'kpi_widget_data': kpi_widget_data, 'kpi_month': today.strftime('%B %Y'),
        'lead_dataset': json.dumps(lead_dataset), 'income_expense_dataset': json.dumps([float(total_income), float(total_expense)]),
        'trend_labels': json.dumps(trend_labels), 'trend_data': json.dumps(trend_data),
        'monthly_labels': json.dumps(monthly_labels), 'monthly_income': json.dumps(monthly_income), 'monthly_expense': json.dumps(monthly_expense),
    }
    log_time("Final Context")
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


def health_check(request):
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = "Green"
    except Exception as e:
        db_ok = f"Red (Error: {str(e)})"
    
    return HttpResponse(f"Server Status: OK\nDatabase Status: {db_ok}", content_type="text/plain")