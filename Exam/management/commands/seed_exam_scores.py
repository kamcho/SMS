import random
from django.core.management.base import BaseCommand
from core.models import StudentProfile
from Exam.models import Exam, ExamSubjectConfiguration, ExamSubjectPaper, ExamSUbjectScore

class Command(BaseCommand):
    help = 'Seeds random exam score data for a specific exam based on subject configurations'

    def add_arguments(self, parser):
        parser.add_argument('exam_id', type=int, help='The ID of the exam to seed scores for')
        parser.add_argument('--clear', action='store_true', help='Clear existing scores for this exam before seeding')

    def handle(self, *args, **options):
        exam_id = options['exam_id']
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Exam with ID {exam_id} does not exist."))
            return
        
        if options['clear']:
            self.stdout.write(f"Clearing existing scores for {exam.name}...")
            ExamSUbjectScore.objects.filter(paper__exam_subject__exam=exam).delete()

        # Get all configurations for this exam
        configs = ExamSubjectConfiguration.objects.filter(exam=exam).select_related('subject')
        if not configs.exists():
            self.stdout.write(self.style.WARNING(f"No subject configurations found for exam {exam.name}. Please configure subjects first."))
            return

        total_scores = 0
        total_configs = configs.count()
        
        self.stdout.write(f"Seeding scores for exam: {exam.name} ({exam.year}, {exam.term})")

        for idx, config in enumerate(configs, 1):
            grade_name = config.subject.grade
            # Get students in this grade across all schools (or filter as needed)
            student_profiles = StudentProfile.objects.filter(class_id__grade__name=grade_name).select_related('student')
            papers = config.examsubjectpaper_set.all()
            
            if not papers.exists():
                self.stdout.write(self.style.WARNING(f"  - No papers found for {config.subject.name} in {grade_name}. Skipping."))
                continue

            self.stdout.write(f"[{idx}/{total_configs}] Seeding {config.subject.name} for {grade_name} ({student_profiles.count()} students)...")
            
            for profile in student_profiles:
                for paper in papers:
                    # Random score between 40% and 100% of out_of
                    min_score = int(paper.out_of * 0.3)
                    score = random.randint(min_score, paper.out_of)
                    
                    ExamSUbjectScore.objects.update_or_create(
                        paper=paper,
                        student=profile.student,
                        defaults={
                            'score': score,
                            'class_id': profile.class_id
                        }
                    )
                    total_scores += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {total_scores} scores for exam "{exam.name}".'))
