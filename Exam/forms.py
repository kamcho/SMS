from django import forms
from .models import Exam, ExamSubjectConfiguration, ExamSubjectPaper, ScoreRanking
from core.models import AcademicYear, Term
from .models import Subject

class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['name', 'period', 'year', 'term']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all',
                'placeholder': 'Enter exam name (e.g., Mid-Term Exams, Final Exams)'
            }),
            'period': forms.Select(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all appearance-none cursor-pointer'
            }),
            'year': forms.Select(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all appearance-none cursor-pointer'
            }),
            'term': forms.Select(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all appearance-none cursor-pointer'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['period'].empty_label = "Select Period"
        self.fields['year'].empty_label = "Select Academic Year"
        self.fields['term'].empty_label = "Select Term"
        
        # Filter years and terms to only show active ones
        self.fields['year'].queryset = AcademicYear.objects.filter(is_active=True).order_by('-start_date')
        self.fields['term'].queryset = Term.objects.filter(is_active=True).order_by('name')


class ExamSubjectConfigurationForm(forms.ModelForm):
    exam = forms.ModelChoiceField(
        queryset=Exam.objects.all().order_by('-year__start_date', 'term__name', 'name'),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all appearance-none cursor-pointer'
        })
    )
    
    class Meta:
        model = ExamSubjectConfiguration
        fields = ['exam', 'subject', 'max_score', 'paper_count']
        widgets = {
            'subject': forms.Select(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all appearance-none cursor-pointer'
            }),
            'max_score': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all',
                'placeholder': 'Maximum score (e.g., 100)',
                'min': '1',
                'max': '999'
            }),
            'paper_count': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all',
                'placeholder': 'Number of papers (e.g., 1, 2, 3)',
                'min': '1',
                'max': '10'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        grade = kwargs.pop('grade', None)
        exam_id = kwargs.pop('exam_id', None)
        super().__init__(*args, **kwargs)
        self.fields['exam'].empty_label = "Select Exam"
        self.fields['subject'].empty_label = "Select Subject"
        
        # Filter subjects by grade if provided
        if grade:
            subjects_queryset = Subject.objects.filter(grade=grade).order_by('name')
            
            # Further exclude subjects that already have configurations for this exam
            if exam_id:
                configured_subject_ids = ExamSubjectConfiguration.objects.filter(
                    exam_id=exam_id,
                    subject__grade=grade
                ).values_list('subject_id', flat=True)
                subjects_queryset = subjects_queryset.exclude(id__in=configured_subject_ids)
            
            self.fields['subject'].queryset = subjects_queryset


class ExamSubjectPaperForm(forms.ModelForm):
    class Meta:
        model = ExamSubjectPaper
        fields = ['name', 'paper_number', 'out_of']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all',
                'placeholder': 'Paper type (e.g., Paper 1, Paper 2, Insha, Composition, Practical, etc.)',
                'list': 'paper-types'
            }),
            'paper_number': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all',
                'placeholder': 'Paper number (e.g., 1, 2, 3)',
                'min': '1',
                'max': '10'
            }),
            'out_of': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all',
                'placeholder': 'Maximum marks (e.g., 100)',
                'min': '1',
                'max': '999'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # No need to set choices since we're using TextInput with datalist


class ScoreRankingForm(forms.ModelForm):
    class Meta:
        model = ScoreRanking
        fields = ['grade', 'min_score', 'max_score']
        widgets = {
            'grade': forms.Select(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all appearance-none cursor-pointer'
            }),
            'min_score': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all',
                'placeholder': 'Minimum score',
                'min': '0'
            }),
            'max_score': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all',
                'placeholder': 'Maximum score',
                'min': '0'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grade'].empty_label = "Select Grade"
