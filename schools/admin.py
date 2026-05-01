from django.contrib import admin
from django.utils.html import format_html
from .models import School, SchoolProduct


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']
    search_fields = ['name', 'code']


@admin.register(SchoolProduct)
class SchoolProductAdmin(admin.ModelAdmin):
    list_display = ['school', 'product', 'size', 'stock', 'low_stock_threshold', 'stock_badge']
    list_filter = ['school', 'product']
    search_fields = ['school__name', 'product__name', 'size__size_value']
    list_select_related = ['school', 'product', 'size']

    def stock_badge(self, obj):
        if obj.stock == 0:
            color = '#ef4444'
            label = 'OUT'
        elif obj.is_low_stock:
            color = '#f59e0b'
            label = 'LOW'
        else:
            color = '#10b981'
            label = 'OK'
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">{}</span>',
            color, label
        )
    stock_badge.short_description = 'Status'