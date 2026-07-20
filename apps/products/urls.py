from django.urls import path
from . import views

app_name = "products"
urlpatterns = [
    path("", views.shop, name="shop"),
    path("categories/", views.categories, name="categories"),
    path("category/<slug:slug>/", views.category, name="category"),
    path("search/", views.search, name="search"),
    path("<slug:slug>/", views.product_detail, name="product_detail"),
]
