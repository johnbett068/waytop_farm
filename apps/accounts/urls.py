from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views, customer_views

app_name = "accounts"
urlpatterns = [
    path("create-account/", customer_views.register, name="customer_register"),
    path("sign-in/", customer_views.CustomerLoginView.as_view(), name="customer_login"),
    path("sign-out/", customer_views.CustomerLogoutView.as_view(), name="customer_logout"),
    path("my-account/", customer_views.profile, name="customer_profile"),
    path("login/", views.StaffLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
]
