import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Excel.settings')
django.setup()

from core.models import PromotionHistory, AcademicYear

def trace_pp1():
    active_year = AcademicYear.objects.filter(is_active=True).first()
    ph = PromotionHistory.objects.filter(from_class__grade__name__icontains='PP1', academic_year=active_year)
    
    print(f"Tracing PP1 Promotions for {active_year}:")
    counts = {}
    for p in ph:
        target = p.to_class.grade.name if p.to_class else ("Graduated" if p.is_graduation else "None")
        counts[target] = counts.get(target, 0) + 1
    
    for target, count in counts.items():
        print(f"  Moved to {target}: {count}")

if __name__ == "__main__":
    trace_pp1()
