from django.urls import path

from . import views

urlpatterns = [
    path("check/", views.ScamCheckView.as_view(), name="fraud-check"),
    path("history/", views.ScamHistoryView.as_view(), name="fraud-history"),
    path("report/", views.ScamReportView.as_view(), name="fraud-report"),
]
