import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Excel.settings')
django.setup()

from Exam.models import Exam, Subject, ExamSubjectConfiguration, ExamSubjectPaper, Course
from core.models import AcademicYear, Term

# Cleanup
ExamSubjectConfiguration.objects.all().delete()
ExamSubjectPaper.objects.all().delete()

# Setup
year = AcademicYear.objects.first()
term = Term.objects.first()
exam, _ = Exam.objects.get_or_create(name='Test Exam', year=year, term=term, period='CAT')
course, _ = Course.objects.get_or_create(name='Test Course', abbreviation='TC')
subject, _ = Subject.objects.get_or_create(course=course, name='Test Subject', grade='Grade 1')

# Create config with paper_count = 1
config = ExamSubjectConfiguration.objects.create(
    exam=exam,
    subject=subject,
    max_score=100,
    paper_count=1
)

# Check if paper was created
papers = ExamSubjectPaper.objects.filter(exam_subject=config)
print(f"Number of papers created: {papers.count()}")
for paper in papers:
    print(f"Paper: {paper.name}, number: {paper.paper_number}, out_of: {paper.out_of}")

if papers.count() == 1:
    print("SUCCESS: Default paper created correctly.")
else:
    print("FAILURE: Default paper not created correctly.")
