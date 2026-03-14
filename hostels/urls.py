from django.urls import path
from . import views

app_name = 'hostels'

urlpatterns = [
    path('', views.hostel_dashboard, name='dashboard'),
    path('setup/', views.setup_hostel, name='setup'),
    path('allocate/', views.allocate_bed, name='allocate'),
]
