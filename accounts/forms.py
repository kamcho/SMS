from django import forms
from .models import FeeStructure
from core.models import Grade, Term, School

class FeeStructureForm(forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = ['term', 'school', 'student_type', 'amount', 'grade']
        widgets = {
            'term': forms.Select(attrs={'class': 'w-full px-4 py-3 bg-white border border-slate-200 rounded-2xl text-sm font-medium text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all placeholder:text-slate-400 shadow-sm'}),
            'school': forms.Select(attrs={'class': 'w-full px-4 py-3 bg-white border border-slate-200 rounded-2xl text-sm font-medium text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all placeholder:text-slate-400 shadow-sm'}),
            'student_type': forms.Select(attrs={'class': 'w-full px-4 py-3 bg-white border border-slate-200 rounded-2xl text-sm font-medium text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all placeholder:text-slate-400 shadow-sm'}),
            'amount': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 bg-white border border-slate-200 rounded-2xl text-sm font-medium text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all placeholder:text-slate-400 shadow-sm', 'min': 0}),
            'grade': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['term'].queryset = Term.objects.all()
        self.fields['grade'].queryset = Grade.objects.all()
        self.fields['school'].queryset = School.objects.all()


from .models import AdditionalCharges

class AdditionalChargesForm(forms.ModelForm):
    class Meta:
        model = AdditionalCharges
        fields = ['name', 'amount', 'term', 'school', 'grades']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-3 bg-white border border-slate-200 rounded-2xl text-sm font-medium text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all placeholder:text-slate-400 shadow-sm', 'placeholder': 'e.g. Lab Fees'}),
            'amount': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 bg-white border border-slate-200 rounded-2xl text-sm font-medium text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all placeholder:text-slate-400 shadow-sm', 'min': 0}),
            'term': forms.Select(attrs={'class': 'w-full px-4 py-3 bg-white border border-slate-200 rounded-2xl text-sm font-medium text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all placeholder:text-slate-400 shadow-sm'}),
            'school': forms.Select(attrs={'class': 'w-full px-4 py-3 bg-white border border-slate-200 rounded-2xl text-sm font-medium text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all placeholder:text-slate-400 shadow-sm'}),
            'grades': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['school'].queryset = School.objects.all()
        self.fields['term'].queryset = Term.objects.all()
        self.fields['grades'].queryset = Grade.objects.all()


from .models import AuxiliaryServiceType

class AuxiliaryServiceTypeForm(forms.ModelForm):
    class Meta:
        model = AuxiliaryServiceType
        fields = ['name', 'school', 'grades', 'amount', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-3 bg-white border border-slate-200 rounded-2xl text-sm font-medium text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all placeholder:text-slate-400 shadow-sm', 'placeholder': 'e.g. Remedial, School Trip'}),
            'school': forms.Select(attrs={'class': 'w-full px-4 py-3 bg-white border border-slate-200 rounded-2xl text-sm font-medium text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all placeholder:text-slate-400 shadow-sm'}),
            'amount': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 bg-white border border-slate-200 rounded-2xl text-sm font-medium text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all placeholder:text-slate-400 shadow-sm', 'min': 0, 'placeholder': 'Default charge per student'}),
            'description': forms.Textarea(attrs={'class': 'w-full px-4 py-3 bg-white border border-slate-200 rounded-2xl text-sm font-medium text-slate-700 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all placeholder:text-slate-400 shadow-sm', 'rows': 2, 'placeholder': 'Optional description'}),
            'grades': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['school'].queryset = School.objects.all()
        self.fields['grades'].queryset = Grade.objects.all()
