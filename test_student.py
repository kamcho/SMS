import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Excel.settings')
django.setup()

from core.models import PromotionHistory, Student

def test_single_student():
    # Since there are duplicates, I'll check all EG-2996
    students = Student.objects.filter(adm_no__icontains='EG-2996')
    for s in students:
        print(f"Student: {s.id} {s.get_full_name()}")
        ph = PromotionHistory.objects.filter(student=s)
        for p in ph:
            print(f"  - {p.from_class} -> {p.to_class} Year:{p.academic_year_id} At:{p.promoted_at}")

if __name__ == "__main__":
    test_single_student()
