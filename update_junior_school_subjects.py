
import os
import django
import sys

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Excel.settings')
django.setup()

from Exam.models import Subject, Course, ScoreRanking, ExamSubjectConfiguration

def update_junior_school_data():
    """
    Scrapes/Defines KICD Junior School (Grade 7-9) subjects and updates their associations.
    """
    # 1. Define Course mapping for organization
    courses_data = {
        'LAN': 'Language & Communication',
        'SCI': 'Mathematics & Science',
        'ENV': 'Environment & Social',
        'ART': 'Creative & Psychomotor',
        'REL': 'Religious & Moral',
        'TEC': 'Technical & Applied',
    }
    
    course_objects = {}
    for abbr, name in courses_data.items():
        course, _ = Course.objects.get_or_create(abbreviation=abbr, defaults={'name': name})
        course_objects[abbr] = course

    # 2. Define KICD Junior Secondary Subjects (Core and Optional)
    junior_subjects = [
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
    
    print("--- Updating Subjects for Grade 7, 8, and 9 ---")
    total_created = 0
    managed_subjects = []
    for subject_name, course_abbr in junior_subjects:
        course = course_objects[course_abbr]
        for grade in grades:
            subj, created = Subject.objects.get_or_create(
                name=subject_name,
                grade=grade,
                defaults={'course': course}
            )
            managed_subjects.append(subj)
            if created:
                print(f" [+] Added: {subject_name} ({grade})")
                total_created += 1
            else:
                if subj.course != course:
                    subj.course = course
                    subj.save()
                    print(f" [^] Updated course: {subject_name} ({grade})")

    print(f"\nSuccess: Managed {len(managed_subjects)} subject-grade associations.")
    print(f"New records created: {total_created}")

    # 3. Optional: Set up Standard CBC Grading Scale for these subjects
    # This part updates 'grades' in the sense of ScoreRanking (EE, ME, AE, BE)
    print("\n--- Applying Standard CBC Grading Scales (Optional) ---")
    
    # We only apply this if a configuration exists for an exam
    configs = ExamSubjectConfiguration.objects.filter(subject__grade__in=grades)
    updated_rankings = 0
    
    for config in configs:
        max_score = config.max_score
        # Standard CBC: EE (80%+), ME (60%+), AE (40%+), BE (<40%)
        rankings = [
            ('EE', int(max_score * 0.8), max_score),
            ('ME', int(max_score * 0.6), int(max_score * 0.79)),
            ('AE', int(max_score * 0.4), int(max_score * 0.59)),
            ('BE', 0, int(max_score * 0.39)),
        ]
        
        # Update or create rankings
        for grade_code, min_s, max_s in rankings:
            ScoreRanking.objects.update_or_create(
                subject=config,
                grade=grade_code,
                defaults={'min_score': min_s, 'max_score': max_s}
            )
        updated_rankings += 1

    if updated_rankings > 0:
        print(f"Applied CBC grading scales to {updated_rankings} exam configurations.")
    else:
        print("No active exam configurations found for these grades to apply grading scales to.")

if __name__ == "__main__":
    update_junior_school_data()
