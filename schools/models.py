from django.db import models
from products.models import Product
from sizes.models import Size


class School(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        ordering = ['name']


class SchoolProduct(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='school_products')
    size = models.ForeignKey(Size, on_delete=models.CASCADE, related_name='school_products')
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    stock = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=5)

    class Meta:
        unique_together = ('school', 'product', 'size')
        ordering = ['school__name', 'product__name', 'size__size_value']

    def __str__(self):
        return f"{self.school.name} — {self.product.name} ({self.size.size_value})"

    @property
    def is_low_stock(self):
        return self.stock <= self.low_stock_threshold

    @property
    def stock_status(self):
        if self.stock == 0:
            return 'out'
        if self.stock <= self.low_stock_threshold:
            return 'low'
        return 'ok'