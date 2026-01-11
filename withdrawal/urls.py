from django.urls import path
from .views import (
    WithdrawalListCreateView,
    WithdrawalSettingsView,
    JayapayInitiateView,
    JayapayCallbackView,
    WithdrawalTransactionsListView,
)

urlpatterns = [
    path('', WithdrawalListCreateView.as_view(), name='withdrawal-list-create'),
    path('settings/', WithdrawalSettingsView.as_view(), name='withdrawal-settings'),
    path('jayapay/initiate/<int:pk>/', JayapayInitiateView.as_view(), name='withdrawal-jayapay-initiate'),
    path('jayapay/callback/', JayapayCallbackView.as_view(), name='withdrawal-jayapay-callback'),
    path('transactions/', WithdrawalTransactionsListView.as_view(), name='withdrawal-transactions'),
]