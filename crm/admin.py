
from django.contrib import admin
from django.urls import path
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.utils.html import format_html, mark_safe
from django.utils import timezone
from .models import Client, Lead, Project, Task, TaskChecklist, Interaction, Transaction, Document, KPITarget
from django.contrib.auth.models import User
from django.utils.timezone import now
import datetime
from .views import import_leads
from django.shortcuts import redirect as _redirect

# Redirect /admin/ index to /dashboard/
def _admin_index(request, extra_context=None):
    return _redirect('/dashboard/')

admin.site.index = _admin_index

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'transaction_type', 'amount', 'client', 'project', 'created_by')
    list_filter = ('transaction_type', 'date', 'client')
    search_fields = ('description', 'client__name', 'project__project_name')
    date_hierarchy = 'date'

    change_list_template = "admin/transaction_changelist.html"

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)

        try:
            qs = response.context_data['cl'].queryset
        except (AttributeError, KeyError):
            return response

        from django.db.models import Sum, Q
        metrics = qs.aggregate(
            total_income=Sum('amount', filter=Q(transaction_type='INCOME')),
            total_expense=Sum('amount', filter=Q(transaction_type='EXPENSE'))
        )
        metrics['total_income'] = metrics['total_income'] or 0
        metrics['total_expense'] = metrics['total_expense'] or 0
        metrics['net_profit'] = metrics['total_income'] - metrics['total_expense']

        response.context_data['summary'] = metrics
        return response

class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 1
    fields = ('date', 'transaction_type', 'amount', 'description', 'created_by')
    readonly_fields = ('created_at',)
    
    def get_changeform_initial_data(self, request):
        return {'created_by': request.user}

class ProjectInline(admin.TabularInline):
    model = Project
    extra = 1
    fields = ('project_name', 'status', 'deadline', 'progress_percentage')
    show_change_link = True

# --- INTERACTION INLINE ---
class InteractionInline(admin.TabularInline):
    model = Interaction
    extra = 1
    readonly_fields = ('created_at',)
    fields = ('interaction_type', 'notes', 'created_by', 'created_at')

    def get_changeform_initial_data(self, request):
        return {'created_by': request.user}

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'client', 'file_preview_modern', 'uploaded_at', 'download_link_modern')
    list_filter = ('uploaded_at', 'project', 'client')
    search_fields = ('title', 'project__project_name', 'client__name')
    readonly_fields = ('file_preview_modern',)

    @admin.display(description="Preview")
    def file_preview_modern(self, obj):
        try:
            if not obj.file or not obj.file.url:
                raise ValueError
        except (ValueError, AttributeError):
            return mark_safe('<div class="doc-preview-wrapper"><div class="doc-icon-box"><i class="fas fa-file"></i><span>No File</span></div></div>')
        
        file_ext = obj.file.name.split('.')[-1].lower()
        
        if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            return format_html(
                '<div class="doc-preview-wrapper"><img src="{}" class="doc-thumb" /></div>',
                obj.file.url
            )
        
        icons = {
            'pdf': ('fa-file-pdf', 'PDF'),
            'mp4': ('fa-file-video', 'Video'),
            'webm': ('fa-file-video', 'Video'),
            'mov': ('fa-file-video', 'Video'),
            'doc': ('fa-file-word', 'Word'),
            'docx': ('fa-file-word', 'Word'),
            'xls': ('fa-file-excel', 'Excel'),
            'xlsx': ('fa-file-excel', 'Excel'),
            'zip': ('fa-file-archive', 'Archive'),
        }
        
        icon, label = icons.get(file_ext, ('fa-file', 'File'))
        return format_html(
            '<div class="doc-preview-wrapper"><div class="doc-icon-box"><i class="fas {}"></i><span>{}</span></div></div>',
            icon, label
        )

    @admin.display(description="Action")
    def download_link_modern(self, obj):
        try:
            if not obj.file or not obj.file.url:
                raise ValueError
            return format_html(
                '<a href="{}" download class="btn-modern-dl"><i class="fas fa-download"></i> Download</a>',
                obj.file.url
            )
        except (ValueError, AttributeError):
            return "-"

class DocumentInline(admin.TabularInline):
    model = Document
    extra = 1
    fields = ('title', 'file', 'file_preview_modern', 'uploaded_by')
    readonly_fields = ('file_preview_modern',)

    @admin.display(description="Preview")
    def file_preview_modern(self, obj):
        try:
            if not obj.file or not obj.file.url:
                raise ValueError
            
            file_ext = obj.file.name.split('.')[-1].lower()
            if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                content = format_html('<img src="{}" class="doc-thumb" />', obj.file.url)
            else:
                content = format_html('<div class="doc-icon-box"><i class="fas fa-file"></i><span>{}</span></div>', file_ext.upper())
            
            return format_html('<div class="doc-preview-wrapper">{}</div>', content)
        except (ValueError, AttributeError):
            return mark_safe('<span style="color: #64748b; font-size: 11px; font-weight: 700;">Save to see preview</span>')

# --- CLIENT ADMIN: Financials & Revenue Chart ---
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'company_name', 'get_active_projects_count', 'total_payable', 'paid_amount', 'due_amount', 'get_assigned_staff', 'download_invoice')
    search_fields = ('name', 'company_name')
    readonly_fields = ('paid_amount',) 
    filter_horizontal = ('assigned_to',)
    change_list_template = "admin/client_changelist.html"
    inlines = [InteractionInline, ProjectInline, TransactionInline, DocumentInline] # Added Projects

    @admin.display(description="Invoice")
    def download_invoice(self, obj):
        return format_html('<a class="button" href="/invoice/{}/" target="_blank" style="background-color: #447e9b; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">Download Invoice</a>', obj.id)

    @admin.display(description="Assigned Staff")
    def get_assigned_staff(self, obj):
        return ", ".join([user.username for user in obj.assigned_to.all()])

    @admin.display(description="Active Projects")
    def get_active_projects_count(self, obj):
        count = getattr(obj, 'active_projects_count_annotated', 0)
        if count > 0:
            return format_html('<span style="background-color: #3b82f6; color: white; padding: 2px 8px; border-radius: 12px; font-weight: bold;">{}</span>', count)
        return mark_safe('<span style="color: #94a3b8;">0</span>')

    def changelist_view(self, request, extra_context=None):
        import time
        from django.core.cache import cache
        start = time.time()
        
        # Simple aggregated metrics (Cached for 15 min)
        cache_key = "admin_client_metrics_simple"
        metrics = cache.get(cache_key)
        
        if not metrics:
            from django.db.models import Q
            stats = Client.objects.aggregate(
                payable=Sum('total_payable'),
                paid=Sum('paid_amount')
            )
            total_payable = stats['payable'] or 0
            total_paid = stats['paid'] or 0
            
            metrics = {
                'total_revenue': total_payable,
                'total_received': total_paid,
                'total_due': total_payable - total_paid,
            }
            cache.set(cache_key, metrics, 900)
        
        extra_context = extra_context or {}
        extra_context.update(metrics)
        # Chart data removed from list page to prevent timeouts
        extra_context['chart_labels'] = []
        extra_context['chart_data'] = []

        print(f"DEBUG: Client changelist view metrics took {time.time() - start:.4f}s")
        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        from django.db.models import Count, Q
        qs = super().get_queryset(request).prefetch_related('assigned_to')
        # Annotate active projects count to avoid N+1 queries in list display
        qs = qs.annotate(
            active_projects_count_annotated=Count('projects', filter=~Q(projects__status='COMPLETED'))
        )
        
        if request.user.is_superuser or request.user.groups.filter(name='Manager').exists():
            return qs 
        return qs.filter(assigned_to=request.user).distinct()

    def save_model(self, request, obj, form, change):
        import time
        start = time.time()
        super().save_model(request, obj, form, change)
        if not change and not obj.assigned_to.exists():
            obj.assigned_to.add(request.user)
        print(f"DEBUG: Client save_model took {time.time() - start:.4f}s")

# --- LEAD ADMIN: Conversion & Performance Chart ---
@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'source', 'colored_status', 'next_follow_up', 'assigned_to', 'created_at')
    list_filter = ('status', 'assigned_to', 'next_follow_up')
    search_fields = ('name', 'company_name', 'source', 'contact_info')
    change_list_template = "admin/lead_changelist.html"
    actions = ['convert_to_client']
    inlines = [InteractionInline, DocumentInline] # Interaction + Documents

    @admin.action(description='Convert selected leads to Clients')
    def convert_to_client(self, request, queryset):
        converted_count = 0
        for lead in queryset:
            if lead.status == 'CONVERTED':
                continue
            
            self.process_conversion(lead)
            converted_count += 1
            
        self.message_user(request, f"{converted_count} leads successfully converted to Clients.")

    def process_conversion(self, lead):
        # Create Client from Lead
        client = Client.objects.create(
            name=lead.name or lead.source,
            company_name=lead.company_name or lead.name or lead.source,
            services='Consulting', # Default service
            created_at=timezone.now()
        )
        
        # Transfer Assigned Staff (Lead has only one, Client has ManyToMany)
        if lead.assigned_to:
            client.assigned_to.add(lead.assigned_to)
        
        # Link Interaction history to Client
        lead.interactions.all().update(client=client)
        
        # Transfer Documents to Client
        lead.documents.all().update(client=client, lead=None)
        
        # Update Lead status and record exact conversion timestamp
        lead.status = 'CONVERTED'
        lead.converted_at = timezone.now()
        lead.save()

    def save_model(self, request, obj, form, change):
        if change:
            old_obj = Lead.objects.get(pk=obj.pk)
            # If status changed to CONVERTED, trigger conversion
            if old_obj.status != 'CONVERTED' and obj.status == 'CONVERTED':
                # Record the conversion timestamp before processing
                obj.converted_at = timezone.now()
                # We save first to ensure we have the latest data
                super().save_model(request, obj, form, change)
                self.process_conversion(obj)
                return
        
        super().save_model(request, obj, form, change)

    @admin.display(description="Status")
    def colored_status(self, obj):
        colors = {'HOT': '#d9534f', 'WARM': '#f0ad4e', 'COLD': '#5bc0de', 'CONVERTED': '#5cb85c'}
        return format_html('<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{}</span>', colors.get(obj.status, '#777'), obj.get_status_display())

    def changelist_view(self, request, extra_context=None):
        today = timezone.now().date()
        follow_up_count = Lead.objects.filter(next_follow_up=today).count()
        
        total_leads = Lead.objects.count()
        converted_leads = Lead.objects.filter(status='CONVERTED').count()
        conversion_rate = round((converted_leads / total_leads * 100), 2) if total_leads > 0 else 0

        staff_performance = (
            Lead.objects.filter(status='CONVERTED')
            .values('assigned_to__username')
            .annotate(total=Count('id'))
            .order_by('-total')[:3]
        )

        revenue_data = (
            Client.objects.annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(total=Sum('total_payable'))
            .order_by('month')
        )
        chart_labels = [entry['month'].strftime('%b %Y') for entry in revenue_data]
        chart_data = [float(entry['total']) for entry in revenue_data]

        extra_context = extra_context or {}
        extra_context['today_follow_ups'] = follow_up_count
        extra_context['conversion_rate'] = conversion_rate
        extra_context['total_leads'] = total_leads
        extra_context['converted_leads'] = converted_leads
        extra_context['staff_performance'] = staff_performance
        extra_context['chart_labels'] = chart_labels
        extra_context['chart_data'] = chart_data
        
        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('assigned_to')
        if request.user.is_superuser or request.user.groups.filter(name='Manager').exists():
            return qs
        return qs.filter(assigned_to=request.user)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.admin_site.admin_view(import_leads), name='import_leads'),
        ]
        return custom_urls + urls

# --- TASK INLINE logic ---
class TaskInline(admin.TabularInline):
    model = Task
    extra = 1 
    fields = ('task_name', 'assigned_to', 'priority', 'status', 'due_date')

# --- PROJECT ADMIN: Progress Tracking with Inline Tasks ---
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('project_name', 'client', 'colored_progress', 'status', 'deadline')
    list_filter = ('status', 'client')
    search_fields = ('project_name', 'client__name')
    # NOTUN: Eita add korle Project-er bhetorei Task list dekhabe
    inlines = [TaskInline, DocumentInline] 

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.groups.filter(name='Manager').exists():
            return qs
        return qs.filter(client__assigned_to=request.user).distinct()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "client":
            if not (request.user.is_superuser or request.user.groups.filter(name='Manager').exists()):
                kwargs["queryset"] = Client.objects.filter(assigned_to=request.user).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs) 

    @admin.display(description="Progress")
    def colored_progress(self, obj):
        color = "#28a745" if obj.progress_percentage > 70 else "#ffc107"
        if obj.progress_percentage < 30: color = "#dc3545"
        
        return format_html(
            '''
            <div style="width: 100px; background-color: #eee; border-radius: 5px;">
                <div style="width: {}px; background-color: {}; height: 10px; border-radius: 5px;"></div>
            </div>
            <span>{}%</span>
            ''',
            obj.progress_percentage, color, obj.progress_percentage
        )

class TaskChecklistInline(admin.TabularInline):
    model = TaskChecklist
    extra = 1

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('task_name', 'priority', 'project', 'assigned_to', 'status', 'due_date')
    list_filter = ('status', 'priority', 'assigned_to', 'due_date', 'project')
    search_fields = ('task_name', 'project__project_name')
    inlines = [TaskChecklistInline]


# ══════════════════════════════════════════════════════════
# KPI TARGET ADMIN
# ══════════════════════════════════════════════════════════
@admin.register(KPITarget)
class KPITargetAdmin(admin.ModelAdmin):
    change_list_template = 'admin/kpi_changelist.html'

    list_display = ('staff', 'month_display', 'leads_progress', 'tasks_progress',
                    'interactions_progress', 'revenue_progress', 'overall_badge')
    list_filter = ('month', 'staff')
    search_fields = ('staff__username',)
    autocomplete_fields = []

    fieldsets = (
        ('Staff & Month', {
            'fields': ('staff', 'month'),
            'description': 'Select the staff member and the 1st day of the target month.'
        }),
        ('Monthly Targets', {
            'fields': ('target_leads', 'target_tasks', 'target_interactions', 'target_revenue'),
        }),
        ('Notes', {'fields': ('notes',), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_by', 'created_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.groups.filter(name='Manager').exists():
            return qs
        return qs.filter(staff=request.user)

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.groups.filter(name='Manager').exists()

    def has_change_permission(self, request, obj=None):
        if obj and not (request.user.is_superuser or request.user.groups.filter(name='Manager').exists()):
            return False
        return True

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # ── Display helpers ───────────────────────────────────────────────
    @admin.display(description='Month')
    def month_display(self, obj):
        return obj.month.strftime('%B %Y')

    def _bar(self, pct):
        color = '#22c55e' if pct >= 80 else '#f59e0b' if pct >= 50 else '#ef4444'
        return format_html(
            '<div style="background:#f1f5f9;border-radius:4px;height:8px;width:100px;display:inline-block;vertical-align:middle;margin-right:6px;">'
            '<div style="background:{};height:8px;border-radius:4px;width:{}%;"></div></div>'
            '<span style="font-size:12px;font-weight:700;color:{};">{} %</span>',
            color, pct, color, pct
        )

    @admin.display(description='📞 Leads')
    def leads_progress(self, obj):
        return format_html('{} <small style="color:#94a3b8;">/ {}</small><br>{}',
            obj.actual_leads(), obj.target_leads, self._bar(obj.leads_pct()))

    @admin.display(description='✅ Tasks')
    def tasks_progress(self, obj):
        return format_html('{} <small style="color:#94a3b8;">/ {}</small><br>{}',
            obj.actual_tasks(), obj.target_tasks, self._bar(obj.tasks_pct()))

    @admin.display(description='💬 Interactions')
    def interactions_progress(self, obj):
        return format_html('{} <small style="color:#94a3b8;">/ {}</small><br>{}',
            obj.actual_interactions(), obj.target_interactions, self._bar(obj.interactions_pct()))

    @admin.display(description='💰 Revenue (৳)')
    def revenue_progress(self, obj):
        return format_html('৳{} <small style="color:#94a3b8;">/ ৳{}</small><br>{}',
            int(obj.actual_revenue()), int(obj.target_revenue), self._bar(obj.revenue_pct()))

    @admin.display(description='Overall')
    def overall_badge(self, obj):
        pct = obj.overall_pct()
        color = '#22c55e' if pct >= 80 else '#f59e0b' if pct >= 50 else '#ef4444'
        label = '🟢 On Track' if pct >= 80 else '🟡 Behind' if pct >= 50 else '🔴 At Risk'
        return format_html(
            '<div style="background:{};color:white;padding:3px 10px;border-radius:12px;'
            'font-size:12px;font-weight:700;display:inline-block;">{} ({}%)</div>',
            color, label, pct
        )

    def changelist_view(self, request, extra_context=None):
        today = now().date()

        # ── Month navigation via session (avoids Django admin GET param conflict) ──
        # If nav buttons pass ?kpi_year=&kpi_month=, store in session then redirect clean
        if 'kpi_year' in request.GET and 'kpi_month' in request.GET:
            try:
                request.session['kpi_year'] = int(request.GET['kpi_year'])
                request.session['kpi_month'] = int(request.GET['kpi_month'])
            except (ValueError, TypeError):
                pass
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(request.path)

        selected_year  = request.session.get('kpi_year', today.year)
        selected_month = request.session.get('kpi_month', today.month)

        selected_date = datetime.date(selected_year, selected_month, 1)

        # ── Previous / Next month helpers ──────────────────────────────
        if selected_month == 1:
            prev_year, prev_month = selected_year - 1, 12
        else:
            prev_year, prev_month = selected_year, selected_month - 1

        if selected_month == 12:
            next_year, next_month = selected_year + 1, 1
        else:
            next_year, next_month = selected_year, selected_month + 1

        # ── Build KPI card data ────────────────────────────────────────
        if request.user.is_superuser or request.user.groups.filter(name='Manager').exists():
            kpi_qs = KPITarget.objects.filter(
                month__year=selected_year, month__month=selected_month
            ).select_related('staff')
        else:
            kpi_qs = KPITarget.objects.filter(
                staff=request.user,
                month__year=selected_year, month__month=selected_month
            ).select_related('staff')

        kpi_cards = []
        for kpi in kpi_qs:
            kpi_cards.append({
                'kpi': kpi,
                'username': kpi.staff.get_full_name() or kpi.staff.username,
                'overall_pct': kpi.overall_pct(),
                'metrics': [
                    {'label': '📞 Leads Converted', 'actual': kpi.actual_leads(),
                     'target': kpi.target_leads, 'pct': kpi.leads_pct()},
                    {'label': '✅ Tasks Completed', 'actual': kpi.actual_tasks(),
                     'target': kpi.target_tasks, 'pct': kpi.tasks_pct()},
                    {'label': '💬 Interactions',    'actual': kpi.actual_interactions(),
                     'target': kpi.target_interactions, 'pct': kpi.interactions_pct()},
                    {'label': '💰 Revenue (৳)',     'actual': int(kpi.actual_revenue()),
                     'target': int(kpi.target_revenue), 'pct': kpi.revenue_pct()},
                ]
            })

        extra_context = extra_context or {}
        extra_context['kpi_cards']          = kpi_cards
        extra_context['selected_month']     = selected_date.strftime('%B %Y')
        extra_context['prev_url']           = f'?kpi_year={prev_year}&kpi_month={prev_month}'
        extra_context['next_url']           = f'?kpi_year={next_year}&kpi_month={next_month}'
        extra_context['is_manager']         = (
            request.user.is_superuser or request.user.groups.filter(name='Manager').exists()
        )
        return super().changelist_view(request, extra_context=extra_context)
