from django.urls import path
from . import views

app_name = 'transport'

urlpatterns = [
    path('', views.transport_dashboard, name='dashboard'),
    path('route/add/', views.add_route, name='add-route'),
    path('route/edit/<int:route_id>/', views.edit_route, name='edit-route'),
    path('vehicle/add/', views.add_vehicle, name='add-vehicle'),
    path('assign/', views.assign_transport, name='assign-transport'),
    path('unassign/<int:assignment_id>/', views.delete_assignment, name='delete-assignment'),
]
