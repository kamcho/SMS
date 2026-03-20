import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Excel.settings')
django.setup()

from core.models import PromotionHistory, AcademicYear
from django.db.models import Count

def detect_double_promotions():
    active_year = AcademicYear.objects.get(is_active=True)
    doubles = PromotionHistory.objects.filter(academic_year=active_year).values('student').annotate(cnt=Count('id')).filter(cnt__gt=1)
    
    print(f"Found {doubles.count()} students with double promotions in {active_year}")
    for d in doubles[:5]:
        sid = d['student']
        recs = PromotionHistory.objects.filter(student_id=sid, academic_year=active_year).order_by('promoted_at')
        print(f"Student ID {sid}:")
        for r in recs:
            print(f"  {r.from_class} -> {r.to_class} ({r.promoted_at})")

if __name__ == "__main__":
    detect_double_promotions()
