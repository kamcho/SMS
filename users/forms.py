from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import MyUser

class AdminUserCreationForm(UserCreationForm):
    class Meta:
        model = MyUser
        fields = ('email', 'role', 'school')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter role choices to exclude 'Guardian'
        all_roles = MyUser.ROLE_CHOICES
        filtered_roles = [role for role in all_roles if role[0] != 'Guardian']
        self.fields['role'].choices = filtered_roles
        
        # Make role and school required for this admin-led creation
        self.fields['role'].required = True
        self.fields['school'].required = True
