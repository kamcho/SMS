import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Excel.settings')
django.setup()

from core.models import StudentProfile, PromotionHistory, AcademicYear, Student

def double_check():
    s = Student.objects.get(adm_no='EG-2996')
    active_year = AcademicYear.objects.get(is_active=True)
    ph_list = PromotionHistory.objects.filter(student=s, academic_year=active_year).order_by('promoted_at')
    
    print(f"Double Check for {s.adm_no}:")
    for ph in ph_list:
        print(f"  From: {ph.from_class} -> To: {ph.to_class} (Graduation={ph.is_graduation}) at {ph.promoted_at}")
    
    profile = StudentProfile.objects.filter(student=s).first()
    print(f"Current Profile Class: {profile.class_id}, Status: {profile.status}")

if __name__ == "__main__":
    double_check()
