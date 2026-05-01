from django.db.models import F
from schools.models import SchoolProduct


def global_stats(request):
    """Makes low_stock_count available in every template for the sidebar badge."""
    try:
        low_stock_count = SchoolProduct.objects.filter(stock__lte=F('low_stock_threshold')).count()
    except Exception:
        low_stock_count = 0
    return {'low_stock_count': low_stock_count}
