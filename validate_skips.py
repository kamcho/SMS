import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Excel.settings')
django.setup()

from core.models import StudentProfile, PromotionHistory, AcademicYear, Class, School

def validate_skips():
    active_year = AcademicYear.objects.filter(is_active=True).first()
    print(f"Validating for Academic Year: {active_year}")
    
    # 1. Get all students who were promoted from PP2 or Grade 6 this year
    ph_records = PromotionHistory.objects.filter(
        academic_year=active_year,
        from_class__grade__name__in=['PP2', 'Grade 6']
    ).select_related('student', 'from_class', 'from_class__grade', 'from_class__grade__school')
    
    total_found = ph_records.count()
    print(f"Total students promoted from PP2/Grade 6: {total_found}")
    
    skipped_correctly = 0
    not_skipped = []
    
    for ph in ph_records:
        profile = StudentProfile.objects.filter(student=ph.student).first()
        if profile:
            if profile.class_id is None:
                skipped_correctly += 1
            else:
                not_skipped.append({
                    'id': ph.student.id,
                    'adm': ph.student.adm_no,
                    'school': ph.from_class.grade.school.name,
                    'old_class': ph.from_class.grade.name,
                    'new_class': str(profile.class_id)
                })
        else:
            print(f"Warning: Student {ph.student.adm_no} has no profile!")

    print(f"\nResults:")
    print(f"  Skipped Correctly (Class is None): {skipped_correctly}")
    print(f"  NOT Skipped (Class is assigned): {len(not_skipped)}")
    
    if not_skipped:
        print("\nDetail of students NOT skipped:")
        for item in not_skipped[:20]:  # Show first 20
            print(f"  {item['adm']} - {item['school']} - {item['old_class']} -> {item['new_class']}")
        if len(not_skipped) > 20:
            print(f"  ... and {len(not_skipped) - 20} more.")
    else:
        print("\n✅ Verification SUCCESS: All PP2 and Grade 6 students were correctly moved to 'None' for reshuffling.")

if __name__ == "__main__":
    validate_skips()
