from django.db import models
from django.utils import timezone
from schools.models import School, SchoolProduct


class StockTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('RESTOCK', 'Stock Added'),
        ('SALE', 'Sale'),
        ('RETURN', 'Return'),
        ('EXCHANGE_IN', 'Exchange — Returned'),
        ('EXCHANGE_OUT', 'Exchange — Given'),
        ('BILL_SALE', 'Bill Sale'),
    ]

    school_product = models.ForeignKey(
        SchoolProduct, on_delete=models.CASCADE, related_name='transactions'
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField()
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_void = models.BooleanField(default=False, db_index=True)
    void_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        prefix = '[VOID] ' if self.is_void else ''
        return f"{prefix}{self.get_transaction_type_display()} | {self.school_product} | Qty: {self.quantity}"


class Bill(models.Model):
    PAYMENT_MODES = [
        ('CASH', 'Cash'),
        ('UPI', 'UPI'),
        ('CARD', 'Card'),
        ('OTHER', 'Other'),
    ]

    bill_number = models.CharField(max_length=20, unique=True, db_index=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='bills')
    customer_name = models.CharField(max_length=100, blank=True)
    customer_phone = models.CharField(max_length=15, blank=True)
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODES, default='CASH')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_void = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Bill #{self.bill_number} — {self.school.name} — ₹{self.total_amount}"

    @staticmethod
    def generate_bill_number():
        today = timezone.now()
        prefix = f"HSD-{today.strftime('%y%m')}"
        last = Bill.objects.filter(bill_number__startswith=prefix).order_by('-bill_number').first()
        if last:
            last_seq = int(last.bill_number.split('-')[-1])
            seq = last_seq + 1
        else:
            seq = 1
        return f"{prefix}-{seq:04d}"


class BillItem(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    school_product = models.ForeignKey(SchoolProduct, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=100)  # Snapshot at billing time
    size_value = models.CharField(max_length=20)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product_name} ({self.size_value}) x{self.quantity} = ₹{self.line_total}"


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
