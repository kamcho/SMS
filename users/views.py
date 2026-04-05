from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from .models import MyUser
from .forms import AdminUserCreationForm, UserUpdateForm

class UserCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = MyUser
    form_class = AdminUserCreationForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('users:create-user')

    def test_func(self):
        # Only Admins, Superusers or Receptionists can create users here
        return self.request.user.role in ['Admin', 'Receptionist'] or self.request.user.is_superuser

    def form_valid(self, form):
        if self.request.user.school:
            form.instance.school = self.request.user.school
        messages.success(self.request, f"User {form.cleaned_data.get('email')} created successfully.")
        return super().form_valid(form)


class UserProfileView(LoginRequiredMixin, DetailView):
    model = MyUser
    template_name = 'users/user_profile.html'
    context_object_name = 'user_profile'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_edit'] = (
            self.request.user.is_superuser or 
            self.request.user.role == 'Admin' or 
            (self.request.user == self.object and self.request.user.role == 'Admin')
        )
        return context


class UserUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = MyUser
    form_class = UserUpdateForm
    template_name = 'users/user_update.html'
    success_url = reverse_lazy('users:create-user')

    def test_func(self):
        # Only Admins, Superusers or Receptionists can update users here
        return self.request.user.role in ['Admin', 'Receptionist'] or self.request.user.is_superuser

    def form_valid(self, form):
        messages.success(self.request, f"User {form.cleaned_data.get('email')} updated successfully.")
        return super().form_valid(form)

from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, user_passes_test

@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def quick_update_user_role(request):
    """Allows superusers to quickly switch their own identity for testing purposes."""
    user = request.user
    role = request.POST.get('role')
    flag = request.POST.get('flag')
    
    if role:
        user.role = role
        messages.success(request, f"Role switched to {role}")
    
    if flag:
        if flag == 'is_headteacher':
            user.is_headteacher = not user.is_headteacher
            messages.success(request, f"Headteacher status: {user.is_headteacher}")
        elif flag == 'is_exam_manager':
            user.is_exam_manager = not user.is_exam_manager
            messages.success(request, f"Exam Manager status: {user.is_exam_manager}")
        elif flag == 'is_exam_officer':
            user.is_exam_officer = not user.is_exam_officer
            messages.success(request, f"Exam Officer status: {user.is_exam_officer}")
        elif flag == 'is_staff':
            user.is_staff = not user.is_staff
            messages.success(request, f"Staff status: {user.is_staff}")
            
    user.save()
    return redirect(request.META.get('HTTP_REFERER', 'core:dashboard'))
