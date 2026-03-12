from django.urls import path
from . import views

app_name = 'communication'

urlpatterns = [
    path('', views.notification_dashboard, name='dashboard'),
    path('delete/<int:pk>/', views.delete_notification, name='delete-notification'),
    path('payments/', views.payment_notifications_list, name='payment-notifications'),
]
