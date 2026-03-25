from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import Grade, School, Class, Student
from Exam.models import Subject


class Strand(models.Model):
    """KICD Strand model - Main topic area within a subject"""
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='strands')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta: 
        ordering = ['order', 'name']
        unique_together = ['subject']
    
    def __str__(self):
        return f"{self.subject.name} - {self.name}"


class Substrand(models.Model):
    """KICD Substrand model - Specific topic within a strand"""
    strand = models.ForeignKey(Strand, on_delete=models.CASCADE, related_name='substrands')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'name']
        unique_together = ['strand']
        
    def __str__(self):
        return f"{self.strand.name} - {self.name}"


class LearningOutcome(models.Model):
    """Learning outcomes for substrands"""
    substrand = models.ForeignKey(Substrand, on_delete=models.CASCADE, related_name='learning_outcomes')
    outcome = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.substrand.name} - Outcome {self.order + 1}"


class SuggestedActivity(models.Model):
    """Suggested learning activities"""
    substrand = models.ForeignKey(Substrand, on_delete=models.CASCADE, related_name='suggested_activities')
    activity = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.substrand.name} - Activity {self.order + 1}"


class AssessmentCriterion(models.Model):
    """Assessment criteria for substrands"""
    substrand = models.ForeignKey(Substrand, on_delete=models.CASCADE, related_name='assessment_criteria')
    criterion = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.substrand.name} - Criterion {self.order + 1}"




# ──────────────────────────────────────────────────
#  ONLINE TEST / QUIZ MODELS
# ──────────────────────────────────────────────────

class Quiz(models.Model):
    """A test/quiz that groups questions for students to take online"""
    QUIZ_STATUS = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('closed', 'Closed'),
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='quizzes')
    target_classes = models.ManyToManyField(Class, blank=True, related_name='quizzes',
                                           help_text="Specific classes/streams that can take this quiz")
    substrand = models.ForeignKey(Substrand, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='quizzes',
                                  help_text="Optionally link quiz to a specific substrand")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='created_quizzes')
    status = models.CharField(max_length=20, choices=QUIZ_STATUS, default='draft')
    time_limit_minutes = models.PositiveIntegerField(default=30,
                                                     help_text="Time limit in minutes (0 = unlimited)")
    max_attempts = models.PositiveIntegerField(default=1,
                                               help_text="Max attempts per student (0 = unlimited)")
    pass_percentage = models.PositiveIntegerField(default=50,
                                                  help_text="Minimum % to pass the quiz")
    shuffle_questions = models.BooleanField(default=False)
    
    questions = models.ManyToManyField('Question', blank=True, related_name='quizzes')
    available_from = models.DateTimeField(null=True, blank=True)
    available_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Quizzes"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.subject.name})"


    @property
    def total_marks(self):
        return self.questions.aggregate(total=models.Sum('marks'))['total'] or 0

    @property
    def question_count(self):
        return self.questions.filter(is_active=True).count()

    @property
    def is_available(self):
        """Check if quiz is currently available for students"""
        now = timezone.now()
        if self.status != 'published':
            return False
        if self.available_from and now < self.available_from:
            return False
        if self.available_until and now > self.available_until:
            return False
        return True


class Question(models.Model):
    """Questions for assessment — linked to quiz and optionally to substrand"""
    QUESTION_TYPES = (
        ('multiple_choice', 'Multiple Choice'),
        ('short_answer', 'Short Answer'),
    )
    substrand = models.ForeignKey(Substrand, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='questions')
    question_type = models.CharField(max_length=50, choices=QUESTION_TYPES)
    question = models.TextField()
    marks = models.PositiveIntegerField(default=1, help_text="Points for this question")
    # For short_answer: the expected/model answer that OpenAI will compare against
    expected_answer = models.TextField(blank=True, null=True,
                                       help_text="Model answer for AI grading of short answers")
    # Optional image attachment for the question
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        prefix = self.substrand.name if self.substrand else "General"
        return f"{prefix} - Q{self.order + 1}: {self.question[:50]}"

class QuestionImage(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='e_learning/questions/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    

class Option(models.Model):
    """Options for multiple choice questions"""
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    option = models.TextField()
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        correct_label = "✓" if self.is_correct else "✗"
        return f"{correct_label} {self.option[:50]}"


# ──────────────────────────────────────────────────
#  STUDENT RESPONSE / ATTEMPT MODELS
# ──────────────────────────────────────────────────

class QuizAttempt(models.Model):
    """Tracks each time a student takes a quiz"""
    STATUS_CHOICES = (
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted'),
        ('graded', 'Graded'),
        ('timed_out', 'Timed Out'),
    )
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='quiz_attempts')
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    # Auto-calculated after grading
    total_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total_possible = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    passed = models.BooleanField(default=False)
    # Tracks how many short-answer questions have been AI-graded
    ai_grading_complete = models.BooleanField(default=False)

    class Meta:
        unique_together = ['quiz', 'student', 'attempt_number']
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.student} - {self.quiz.title} (Attempt {self.attempt_number})"

    @property
    def is_timed_out(self):
        """Check if this attempt has exceeded the time limit"""
        if self.quiz.time_limit_minutes == 0:
            return False
        if self.status in ('submitted', 'graded', 'timed_out'):
            return True
        elapsed = (timezone.now() - self.started_at).total_seconds() / 60
        return elapsed > self.quiz.time_limit_minutes

    @property
    def time_remaining_seconds(self):
        """Seconds remaining for this attempt"""
        if self.quiz.time_limit_minutes == 0:
            return None
        elapsed = (timezone.now() - self.started_at).total_seconds()
        remaining = (self.quiz.time_limit_minutes * 60) - elapsed
        return max(0, int(remaining))

    def calculate_score(self):
        """Calculate total score from all graded answers"""
        answers = self.answers.all()
        self.total_score = sum(a.score_awarded for a in answers)
        self.total_possible = sum(a.question.marks for a in answers)
        if self.total_possible > 0:
            self.percentage = (self.total_score / self.total_possible) * 100
        else:
            self.percentage = 0
        self.passed = self.percentage >= self.quiz.pass_percentage
        # Check if all short answers have been graded
        ungraded = answers.filter(
            question__question_type='short_answer',
            is_graded=False
        ).exists()
        self.ai_grading_complete = not ungraded
        if self.ai_grading_complete and self.status == 'submitted':
            self.status = 'graded'
        self.save()


class StudentAnswer(models.Model):
    """Individual student answer to a question within a quiz attempt"""
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='student_answers')
    # For multiple choice — the selected option(s)
    selected_option = models.ForeignKey(Option, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='selections')
    # For short answer — the student's written response
    text_answer = models.TextField(blank=True, null=True)
    # Grading fields
    score_awarded = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_graded = models.BooleanField(default=False)
    # AI grading feedback for short answers
    ai_feedback = models.TextField(blank=True, null=True,
                                   help_text="AI-generated feedback for short answer grading")
    ai_confidence = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True,
                                        help_text="AI confidence score 0.00-1.00")
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['attempt', 'question']

    def __str__(self):
        return f"{self.attempt.student} → Q{self.question.order + 1}"

    def auto_grade(self):
        """Auto-grade multiple choice answers (called on save).
        Short answers need OpenAI grading via a separate service."""
        if self.question.question_type == 'multiple_choice' and self.selected_option:
            if self.selected_option.is_correct:
                self.score_awarded = self.question.marks
            else:
                self.score_awarded = 0
            self.is_graded = True
            self.save()

    def save(self, *args, **kwargs):
        # Auto-grade multiple choice on save
        if self.question.question_type == 'multiple_choice' and self.selected_option and not self.is_graded:
            if self.selected_option.is_correct:
                self.score_awarded = self.question.marks
            else:
                self.score_awarded = 0
            self.is_graded = True
        super().save(*args, **kwargs)


class Assignment(models.Model):
    """Specific instance of a Quiz assigned to a Class"""
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='assignments')
    target_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='assignments')
    due_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.target_class.name})"

