from django.urls import path

from . import views

urlpatterns = [
    path("lessons/", views.LessonListView.as_view(), name="lesson-list"),
    path("lessons/<str:lesson_id>/quiz/", views.QuizView.as_view(), name="lesson-quiz"),
]
