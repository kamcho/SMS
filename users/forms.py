from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import MyUser

class AdminUserCreationForm(UserCreationForm):
    class Meta:
        model = MyUser
        fields = ('email', 'role', 'school')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Include all roles
        self.fields['role'].choices = MyUser.ROLE_CHOICES
        
        # Make role required
        self.fields['role'].required = True
        
        # Make school optional by default, we'll enforce it in clean()
        self.fields['school'].required = False
        
        # Add client-side toggle logic or handle in clean() 
        # For now, let's keep it required unless we want to allow nulls generally
        # The user just asked to ALLOW Guardian role creation.
        
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        school = cleaned_data.get('school')
        
        if role == 'Guardian':
            # School is not strictly required for Guardians
            pass
        elif not school:
            self.add_error('school', 'This field is required for the selected role.')
            
        return cleaned_data
