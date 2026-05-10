from django.db.models import F
from django.core.cache import cache
from schools.models import SchoolProduct


def global_stats(request):
    """Makes low_stock_count available in every template for the sidebar badge."""
    low_stock_count = cache.get('low_stock_count')
    if low_stock_count is None:
        try:
            low_stock_count = SchoolProduct.objects.filter(stock__lte=F('low_stock_threshold')).count()
            cache.set('low_stock_count', low_stock_count, 300) # Cache for 5 minutes
        except Exception:
            low_stock_count = 0
    return {'low_stock_count': low_stock_count}
