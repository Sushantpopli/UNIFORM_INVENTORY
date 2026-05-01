from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # API (cascading dropdowns)
    path('api/products-for-school/', views.api_products_for_school, name='api_products_for_school'),
    path('api/sizes-for-school-product/', views.api_sizes_for_school_product, name='api_sizes_for_school_product'),
    path('api/stock-check/', views.api_stock_check, name='api_stock_check'),

    # Inventory
    path('inventory/', views.inventory_browse, name='inventory_browse'),
    path('inventory/low-stock/', views.low_stock_report, name='low_stock_report'),

    # Transactions
    path('stock-in/', views.stock_in, name='stock_in'),
    path('sale/', views.sale, name='sale'),
    path('return/', views.return_item, name='return_item'),
    path('exchange/', views.exchange, name='exchange'),

    # Manufacturing
    path('manufacturing/', views.manufacturing_list, name='manufacturing_list'),
    path('manufacturing/create/', views.manufacturing_create, name='manufacturing_create'),
    path('manufacturing/<int:pk>/receive/', views.manufacturing_receive, name='manufacturing_receive'),
]
