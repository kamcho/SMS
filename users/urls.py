from django.urls import path
from django.contrib.auth import views as auth_views
from .views import UserCreateView

app_name = 'users'

urlpatterns = [
    path('create-user/', UserCreateView.as_view(), name='create-user'),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
