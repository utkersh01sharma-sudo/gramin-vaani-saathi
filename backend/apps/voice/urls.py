from django.urls import path

from . import views

urlpatterns = [
    path("text/", views.VoiceTextView.as_view(), name="voice-text"),
    path("confirm/", views.VoiceConfirmView.as_view(), name="voice-confirm"),
]
