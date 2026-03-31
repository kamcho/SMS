from django import forms
from .models import Student, StudentProfile, School, AcademicYear, Term, Grade, Class, ExamMode, AttendanceSession, StudentAttendance
from Exam.models import Exam, Subject
from accounts.models import Payment

class BaseStyledForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({
                    'class': 'w-5 h-5 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500 transition-all cursor-pointer'
                })
            else:
                field.widget.attrs.update({
                    'class': 'w-full px-4 py-3 bg-white border border-slate-200 rounded-2xl text-sm font-medium text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all placeholder:text-slate-400 shadow-sm'
                })

class StudentForm(BaseStyledForm):
    class Meta:
        model = Student
        fields = ['first_name', 'middle_name', 'last_name', 'date_of_birth', 'joined_date', 'gender', 'location', 'fee_category']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'joined_date': forms.DateInput(attrs={'type': 'date'}),
            'gender': forms.Select(choices=Student.GENDERS),
            'fee_category': forms.Select(choices=Student.FEE_CATEGORIES),
        }

class StudentProfileForm(BaseStyledForm):
    class Meta:
        model = StudentProfile
        fields = ['class_id', 'school', 'fee_balance', 'discipline']
        widgets = {
            'fee_balance': forms.NumberInput(attrs={'min': 0, 'placeholder': '0'}),
            'discipline': forms.NumberInput(attrs={'min': 0, 'max': 100}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['school'].queryset = School.objects.all()
        self.fields['school'].empty_label = "Select School"
        self.fields['fee_balance'].label = "Opening Balance"
        # Show grade alongside class name in the dropdown, e.g. "East A (Grade 4)"
        self.fields['class_id'].queryset = Class.objects.all().select_related('grade')
        self.fields['class_id'].label_from_instance = lambda obj: f"{obj.name} ({obj.grade.name})"


class AcademicYearForm(BaseStyledForm):
    class Meta:
        model = AcademicYear
        fields = ['start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }


class TermForm(BaseStyledForm):
    class Meta:
        model = Term
        fields = ['name', 'closing_date', 'opening_date']
        widgets = {
            'closing_date': forms.DateInput(attrs={'type': 'date'}),
            'opening_date': forms.DateInput(attrs={'type': 'date'}),
        }


class GradeForm(BaseStyledForm):
    class Meta:
        model = Grade
        fields = ['name']


class ClassForm(BaseStyledForm):
    class Meta:
        model = Class
        fields = ['name', 'school', 'grade']
        widgets = {
            'school': forms.Select(),
            'grade': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['school'].queryset = School.objects.all()
        self.fields['school'].empty_label = "Select School"
        self.fields['grade'].queryset = Grade.objects.all()
        self.fields['grade'].empty_label = "Select Grade"


class StreamUpdateForm(BaseStyledForm):
    class Meta:
        model = Class
        fields = ['name']


class ExamForm(BaseStyledForm):
    class Meta:
        model = Exam
        fields = ['name', 'year', 'term']
        widgets = {
            'year': forms.Select(),
            'term': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['year'].queryset = AcademicYear.objects.all()
        self.fields['year'].empty_label = "Select Academic Year"
        self.fields['term'].queryset = Term.objects.all()
        self.fields['term'].empty_label = "Select Term"


class ExamModeForm(BaseStyledForm):
    class Meta:
        model = ExamMode
        fields = ['active']
        widgets = {
            'active': forms.CheckboxInput(),
        }


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'method', 'reference', 'date_paid']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold focus:outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all',
                'placeholder': 'Enter amount',
                'min': '0',
                'step': '0.01'
            }),
            'method': forms.Select(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold focus:outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all appearance-none cursor-pointer'
            }),
            'reference': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold focus:outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all',
                'placeholder': 'Enter payment reference ID'
            }),
            'date_paid': forms.DateInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold focus:outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all',
                'type': 'date'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reference'].required = True
        self.fields['date_paid'].required = True


class AttendanceSessionForm(forms.ModelForm):
    class Meta:
        model = AttendanceSession
        fields = ['class_id', 'date']
        widgets = {
            'class_id': forms.Select(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold focus:outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all appearance-none cursor-pointer'
            }),
            'date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-xs font-bold focus:outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all',
                'type': 'date'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter classes based on user role
        if user and not user.is_superuser:
            try:
                user_school = user.profile.school
                self.fields['class_id'].queryset = Class.objects.filter(school=user_school).select_related('grade', 'school')
            except AttributeError:
                self.fields['class_id'].queryset = Class.objects.all().select_related('grade', 'school')
        else:
            self.fields['class_id'].queryset = Class.objects.all().select_related('grade', 'school')
        
        self.fields['class_id'].empty_label = "Select Class"
        self.fields['date'].required = True


class StudentAttendanceForm(forms.ModelForm):
    class Meta:
        model = StudentAttendance
        fields = ['status', 'remarks']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold focus:outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all appearance-none cursor-pointer'
            }),
            'remarks': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold focus:outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all',
                'placeholder': 'Optional remarks'
            }),
        }
