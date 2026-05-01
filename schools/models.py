from django.db import models
from products.models import Product
from sizes.models import Size


class School(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)

    def __str__(self):
        return self.name


class SchoolProduct(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    size = models.ForeignKey(Size, on_delete=models.CASCADE)

    price = models.DecimalField(max_digits=8, decimal_places=2)
    stock = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.school.name} - {self.product.name} - {self.size.size_value}"