from django.db import models
from products.models import Product

class Size(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    size_value = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.product.name} - {self.size_value}"