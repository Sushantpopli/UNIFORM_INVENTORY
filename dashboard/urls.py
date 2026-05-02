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
    path('inventory/update-price/<int:pk>/', views.inventory_update_price, name='inventory_update_price'),

    # Transactions
    path('stock-in/', views.stock_in, name='stock_in'),
    path('sale/', views.sale, name='sale'),
    path('return/', views.return_item, name='return_item'),
    path('exchange/', views.exchange, name='exchange'),

    # API
    path('api/barcode-lookup/', views.api_barcode_lookup, name='api_barcode_lookup'),

    # Labels
    path('labels/', views.labels_setup, name='labels_setup'),
    path('labels/print/', views.labels_print, name='labels_print'),

    # Transaction History
    path('history/', views.transaction_history, name='transaction_history'),
    path('history/void/<int:pk>/', views.void_transaction, name='void_transaction'),

    # Billing System
    path('billing/new/', views.bill_create, name='bill_create'),
    path('billing/<int:pk>/print/', views.bill_print, name='bill_print'),
    path('billing/history/', views.bill_history, name='bill_history'),
    path('summary/', views.daily_summary, name='daily_summary'),

    # Manufacturing
    path('manufacturing/', views.manufacturing_list, name='manufacturing_list'),
    path('manufacturing/create/', views.manufacturing_create, name='manufacturing_create'),
    path('manufacturing/<int:pk>/receive/', views.manufacturing_receive, name='manufacturing_receive'),

    # Setup / Master Data
    path('setup/', views.setup_home, name='setup_home'),
    path('setup/school/add/', views.setup_school_add, name='setup_school_add'),
    path('setup/school/<int:pk>/delete/', views.setup_school_delete, name='setup_school_delete'),
    path('setup/product/add/', views.setup_product_add, name='setup_product_add'),
    path('setup/product/<int:pk>/delete/', views.setup_product_delete, name='setup_product_delete'),
    path('setup/size/add/', views.setup_size_add, name='setup_size_add'),
    path('setup/size/<int:pk>/delete/', views.setup_size_delete, name='setup_size_delete'),
    path('setup/link/add/', views.setup_link_add, name='setup_link_add'),
    path('setup/link/bulk/', views.setup_link_bulk, name='setup_link_bulk'),
]
