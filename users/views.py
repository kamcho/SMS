from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from .models import MyUser
from .forms import AdminUserCreationForm

class UserCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = MyUser
    form_class = AdminUserCreationForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('users:create-user')

    def test_func(self):
        # Only Admins or superusers can create users here
        return self.request.user.role == 'Admin' or self.request.user.is_superuser

    def form_valid(self, form):
        messages.success(self.request, f"User {form.cleaned_data.get('email')} created successfully.")
        return super().form_valid(form)
