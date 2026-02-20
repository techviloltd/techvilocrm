import os
import django
from io import StringIO
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from crm.models import Client
from django.conf import settings

# Capture stdout
old_stdout = sys.stdout
sys.stdout = mystdout = StringIO()

try:
    # Ensure a staff user exists with email
    if not User.objects.filter(email='admin@example.com').exists():
        User.objects.create_superuser('admin_test_email', 'admin@example.com', 'password')
    else:
        u = User.objects.get(email='admin@example.com')
        if not u.is_staff:
            u.is_staff = True
            u.save()

    print("Creating Test Client...")
    # Create client to trigger signal
    Client.objects.create(
        name="Test Email Client",
        company_name="Test Company",
        services="WEB"
    )
    
except Exception as e:
    sys.stdout = old_stdout
    print(f"Error: {e}")
    sys.exit(1)

# Restore stdout
sys.stdout = old_stdout
output = mystdout.getvalue()

print("--- CAPTURED OUTPUT ---")
print(output)
print("-----------------------")

if "Subject: New Client Joined" in output:
    print("SUCCESS: Email notification detected!")
else:
    print("FAILURE: No email notification found in output.")
