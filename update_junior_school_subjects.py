
import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Excel.settings')
django.setup()

from Exam.models import Subject, Course

def update_subjects():
    # Define Course mapping
    courses_data = {
        'LAN': 'Language & Communication',
        'SCI': 'Mathematics & Science',
        'ENV': 'Environment & Social',
        'ART': 'Creative & Psychomotor',
        'REL': 'Religious & Moral',
        'TEC': 'Technical & Applied',
    }
    
    # Ensure courses exist
    course_objects = {}
    for abbr, name in courses_data.items():
        course, created = Course.objects.get_or_create(abbreviation=abbr, defaults={'name': name})
        course_objects[abbr] = course
        if created:
            print(f"Created course: {name} ({abbr})")

    # Subjects to add for Grade 7, 8, 9
    junior_subjects = [
        # (Subject Name, Course Abbreviation)
        ('English', 'LAN'),
        ('Kiswahili', 'LAN'),
        ('Mathematics', 'SCI'),
        ('Integrated Science', 'SCI'),
        ('Health Education', 'SCI'),
        ('Pre-Technical Studies', 'TEC'),
        ('Social Studies', 'ENV'),
        ('Christian Religious Education', 'REL'),
        ('Islamic Religious Education', 'REL'),
        ('Business Studies', 'TEC'),
        ('Agriculture', 'SCI'),
        ('Life Skills Education', 'REL'),
        ('Physical Education and Sports', 'ART'),
        ('Computer Science', 'TEC'),
        ('Visual Arts', 'ART'),
        ('Performing Arts', 'ART'),
        ('Home Science', 'TEC'),
    ]

    grades = ['Grade 7', 'Grade 8', 'Grade 9']
    
    total_created = 0
    for subject_name, course_abbr in junior_subjects:
        course = course_objects[course_abbr]
        for grade in grades:
            subj, created = Subject.objects.get_or_create(
                name=subject_name,
                grade=grade,
                defaults={'course': course}
            )
            if created:
                print(f"Created: {subject_name} for {grade}")
                total_created += 1
            else:
                # Optionally update course if it exists but is different
                if subj.course != course:
                    subj.course = course
                    subj.save()
                    print(f"Updated course for: {subject_name} ({grade})")

    print(f"\nFinished! Added {total_created} new subject records.")

if __name__ == "__main__":
    update_subjects()
