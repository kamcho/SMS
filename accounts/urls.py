from django.urls import path
from . import views
from .views import FeesAnalyticsView, PaymentListView
from . import mpesa_views

app_name = 'accounts'

urlpatterns = [
    path('analytics/', FeesAnalyticsView.as_view(), name='fees-analytics'),
    path('payment-history/', PaymentListView.as_view(), name='payment-history'),
    
    # Payroll
    path('payroll/', views.PayrollListView.as_view(), name='payroll-list'),
    path('payroll/pay/<int:staff_id>/', views.process_payroll_payment, name='process-payroll-payment'),
    path('payroll/config/<int:staff_id>/', views.update_salary_config, name='update-salary-config'),
    path('migrate-fees/', views.MigrateFeesView.as_view(), name='migrate-fees'),
    path('migrate-term/', views.MigrateTermView.as_view(), name='migrate-term'),
    path('fee-structure/<int:pk>/', views.FeeStructureDetailView.as_view(), name='fee-structure-detail'),
    
    # M-Pesa Integration
    path('mpesa/test/', mpesa_views.mpesa_test_view, name='mpesa-test'),
    path('mpesa/stk-push/', mpesa_views.MpesaSTKPushView.as_view(), name='mpesa-stk-push'),
    path('initiate-stk-push/', mpesa_views.MpesaSTKPushView.as_view(), name='initiate-stk-push'),
    path('mpesa/pull/', mpesa_views.MpesaB2CView.as_view(), name='mpesa-pull'),
    path('mpesa/callback/', mpesa_views.mpesa_callback, name='mpesa-callback'),
    path('mpesa/result/', mpesa_views.mpesa_result, name='mpesa-result'),
    path('mpesa/timeout/', mpesa_views.mpesa_timeout, name='mpesa-timeout'),
    path('mpesa/transaction/<uuid:transaction_id>/', mpesa_views.transaction_status, name='mpesa-transaction-status'),
    path('mpesa/history/', mpesa_views.transaction_history, name='mpesa-transaction-history'),
    
    # Payments
    path('payments/', views.payments_list_view, name='payments-list'),
    # Reconciliation APIs
    path('reconciliation/student/<int:student_id>/', views.get_student_by_id, name='get-student-by-id'),
    path('reconciliation/process-payment/', views.process_pulled_payment, name='process-pulled-payment'),
]
