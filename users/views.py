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
        # Only Admins or superusers can create users here
        return self.request.user.role == 'Admin' or self.request.user.is_superuser

    def form_valid(self, form):
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
        # Only Admins or superusers can update users here
        return self.request.user.role == 'Admin' or self.request.user.is_superuser

    def form_valid(self, form):
        messages.success(self.request, f"User {form.cleaned_data.get('email')} updated successfully.")
        return super().form_valid(form)
