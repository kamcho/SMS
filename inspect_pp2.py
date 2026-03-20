import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Excel.settings')
django.setup()

from core.models import PromotionHistory, AcademicYear, StudentProfile

def inspect_pp2_move():
    active_year = AcademicYear.objects.filter(is_active=True).first()
    ph = PromotionHistory.objects.filter(from_class__grade__name__icontains='PP2', academic_year=active_year).first()
    if ph:
        print(f"Sample promotion from PP2:")
        print(f"  Student: {ph.student.adm_no}")
        print(f"  To Class: {ph.to_class}")
        print(f"  Is Graduation: {ph.is_graduation}")
        print(f"  Promoted At: {ph.promoted_at}")
        
        # Check current status of student
        sp = StudentProfile.objects.filter(student=ph.student).first()
        print(f"  Current Class: {sp.class_id}")
        print(f"  Current Status: {sp.status}")
    else:
        print("No PP2 promotion history found for active year.")

if __name__ == "__main__":
    inspect_pp2_move()
