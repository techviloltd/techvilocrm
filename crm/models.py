from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import datetime
from django.utils import timezone

# --- CLIENT MODEL ---
class Client(models.Model):
    SERVICE_CHOICES = [
        ('AI', 'AI Agent Development'),
        ('WEB', 'Web Development'),
        ('SEO', 'SEO & Marketing'),
        ('UIUX', 'UI/UX Design'),
    ]

    name = models.CharField(max_length=200)
    company_name = models.CharField(max_length=200, blank=True)
    services = models.CharField(max_length=100)
    total_payable = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    assigned_to = models.ManyToManyField(User, blank=True, related_name='assigned_clients')

    @property
    def due_amount(self):
        return self.total_payable - self.paid_amount

    def __str__(self):
        return self.name
    
# --- LEAD MODEL ---
class Lead(models.Model):
    STATUS_CHOICES = [
        ('COLD', 'Cold (Just Started)'),
        ('WARM', 'Warm (Interested)'),
        ('HOT', 'Hot (Ready to Close)'),
        ('CONVERTED', 'Converted to Client'),
    ]

    name = models.CharField(max_length=200, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    source = models.CharField(max_length=100)
    contact_info = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='COLD')
    next_follow_up = models.DateField(null=True, blank=True)
    feedback_notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    converted_at = models.DateTimeField(null=True, blank=True, verbose_name='Converted At')

    def __str__(self):
        return f"{self.name or self.source} - {self.status}"
    
# --- PROJECT MODEL ---
class Project(models.Model):
    STATUS_CHOICES = [
        ('PLANNING', 'Planning'),
        ('IN_PROGRESS', 'In Progress'),
        ('REVIEW', 'In Review'),
        ('COMPLETED', 'Completed'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='projects')
    project_name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNING')
    deadline = models.DateField(null=True, blank=True)
    progress_percentage = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.project_name} - {self.client.name}"

# --- NEW: TASK MODEL ---
class Task(models.Model):
    STATUS_CHOICES = [
        ('TODO', 'To Do'),
        ('IN_PROGRESS', 'In Progress'),
        ('REVIEW', 'In Review'),
        ('DONE', 'Done'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    task_name = models.CharField(max_length=200)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TODO')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    is_completed = models.BooleanField(default=False) 
    due_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.task_name} ({self.project.project_name})"

    @property
    def checklist_total(self):
        return self.checklist_items.count()

    @property
    def checklist_done(self):
        return self.checklist_items.filter(is_done=True).count()

class TaskChecklist(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='checklist_items')
    item_name = models.CharField(max_length=200)
    is_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.item_name

# --- Auto Progress Logic (Magic!) ---
@receiver([post_save, post_delete], sender=Task)
def update_project_progress(sender, instance, **kwargs):
    project = instance.project
    total_tasks = project.tasks.count()
    
    if total_tasks > 0:
        # Update logic: Count 'DONE' tasks
        completed_tasks = project.tasks.filter(status='DONE').count()
        # % calculation: (completed / total) * 100
        project.progress_percentage = int((completed_tasks / total_tasks) * 100)
    else:
        project.progress_percentage = 0
    project.save()

# --- Auto-sync is_completed when Task status changes ---
@receiver(post_save, sender=Task)
def sync_task_is_completed(sender, instance, **kwargs):
    """Keep is_completed in sync with status='DONE' regardless of how it's updated."""
    expected = instance.status == 'DONE'
    if instance.is_completed != expected:
        Task.objects.filter(pk=instance.pk).update(is_completed=expected)

# --- NEW: INTERACTION HISTORY MODEL ---
class Interaction(models.Model):
    INTERACTION_TYPES = [
        ('CALL', 'Phone Call'),
        ('EMAIL', 'Email'),
        ('MEETING', 'Meeting'),
        ('NOTE', 'Internal Note'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True, related_name='interactions')
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, null=True, blank=True, related_name='interactions')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES, default='NOTE')
    notes = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_interaction_type_display()} - {self.created_at.strftime('%Y-%m-%d')}"

class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('INCOME', 'Income'),
        ('EXPENSE', 'Expense'),
    ]

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, default='EXPENSE')
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    date = models.DateField(default=datetime.date.today)
    description = models.CharField(max_length=255)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_transaction_type_display()}: {self.amount} ({self.date})"

# --- Financial Automation Logic ---
def _recalculate_paid_amount(client):
    """Recalculate paid_amount for a client from all income sources."""
    # Direct income: transaction.client = this client
    direct_income = Transaction.objects.filter(
        client=client,
        transaction_type='INCOME'
    ).aggregate(models.Sum('amount'))['amount__sum'] or 0

    # Project income: transaction.project.client = this client, but client field is blank
    # (avoid double-counting transactions that have BOTH client and project set)
    project_income = Transaction.objects.filter(
        project__client=client,
        client__isnull=True,
        transaction_type='INCOME'
    ).aggregate(models.Sum('amount'))['amount__sum'] or 0

    client.paid_amount = direct_income + project_income
    client.save(update_fields=['paid_amount'])

@receiver(post_save, sender=Transaction)
def update_client_paid_amount_on_save(sender, instance, created, **kwargs):
    # Determine affected client (directly linked or via project)
    client = instance.client
    if not client and instance.project_id:
        try:
            client = instance.project.client
        except Exception:
            client = None

    if client and instance.transaction_type == 'INCOME':
        _recalculate_paid_amount(client)

@receiver(post_delete, sender=Transaction)
def update_client_paid_amount_on_delete(sender, instance, **kwargs):
    client = instance.client
    if not client and instance.project_id:
        try:
            client = instance.project.client
        except Exception:
            client = None

    if client and instance.transaction_type == 'INCOME':
        _recalculate_paid_amount(client)

# --- NEW: DOCUMENT MODEL ---
class Document(models.Model):
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents')
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.title}"

# --- KPI TARGET MODEL ---
class KPITarget(models.Model):
    """Monthly KPI targets set by Manager for each staff member."""
    staff = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='kpi_targets',
        limit_choices_to={'is_superuser': False},
        verbose_name='Staff Member'
    )
    month = models.DateField(
        help_text='Select the 1st day of the target month',
        verbose_name='Month'
    )
    target_leads = models.IntegerField(default=0, verbose_name='Target: Leads Converted')
    target_tasks = models.IntegerField(default=0, verbose_name='Target: Tasks Completed')
    target_interactions = models.IntegerField(default=0, verbose_name='Target: Interactions')
    target_revenue = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Target: Revenue (৳)'
    )
    notes = models.TextField(blank=True, verbose_name='Manager Notes')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='kpi_targets_created',
        verbose_name='Set By'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('staff', 'month')
        ordering = ['-month', 'staff']
        verbose_name = 'KPI Target'
        verbose_name_plural = 'KPI Targets'

    def __str__(self):
        return f"{self.staff.username} — {self.month.strftime('%B %Y')}"

    def get_month_start(self):
        return self.month.replace(day=1)

    def get_month_end(self):
        """Last day of the target month."""
        import calendar
        last_day = calendar.monthrange(self.month.year, self.month.month)[1]
        return self.month.replace(day=last_day)

    # ── Auto-calculated actuals (computed from live data) ──────────────

    def actual_leads(self):
        """Count leads CONVERTED by this staff member this month (by conversion date)."""
        return Lead.objects.filter(
            assigned_to=self.staff,
            status='CONVERTED',
            converted_at__month=self.month.month,
            converted_at__year=self.month.year,
        ).count()

    def actual_tasks(self):
        """Count tasks COMPLETED by this staff member this month."""
        return Task.objects.filter(
            assigned_to=self.staff,
            is_completed=True,
            due_date__month=self.month.month,
            due_date__year=self.month.year,
        ).count()

    def actual_interactions(self):
        """Count interactions logged by this staff member this month."""
        return Interaction.objects.filter(
            created_by=self.staff,
            created_at__month=self.month.month,
            created_at__year=self.month.year,
        ).count()

    def actual_revenue(self):
        """Sum of INCOME transactions created by this staff member this month."""
        from django.db.models import Sum as _Sum
        result = Transaction.objects.filter(
            created_by=self.staff,
            transaction_type='INCOME',
            date__month=self.month.month,
            date__year=self.month.year,
        ).aggregate(total=_Sum('amount'))['total'] or 0
        return float(result)

    def pct(self, actual, target):
        """Safe percentage calculation."""
        if not target:
            return 100 if actual else 0
        return min(int((actual / target) * 100), 100)

    def leads_pct(self):
        return self.pct(self.actual_leads(), self.target_leads)

    def tasks_pct(self):
        return self.pct(self.actual_tasks(), self.target_tasks)

    def interactions_pct(self):
        return self.pct(self.actual_interactions(), self.target_interactions)

    def revenue_pct(self):
        return self.pct(self.actual_revenue(), float(self.target_revenue))

    def overall_pct(self):
        parts = [self.leads_pct(), self.tasks_pct(), self.interactions_pct(), self.revenue_pct()]
        return int(sum(parts) / len(parts))