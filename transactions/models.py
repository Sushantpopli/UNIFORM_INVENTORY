from django.db import models
from schools.models import SchoolProduct


class StockTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('RESTOCK', 'Restock (Stock IN)'),
        ('SALE', 'Sale (Stock OUT)'),
        ('RETURN', 'Return'),
        ('EXCHANGE_IN', 'Exchange — Item Returned'),
        ('EXCHANGE_OUT', 'Exchange — New Item Given'),
    ]

    school_product = models.ForeignKey(
        SchoolProduct, on_delete=models.CASCADE, related_name='transactions'
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField()
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_transaction_type_display()} | {self.school_product} | Qty: {self.quantity}"


class ManufacturingOrder(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PARTIAL', 'Partially Received'),
        ('COMPLETED', 'Completed'),
    ]

    school_product = models.ForeignKey(
        SchoolProduct, on_delete=models.CASCADE, related_name='manufacturing_orders'
    )
    quantity_ordered = models.IntegerField()
    quantity_received = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    ordered_at = models.DateTimeField(auto_now_add=True)
    expected_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-ordered_at']

    def __str__(self):
        return f"Order: {self.school_product} — {self.quantity_ordered} units ({self.status})"
