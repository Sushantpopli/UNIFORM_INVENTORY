from django.contrib import admin
from .models import Size


@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ['product', 'size_value']
    list_filter = ['product']
    search_fields = ['size_value']