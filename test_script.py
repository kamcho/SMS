import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SMS.settings") # adjust SMS if incorrect, wait project is SMS but settings could be Excel.settings
try:
    django.setup()
    from django.test import Client
    from core.models import Student, User, Class
    user = User.objects.filter(is_superuser=True).first()
    client = Client()
    client.force_login(user)
    res = client.get('/class/6/analytics/')
    print("STATUS", res.status_code)
except Exception as e:
    import traceback
    traceback.print_exc()
