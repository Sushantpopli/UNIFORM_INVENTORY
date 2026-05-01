from django.contrib import admin
from .models import StockTransaction, ManufacturingOrder


@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'school_product', 'transaction_type', 'quantity', 'note']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['school_product__school__name', 'school_product__product__name']
    list_select_related = ['school_product__school', 'school_product__product', 'school_product__size']
    readonly_fields = ['created_at']


@admin.register(ManufacturingOrder)
class ManufacturingOrderAdmin(admin.ModelAdmin):
    list_display = ['school_product', 'quantity_ordered', 'quantity_received', 'status', 'ordered_at', 'expected_at']
    list_filter = ['status']
    search_fields = ['school_product__school__name', 'school_product__product__name']
    list_select_related = ['school_product__school', 'school_product__product', 'school_product__size']
