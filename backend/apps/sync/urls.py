from django.urls import path

from . import views

urlpatterns = [
    path("replay/", views.ReplayView.as_view(), name="sync-replay"),
]
