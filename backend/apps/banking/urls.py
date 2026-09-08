from django.urls import path

from . import views

urlpatterns = [
    path("account/", views.AccountView.as_view(), name="account"),
    path("transfer/", views.TransferView.as_view(), name="transfer"),
    path("transactions/", views.TransactionListView.as_view(), name="transactions"),
]
