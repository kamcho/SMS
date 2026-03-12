from django.urls import path
from .views import FeesAnalyticsView, PaymentListView

app_name = 'accounts'

urlpatterns = [
    path('analytics/', FeesAnalyticsView.as_view(), name='fees-analytics'),
    path('payments/', PaymentListView.as_view(), name='payments-list'),
]
