import os
import django
from django.db.models import Count

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Excel.settings')
django.setup()

from core.models import StudentProfile, PromotionHistory, Class, AcademicYear

def check_promotion_stats():
    active_year = AcademicYear.objects.filter(is_active=True).first()
    print(f"Active Year: {active_year}")
    
    # Get all classes
    classes = Class.objects.select_related('grade').all()
    
    # Get all promoted_into IDs for this year
    all_promoted_into = list(PromotionHistory.objects.filter(
        academic_year=active_year,
        to_class__isnull=False
    ).values_list('student_id', flat=True))
    
    print(f"\nSummary for specific classes:")
    target_grades = ['PP2', 'Grade 6']
    
    for c in classes:
        if any(tg in c.grade.name for tg in target_grades):
            total_active = StudentProfile.objects.filter(class_id=c, status='Active').count()
            just_arrived = StudentProfile.objects.filter(
                class_id=c, 
                status='Active',
                student_id__in=all_promoted_into
            ).count()
            
            promoted_away = PromotionHistory.objects.filter(
                academic_year=active_year,
                from_class=c
            ).count()
            
            remaining = max(0, total_active - just_arrived)
            
            print(f"Class: {c.grade.name} {c.name}")
            print(f"  Total Active: {total_active}")
            print(f"  Just Arrived (Promoted IN): {just_arrived}")
            print(f"  Promoted AWAY (OUT): {promoted_away}")
            print(f"  REMAINING (Old students still here): {remaining}")
            print("-" * 30)

if __name__ == "__main__":
    check_promotion_stats()
