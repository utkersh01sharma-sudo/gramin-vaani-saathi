from django.urls import path

from . import views

urlpatterns = [
    path("", views.SchemeListView.as_view(), name="scheme-list"),
    path("search/", views.SchemeSearchView.as_view(), name="scheme-search"),
    path("check/", views.SchemeCheckView.as_view(), name="scheme-check"),
]
