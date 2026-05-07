from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from products.models import Product
from schools.models import School, SchoolProduct
from sizes.models import Size
from transactions.models import Bill, BillItem, StockTransaction


class BillingStockTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Demo School', code='DEMO')
        self.product = Product.objects.create(name='Shirt')
        self.size = Size.objects.create(product=self.product, size_value='32')
        self.item = SchoolProduct.objects.create(
            school=self.school,
            product=self.product,
            size=self.size,
            price=Decimal('450.00'),
            stock=10,
        )
        self.other_school = School.objects.create(name='Other School', code='OS')
        self.other_item = SchoolProduct.objects.create(
            school=self.other_school,
            product=self.product,
            size=self.size,
            price=Decimal('500.00'),
            stock=8,
        )

    def test_bill_sale_deducts_stock(self):
        response = self.client.post(reverse('bill_create'), {
            'school': str(self.school.pk),
            'customer_name': 'Test Customer',
            'customer_phone': '9999999999',
            'payment_mode': 'CASH',
            'item_id[]': [str(self.item.pk)],
            'qty[]': ['3'],
        })

        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 7)

        bill = Bill.objects.get()
        self.assertEqual(bill.total_amount, Decimal('1350.00'))
        self.assertEqual(BillItem.objects.get().quantity, 3)

        tx = StockTransaction.objects.get()
        self.assertEqual(tx.transaction_type, 'BILL_SALE')
        self.assertEqual(tx.quantity, 3)

    def test_void_bill_sale_transaction_restores_stock(self):
        self.client.post(reverse('bill_create'), {
            'school': str(self.school.pk),
            'payment_mode': 'CASH',
            'item_id[]': [str(self.item.pk)],
            'qty[]': ['3'],
        })
        tx = StockTransaction.objects.get(transaction_type='BILL_SALE')

        response = self.client.post(reverse('void_transaction', args=[tx.pk]), {
            'reason': 'Billing mistake',
        })

        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        tx.refresh_from_db()
        self.assertEqual(self.item.stock, 10)
        self.assertTrue(tx.is_void)
        self.assertEqual(tx.void_reason, 'Billing mistake')

    def test_bill_allows_items_from_multiple_schools(self):
        response = self.client.post(reverse('bill_create'), {
            'school': str(self.school.pk),
            'payment_mode': 'CASH',
            'item_id[]': [str(self.item.pk), str(self.other_item.pk)],
            'qty[]': ['2', '1'],
        })

        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.other_item.refresh_from_db()
        self.assertEqual(self.item.stock, 8)
        self.assertEqual(self.other_item.stock, 7)

        bill = Bill.objects.get()
        self.assertEqual(bill.items.count(), 2)
        self.assertEqual(bill.total_amount, Decimal('1400.00'))
        self.assertIn(self.school.name, bill.school_summary)
        self.assertIn(self.other_school.name, bill.school_summary)

    def test_bill_rejects_zero_quantity(self):
        response = self.client.post(reverse('bill_create'), {
            'school': str(self.school.pk),
            'payment_mode': 'CASH',
            'item_id[]': [str(self.item.pk)],
            'qty[]': ['0'],
        })

        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 10)
        self.assertFalse(Bill.objects.exists())

    def test_bill_rejects_incomplete_item_data(self):
        response = self.client.post(reverse('bill_create'), {
            'school': str(self.school.pk),
            'payment_mode': 'CASH',
            'item_id[]': [str(self.item.pk)],
        })

        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 10)
        self.assertFalse(Bill.objects.exists())
