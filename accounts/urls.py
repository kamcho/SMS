from django.urls import path
from . import views
from .views import FeesAnalyticsView, PaymentListView

app_name = 'accounts'

urlpatterns = [
    path('analytics/', FeesAnalyticsView.as_view(), name='fees-analytics'),
    path('payments/', PaymentListView.as_view(), name='payments-list'),
    
    # Payroll
    path('payroll/', views.PayrollListView.as_view(), name='payroll-list'),
    path('payroll/pay/<int:staff_id>/', views.process_payroll_payment, name='process-payroll-payment'),
    path('payroll/config/<int:staff_id>/', views.update_salary_config, name='update-salary-config'),
]
