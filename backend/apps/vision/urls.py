from django.urls import path

from . import views

urlpatterns = [
    path("qr/", views.QRView.as_view(), name="vision-qr"),
    path("note/", views.NoteView.as_view(), name="vision-note"),
]
