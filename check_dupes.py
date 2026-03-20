import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Excel.settings')
django.setup()

from core.models import Student, StudentProfile

def check_duplicates():
    from django.db.models import Count
    dupes = Student.objects.values('adm_no').annotate(count=Count('id')).filter(count__gt=1)
    
    print(f"Found {dupes.count()} duplicate Admission Numbers:")
    for d in dupes[:10]:
        adm = d['adm_no']
        count = d['count']
        print(f"  {adm}: {count} students found.")
        students = Student.objects.filter(adm_no=adm)
        for s in students:
            profile = StudentProfile.objects.filter(student=s).first()
            print(f"    - ID: {s.id}, Name: {s.get_full_name()}, Class: {profile.class_id if profile else 'No Profile'}")

if __name__ == "__main__":
    check_duplicates()
