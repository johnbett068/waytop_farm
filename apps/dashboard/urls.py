from django.urls import path
from . import views
app_name = "dashboard"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("orders/", views.orders, name="orders"),
    path("orders/<str:order_number>/", views.order_detail, name="order_detail"),
    path("production/", views.production, name="production"),
    path("production/source-lots/", views.source_lots, name="source_lots"),
    path("production/batches/", views.production_batches, name="production_batches"),
    path("production/batches/<str:batch_number>/", views.production_batch_detail, name="production_batch_detail"),
    path("production/tasks/", views.production_tasks, name="production_tasks"),
    path("production/exceptions/", views.production_exceptions, name="production_exceptions"),
    path("inventory/", views.inventory, name="inventory"),
    path("inventory/items/", views.inventory_items, name="inventory_items"),
    path("inventory/items/<str:item_code>/", views.inventory_item_detail, name="inventory_item_detail"),
    path("inventory/lots/", views.inventory_lots, name="inventory_lots"),
    path("inventory/movements/", views.inventory_movements, name="inventory_movements"),
    path("inventory/receiving/", views.inventory_receiving, name="inventory_receiving"),
    path("inventory/transfers/", views.inventory_transfers, name="inventory_transfers"),
    path("inventory/counts/", views.inventory_counts, name="inventory_counts"),
    path("inventory/adjustments/", views.inventory_adjustments, name="inventory_adjustments"),
    path("pos/", views.pos, name="pos"),
    path("pos/sale/", views.pos_sale, name="pos_sale"),
]
