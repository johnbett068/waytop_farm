"""Project URL configuration for Waytop Farm."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(("apps.core.urls", "core"), namespace="core")),
    path("accounts/", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path("products/", include(("apps.products.urls", "products"), namespace="products")),
    path("cart/", include(("apps.cart.urls", "cart"), namespace="cart")),
    path("wishlist/", include(("apps.wishlist.urls", "wishlist"), namespace="wishlist")),
    path("orders/", include(("apps.orders.urls", "orders"), namespace="orders")),
    path("payments/", include(("apps.payments.urls", "payments"), namespace="payments")),
    path("branches/", include(("apps.branches.urls", "branches"), namespace="branches")),
    path("blog/", include(("apps.blog.urls", "blog"), namespace="blog")),
    path("reviews/", include(("apps.reviews.urls", "reviews"), namespace="reviews")),
    path("contact/", include(("apps.contact.urls", "contact"), namespace="contact")),
    path("dashboard/", include(("apps.dashboard.urls", "dashboard"), namespace="dashboard")),
    path("notifications/", include(("apps.notifications.urls", "notifications"), namespace="notifications")),
]
