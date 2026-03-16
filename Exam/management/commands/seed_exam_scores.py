import random
from django.core.management.base import BaseCommand
from core.models import Student, StudentProfile, AcademicYear, Term, Class, Grade
from Exam.models import Exam, Subject, ExamSUbjectScore

class Command(BaseCommand):
    help = 'Seeds random exam score data for students based on their grade and CBC subjects'

    def handle(self, *args, **kwargs):
        academic_year = AcademicYear.objects.first()
        term = Term.objects.first()

        if not academic_year or not term:
            self.stdout.write(self.style.ERROR('Please ensure AcademicYear and Term exist before seeding scores.'))
            return

        # Create an Exam
        exam, _ = Exam.objects.get_or_create(
            name='End Term',
            year=academic_year,
            term=term
        )

        students = StudentProfile.objects.all().select_related('student', 'class_id__grade')
        total_students = students.count()
        score_count = 0

        self.stdout.write(f"Seeding scores for {total_students} students...")

        for i, profile in enumerate(students, 1):
            if not profile.class_id:
                continue

            grade_name = profile.class_id.grade.name
            subjects = Subject.objects.filter(grade=grade_name)

            for subject in subjects:
                # Random score between 40 and 100
                score = random.randint(40, 100)
                
                ExamSUbjectScore.objects.get_or_create(
                    exam=exam,
                    student=profile.student,
                    subject=subject,
                    defaults={'score': score}
                )
                score_count += 1
            
            # Show progress
            percent = (i / total_students) * 100
            self.stdout.write(f"Progress: [{i}/{total_students}] {percent:.1f}% complete...", ending='\r')
            self.stdout.flush()

        self.stdout.write("") # New line after the progress bar
        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {score_count} subject scores across {total_students} students.'))
