from django.urls import path

from . import views

urlpatterns = [
    path("text/", views.VoiceTextView.as_view(), name="voice-text"),
    path("confirm/", views.VoiceConfirmView.as_view(), name="voice-confirm"),
    path("query/", views.VoiceQueryView.as_view(), name="voice-query"),
    path("result/<str:task_id>/", views.VoiceResultView.as_view(), name="voice-result"),
]
