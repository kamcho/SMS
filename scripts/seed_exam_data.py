import os
import django
import random
import sys

# Setup Django environment
sys.path.append('/home/kali/Documents/SMS/Excel')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Excel.settings')
django.setup()

from Exam.models import Exam, Subject, ExamSubjectConfiguration, ScoreRanking, ExamSubjectPaper, ExamSUbjectScore
from core.models import Student, StudentProfile, Class, Grade
from django.db import transaction

def seed_data():
    exam_id = 8
    try:
        exam = Exam.objects.get(id=exam_id)
    except Exam.DoesNotExist:
        print(f"Exam with ID {exam_id} not found.")
        return

    grade_name = 'Grade 3'
    subjects = Subject.objects.filter(grade=grade_name)
    if not subjects.exists():
        print(f"No subjects found for {grade_name}.")
        return

    # Get students in Grade 3 classes
    students = Student.objects.filter(studentprofile__class_id__grade__name=grade_name)
    if not students.exists():
        print(f"No students found in {grade_name}.")
        return

    print(f"Seeding data for Exam: {exam.name}, Grade: {grade_name}")
    print(f"Found {subjects.count()} subjects and {students.count()} students.")

    with transaction.atomic():
        for subject in subjects:
            # 1. Create/Update Configuration
            # Randomly decide paper count (1, 2, or 3)
            paper_count = random.choice([1, 2, 3])
            # Randomly decide total max score (30-100)
            total_max_score = random.randint(30, 100)
            
            config, created = ExamSubjectConfiguration.objects.get_or_create(
                exam=exam,
                subject=subject,
                defaults={
                    'max_score': total_max_score,
                    'paper_count': paper_count
                }
            )
            
            if not created:
                config.max_score = total_max_score
                config.paper_count = paper_count
                config.save()

            # 2. Create Score Rankings for this config
            # EE: 80-100%, ME: 60-79%, AE: 40-59%, BE: 0-39%
            rankings_data = [
                ('EE', int(total_max_score * 0.8), total_max_score),
                ('ME', int(total_max_score * 0.6), int(total_max_score * 0.79)),
                ('AE', int(total_max_score * 0.4), int(total_max_score * 0.59)),
                ('BE', 0, int(total_max_score * 0.39)),
            ]
            
            # Clear old rankings to avoid unique constraint issues if we re-run
            ScoreRanking.objects.filter(subject=config).delete()
            
            for grade_code, min_s, max_s in rankings_data:
                # min_s should not exceed max_s
                if min_s > max_s: min_s = max_s
                ScoreRanking.objects.create(
                    subject=config,
                    min_score=min_s,
                    max_score=max_s,
                    grade=grade_code
                )

            # 3. Create Papers
            # Clear old papers
            ExamSubjectPaper.objects.filter(exam_subject=config).delete()
            
            papers = []
            remaining_max = total_max_score
            for i in range(1, paper_count + 1):
                if i == paper_count:
                    out_of = remaining_max
                else:
                    # Allocate at least 5 marks per paper if possible
                    upper = max(5, remaining_max - (paper_count - i) * 5)
                    out_of = random.randint(5, upper)
                    remaining_max -= out_of
                
                paper = ExamSubjectPaper.objects.create(
                    exam_subject=config,
                    name=f"Paper {i}" if paper_count > 1 else "Main Paper",
                    paper_number=i,
                    out_of=out_of
                )
                papers.append(paper)

            # 4. Seed Scores for each student
            for student in students:
                for paper in papers:
                    # Random score between 0 and paper.out_of
                    score_val = random.randint(0, paper.out_of)
                    
                    # Create or update score
                    # Use unique_together (paper, student)
                    ExamSUbjectScore.objects.update_or_create(
                        paper=paper,
                        student=student,
                        defaults={'score': score_val}
                    )

    print("Seeding completed successfully!")

if __name__ == "__main__":
    seed_data()
