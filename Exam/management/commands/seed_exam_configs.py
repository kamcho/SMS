from django.core.management.base import BaseCommand
from Exam.models import Exam, Subject, ExamSubjectConfiguration, ExamSubjectPaper
import random

class Command(BaseCommand):
    help = 'Seeds subject configurations for a specific exam'

    def add_arguments(self, parser):
        parser.add_argument('exam_id', type=int, help='The ID of the exam to configure subjects for')
        parser.add_argument('--clear', action='store_true', help='Clear existing configurations for this exam before seeding')

    def handle(self, *args, **options):
        exam_id = options['exam_id']
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Exam with ID {exam_id} does not exist."))
            return

        if options['clear']:
            self.stdout.write(f"Clearing existing configurations for {exam.name}...")
            ExamSubjectConfiguration.objects.filter(exam=exam).delete()

        all_subjects = Subject.objects.all()
        config_count = 0
        
        self.stdout.write(f"Configuring {all_subjects.count()} subjects for exam: {exam.name}")

        for subject in all_subjects:
            # Determine max score based on grade level
            grade = subject.grade
            if any(x in grade for x in ['Play Group', 'PP1', 'PP2']):
                max_score = 30
            elif any(x in grade for x in ['Grade 1', 'Grade 2', 'Grade 3']):
                max_score = 50
            else:
                max_score = 100

            # Get or create configuration
            config, created = ExamSubjectConfiguration.objects.get_or_create(
                exam=exam,
                subject=subject,
                defaults={
                    'max_score': max_score,
                    'paper_count': 1
                }
            )
            
            if created:
                config_count += 1
                # Note: ExamSubjectConfiguration.save() automatically creates Paper 1 if paper_count is 1

            # Progress feedback for large sets
            if config_count % 10 == 0 and created:
                self.stdout.write(f"Created {config_count} configurations...", ending='\r')

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f'Successfully created {config_count} subject configurations for "{exam.name}".'))
        self.stdout.write(f'Summary: ECDE (30pts), Lower Primary (50pts), others (100pts).')
