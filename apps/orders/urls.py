from django.urls import path
from . import views
app_name = "orders"
urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("success/", views.success, name="success"),
    path("track/", views.tracking, name="tracking"),
    path("history/", views.history, name="history"),
]
