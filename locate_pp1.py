import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Excel.settings')
django.setup()

from core.models import StudentProfile, PromotionHistory, AcademicYear, Class

def locate_students():
    # Find PP1 Indigo from previous year
    # Actually just find people who were in a class named PP1 Indigo and moved this year
    active_year = AcademicYear.objects.get(is_active=True)
    
    ph_list = PromotionHistory.objects.filter(
        from_class__grade__name__icontains='PP1',
        from_class__name__icontains='Indigo',
        academic_year=active_year
    )
    
    print(f"Tracing students from PP1 Indigo ({len(ph_list)} students):")
    for ph in ph_list[:10]:
        profile = StudentProfile.objects.filter(student=ph.student).first()
        print(f"  Student {ph.student.adm_no}: Ph.to_class={ph.to_class}, Current.class={profile.class_id}, Status={profile.status}")

if __name__ == "__main__":
    locate_students()
