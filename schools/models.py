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
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_products', null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='school_products')
    size = models.ForeignKey(Size, on_delete=models.CASCADE, related_name='school_products')
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    stock = models.IntegerField(default=0, db_index=True)
    low_stock_threshold = models.IntegerField(default=5)
    sku_code = models.CharField(max_length=30, unique=True, blank=True, null=True, db_index=True)

    class Meta:
        unique_together = ('school', 'product', 'size')
        ordering = ['school__name', 'product__name', 'size__size_value']
        indexes = [
            models.Index(fields=['school', 'product', 'size'], name='idx_school_product_size'),
            models.Index(fields=['school', 'product'], name='idx_school_product'),
            models.Index(fields=['stock'], name='idx_stock_level'),
        ]

    def __str__(self):
        if self.school:
            return f"{self.school.name} — {self.product.name} ({self.size.size_value})"
        return f"General Item — {self.product.name} ({self.size.size_value})"

    def save(self, *args, **kwargs):
        # Auto-generate SKU code if not set
        if not self.sku_code and self.pk:
            self.sku_code = f"HSD{self.pk:06d}"
        super().save(*args, **kwargs)
        if not self.sku_code:
            self.sku_code = f"HSD{self.pk:06d}"
            SchoolProduct.objects.filter(pk=self.pk).update(sku_code=self.sku_code)

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