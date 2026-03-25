import random
from e_learning.models import Quiz, Question, Option
from Exam.models import Subject
from core.models import Grade
from users.models import MyUser

# Setup context
user = MyUser.objects.filter(is_superuser=True).first()
if not user:
    user = MyUser.objects.first()

subjects = list(Subject.objects.all()[:20])
random.shuffle(subjects)

def create_test_quiz(title, subject):
    quiz = Quiz.objects.create(
        title=title,
        description=f"Automated test quiz for {subject.name} - {subject.grade}",
        subject=subject,
        created_by=user,
        status='published',
        time_limit_minutes=15,
        max_attempts=3
    )
    
    # 2 Multiple Choice Questions
    for i in range(2):
        q = Question.objects.create(
            question=f"Sample MCQ {i+1} for {title}: What is 2 + {i}?",
            question_type='multiple_choice',
            marks=2,
            order=i
        )
        Option.objects.create(question=q, option=str(2+i), is_correct=True, order=0)
        Option.objects.create(question=q, option=str(2+i+1), is_correct=False, order=1)
        Option.objects.create(question=q, option=str(2+i+2), is_correct=False, order=2)
        quiz.questions.add(q)
        
    # 2 Short Answer Questions
    for i in range(2):
        q = Question.objects.create(
            question=f"Sample Short Answer {i+1} for {title}: Explain the concept of {subject.name}.",
            question_type='short_answer',
            marks=5,
            expected_answer=f"The concept of {subject.name} involves basic principles of the student's level.",
            order=i+2
        )
        quiz.questions.add(q)
    
    return quiz

# Create 5 quizzes
for index in range(min(5, len(subjects))):
    sub = subjects[index]
    create_test_quiz(f"Assessment {index+1} - {sub.name}", sub)

print("Created 5 test quizzes successfully.")
