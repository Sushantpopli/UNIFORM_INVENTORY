import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from products.models import Product
from schools.models import School, SchoolProduct
from sizes.models import Size


class BulkImportCommandTests(TestCase):
    def run_import(self, content):
        with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False, encoding='utf-8', newline='') as f:
            f.write(content)
            path = f.name
        out = StringIO()
        try:
            call_command('bulk_import', path, stdout=out)
        finally:
            os.unlink(path)
        return out.getvalue()

    def test_invalid_row_cancels_without_partial_import(self):
        output = self.run_import(
            'School Name,Product Name,Size,Price,Initial Stock\n'
            'Banda Bahadur School,Shirt,32,450,10\n'
            'Banda Bahadur School,Pant,34,550,-5\n'
        )

        self.assertIn('Import cancelled', output)
        self.assertEqual(School.objects.count(), 0)
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(SchoolProduct.objects.count(), 0)

    def test_duplicate_rows_cancel_import(self):
        output = self.run_import(
            'School Name,Product Name,Size,Price,Initial Stock\n'
            'Banda Bahadur School,Shirt,32,450,10\n'
            'Banda Bahadur School,Shirt,32,450,20\n'
        )

        self.assertIn('duplicate of row 2', output)
        self.assertEqual(SchoolProduct.objects.count(), 0)

    def test_suspicious_product_typo_cancels_import(self):
        School.objects.create(name='Banda Bahadur School', code='BBS')
        Product.objects.create(name='Shirt')

        output = self.run_import(
            'School Name,Product Name,Size,Price,Initial Stock\n'
            'Banda Bahadur School,Shrit,32,450,10\n'
        )

        self.assertIn('looks close to "Shirt"', output)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(SchoolProduct.objects.count(), 0)

    def test_existing_stock_can_update_to_zero(self):
        school = School.objects.create(name='Banda Bahadur School', code='BBS')
        product = Product.objects.create(name='Shirt')
        size = Size.objects.create(product=product, size_value='32')
        item = SchoolProduct.objects.create(
            school=school,
            product=product,
            size=size,
            price='450',
            stock=10,
        )

        output = self.run_import(
            'School Name,Product Name,Size,Price,Initial Stock\n'
            'Banda Bahadur School,Shirt,32,450,0\n'
        )

        self.assertIn('Updated 1 existing', output)
        item.refresh_from_db()
        self.assertEqual(item.stock, 0)
