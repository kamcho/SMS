import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Excel.settings')
django.setup()

from core.models import AcademicYear

def check_years():
    for y in AcademicYear.objects.all():
        print(f"Year ID: {y.id}, Year: {y}, Active: {y.is_active}")

if __name__ == "__main__":
    check_years()
