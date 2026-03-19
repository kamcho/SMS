from django import forms
from .models import MyUser

class AdminUserCreationForm(forms.ModelForm):
    class Meta:
        model = MyUser
        fields = ('email', 'first_name', 'last_name', 'password', 'role', 'school', 'phone_number', 'is_active', 'is_exam_manager', 'is_exam_officer', 'is_headteacher')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Include all roles
        self.fields['role'].choices = MyUser.ROLE_CHOICES
        
        # Make role required
        self.fields['role'].required = True
        
        # Make school optional by default, we'll enforce it in clean()
        self.fields['school'].required = False
        
        # Make phone number required
        self.fields['phone_number'].required = True
        
        # Make name fields required
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        
        # Add password field
        self.fields['password'] = forms.CharField(
            label='Password',
            widget=forms.PasswordInput,
            required=True
        )
        
        # Add account status field
        self.fields['is_active'] = forms.BooleanField(
            label='Account Status',
            widget=forms.CheckboxInput,
            required=False,
            initial=True
        )
        
        # Add exam manager field
        self.fields['is_exam_manager'] = forms.BooleanField(
            label='Exam Manager',
            widget=forms.CheckboxInput,
            required=False,
            initial=False
        )
        
        # Add exam officer field
        self.fields['is_exam_officer'] = forms.BooleanField(
            label='Exam Officer',
            widget=forms.CheckboxInput,
            required=False,
            initial=False
        )

        # Add head teacher field
        self.fields['is_headteacher'] = forms.BooleanField(
            label='Head Teacher',
            widget=forms.CheckboxInput,
            required=False,
            initial=False
        )
        
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
        if role != 'Teacher':
            cleaned_data['is_exam_manager'] = False
            cleaned_data['is_exam_officer'] = False
            cleaned_data['is_headteacher'] = False
        elif not school:
            self.add_error('school', 'This field is required for the selected role.')
            
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = MyUser
        fields = ('email', 'first_name', 'last_name', 'password', 'role', 'school', 'phone_number', 'is_active', 'is_exam_manager', 'is_exam_officer', 'is_headteacher')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Include all roles
        self.fields['role'].choices = MyUser.ROLE_CHOICES
        
        # Make role required
        self.fields['role'].required = True
        
        # Make school optional by default, we'll enforce it in clean()
        self.fields['school'].required = False
        
        # Make phone number required
        self.fields['phone_number'].required = True
        
        # Make name fields required
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        
        # Add password field
        self.fields['password'] = forms.CharField(
            label='Password',
            widget=forms.PasswordInput,
            required=False  # Make optional for update form
        )
        
        # Add account status field
        self.fields['is_active'] = forms.BooleanField(
            label='Account Status',
            widget=forms.CheckboxInput,
            required=False
        )
        
        # Add exam manager field
        self.fields['is_exam_manager'] = forms.BooleanField(
            label='Exam Manager',
            widget=forms.CheckboxInput,
            required=False
        )
        
        # Add exam officer field
        self.fields['is_exam_officer'] = forms.BooleanField(
            label='Exam Officer',
            widget=forms.CheckboxInput,
            required=False
        )
        
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        school = cleaned_data.get('school')
        
        if role == 'Guardian':
            # School is not strictly required for Guardians
            pass
        if role != 'Teacher':
            cleaned_data['is_exam_manager'] = False
            cleaned_data['is_exam_officer'] = False
            cleaned_data['is_headteacher'] = False
        elif not school:
            self.add_error('school', 'This field is required for the selected role.')
            
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:  # Only update password if provided
            user.set_password(password)
        if commit:
            user.save()
        return user
