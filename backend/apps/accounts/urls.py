from django.urls import path

from . import views

urlpatterns = [
    path("otp/request/", views.OtpRequestView.as_view(), name="otp-request"),
    path("otp/verify/", views.OtpVerifyView.as_view(), name="otp-verify"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("me/", views.MeView.as_view(), name="me"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("contacts/", views.ContactListView.as_view(), name="contacts"),
]
