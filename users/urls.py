from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    UserCreateView, UserProfileView, UserUpdateView,
    quick_update_user_role
)

app_name = 'users'

urlpatterns = [
    path('create-user/', UserCreateView.as_view(), name='create-user'),
    path('profile/<int:pk>/', UserProfileView.as_view(), name='user-profile'),
    path('profile/<int:pk>/update/', UserUpdateView.as_view(), name='update-user'),
    path('quick-update-role/', quick_update_user_role, name='quick-update-role'),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
