from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from products.models import Product
from sizes.models import Size


class School(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(Lower('code'), name='uniq_school_code_ci'),
        ]


class SchoolProduct(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_products', null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='school_products')
    size = models.ForeignKey(Size, on_delete=models.CASCADE, related_name='school_products')
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    stock = models.IntegerField(default=0, db_index=True)
    low_stock_threshold = models.IntegerField(default=5)
    sku_code = models.CharField(max_length=30, unique=True, blank=True, null=True, db_index=True)

    class Meta:
        ordering = ['school__name', 'product__name', 'size__size_value']
        indexes = [
            models.Index(fields=['school', 'product', 'size'], name='idx_school_product_size'),
            models.Index(fields=['school', 'product'], name='idx_school_product'),
            models.Index(fields=['stock'], name='idx_stock_level'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'product', 'size'],
                condition=Q(school__isnull=False),
                name='uniq_school_product_size_specific',
            ),
            models.UniqueConstraint(
                fields=['product', 'size'],
                condition=Q(school__isnull=True),
                name='uniq_school_product_size_general',
            ),
            models.CheckConstraint(
                condition=Q(price__isnull=True) | Q(price__gte=0),
                name='schoolproduct_price_non_negative',
            ),
            models.CheckConstraint(
                condition=Q(stock__gte=0),
                name='schoolproduct_stock_non_negative',
            ),
            models.CheckConstraint(
                condition=Q(low_stock_threshold__gte=0),
                name='schoolproduct_threshold_non_negative',
            ),
        ]

    def __str__(self):
        if self.school:
            return f"{self.school.name} — {self.product.name} ({self.size.size_value})"
        return f"General Item — {self.product.name} ({self.size.size_value})"

    def save(self, *args, **kwargs):
        # Auto-generate SKU code if not set
        if not self.sku_code and self.pk:
            prefix = self.school.code.upper() if self.school else "GEN"
            self.sku_code = f"{prefix}{self.pk:06d}"
        
        super().save(*args, **kwargs)
        
        if not self.sku_code:
            prefix = self.school.code.upper() if self.school else "GEN"
            self.sku_code = f"{prefix}{self.pk:06d}"
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
