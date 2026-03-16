from django.db import models

# Create your models here.
class Course(models.Model):
    name = models.CharField(max_length=100, unique=True)
    abbreviation = models.CharField(max_length=10, unique=True)
    
    def __str__(self):
        return self.name

class Subject(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    grade = models.CharField(max_length=10)
    
    def __str__(self):
        return str(self.name) + ' ' + str(self.grade)

class MySubject(models.Model):
    subject = models.ManyToManyField(Subject)
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE)
    
    def __str__(self):
        return self.student

class Exam(models.Model):
    period_choices = (
        ('Mid Term', 'Mid Term'),
        ('End Term', 'End Term'),
        ('Opener', 'Opener'),
        ('Mock', 'Mock'),
        ('CAT', 'CAT'),
        ('Final', 'Final'),
    )
    name = models.CharField(max_length=100)
    period = models.CharField(max_length=100, choices=period_choices)
    year = models.ForeignKey('core.AcademicYear', on_delete=models.CASCADE)
    term = models.ForeignKey('core.Term', on_delete=models.CASCADE)
    is_running = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.MyUser', on_delete=models.CASCADE, related_name='created_exams', null=True, blank=True)
    updated_by = models.ForeignKey('users.MyUser', on_delete=models.CASCADE, related_name='updated_exams', null=True, blank=True)
    class Meta:
        unique_together = ('name', 'year', 'term')
    
    def __str__(self):
        return self.name

class ExamSubjectConfiguration(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    max_score = models.IntegerField()
    paper_count = models.IntegerField(default=1)

    class Meta:
        unique_together = ('exam', 'subject')
    
    def __str__(self):
        return f"{self.exam} - {self.subject}"
    
    def get_score_rankings(self):
        """Get all score rankings for this configuration"""
        return self.scoreranking_set.all().order_by('min_score')

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Automatically create a paper if paper_count is 1 and no papers exist
        if self.paper_count == 1:
            if not ExamSubjectPaper.objects.filter(exam_subject=self).exists():
                ExamSubjectPaper.objects.create(
                    exam_subject=self,
                    name='Paper 1',
                    paper_number=1,
                    out_of=self.max_score
                )

class ScoreRanking(models.Model):
    choices = (
        ('EE','EE'),
        ('ME','ME'),
        ('AE','AE'),
        ('BE','BE')
    )
    subject = models.ForeignKey(ExamSubjectConfiguration, on_delete=models.CASCADE)
    min_score = models.PositiveIntegerField()
    max_score = models.PositiveIntegerField()
    grade = models.CharField(max_length=10, choices=choices)

    class Meta:
        unique_together = ('subject', 'min_score', 'max_score')
class ExamSubjectPaper(models.Model):
    choices = (
        ('P1', 'Paper 1'),
        ('P2', 'Paper 2'),
        ('P3', 'Paper 3'),
        ('Insha', 'Insha'),
        ('Composition', 'Composition'),
        
    )
    exam_subject = models.ForeignKey(ExamSubjectConfiguration, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    paper_number = models.IntegerField()
    out_of = models.IntegerField()

    class Meta:
        unique_together = ('exam_subject', 'name')
    
    def __str__(self):
        return f"{self.exam_subject} - {self.name}"

class ExamSUbjectScore(models.Model):
    paper = models.ForeignKey(ExamSubjectPaper, on_delete=models.CASCADE)
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE)
    class_id = models.ForeignKey('core.Class', on_delete=models.SET_NULL, null=True, blank=True)
    score = models.IntegerField()
    grade = models.CharField(max_length=10)

    class Meta:
        unique_together = ('paper', 'student')
    @property
    def subject(self):
        return self.paper.exam_subject.subject

    @property
    def exam(self):
        return self.paper.exam_subject.exam

    def save(self, *args, **kwargs):
        # Capture current class if not set
        if not self.class_id and hasattr(self.student, 'studentprofile'):
            self.class_id = self.student.studentprofile.class_id

        # Always check for ranking first if not in hardcoded grades
        if self.student.studentprofile.class_id and self.student.studentprofile.class_id.grade.name not in ['Grade 7', 'Grade 8', 'Grade 9']:
            ranking = ScoreRanking.objects.filter(
                subject=self.paper.exam_subject,
                min_score__lte=self.score,
                max_score__gte=self.score
            ).first()

            if ranking:
                self.grade = ranking.grade
                super().save(*args, **kwargs)
                return

        # Fallback logic for Grade 7/8/9 OR if no ranking found for others
        if self.score >= 70:
            self.grade = 'EE'
        elif self.score >= 60:
            self.grade = 'ME'
        elif self.score >= 50:
            self.grade = 'AE'
        else:
            self.grade = 'BE'

        super().save(*args, **kwargs)
    def __str__(self):
        return f"{self.student} - {self.score} - {self.paper.exam_subject.exam}"