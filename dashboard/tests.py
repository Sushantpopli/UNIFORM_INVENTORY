from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from products.models import Product
from schools.models import School, SchoolProduct
from sizes.models import Size
from transactions.models import StockTransaction


class SetupImportDataTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='importer',
            password='password123',
        )
        self.client.force_login(user)

    def upload_csv(self, content, filename='inventory.csv'):
        upload = SimpleUploadedFile(
            filename,
            content.encode('utf-8'),
            content_type='text/csv',
        )
        return self.client.post(reverse('setup_import_data'), {'csv_file': upload})

    def test_school_typo_matches_existing_school_instead_of_creating_duplicate(self):
        school = School.objects.create(name='Banda Bahadur School', code='BBS')
        product = Product.objects.create(name='Shirt')
        size = Size.objects.create(product=product, size_value='32')

        response = self.upload_csv(
            'School Name,Product Name,Size,Price,Initial Stock\n'
            'Banda Bhadur School,Shirt,32,450,10\n'
        )

        self.assertRedirects(response, reverse('setup_home'))
        self.assertEqual(School.objects.count(), 1)
        school_product = SchoolProduct.objects.get(
            school=school,
            product=product,
            size=size,
        )
        self.assertEqual(school_product.stock, 10)
        self.assertEqual(str(school_product.price), '450.00')

    def test_suspicious_school_typo_is_skipped_to_avoid_duplicate(self):
        school = School.objects.create(name='Banda Bahadur School', code='BBS')
        Product.objects.create(name='Shirt')

        response = self.upload_csv(
            'School Name,Product Name,Size,Price,Initial Stock\n'
            'Banda Badal School,Shirt,32,450,10\n'
        )

        self.assertRedirects(response, reverse('setup_home'))
        self.assertEqual(School.objects.count(), 1)
        self.assertEqual(Product.objects.count(), 1)
        self.assertFalse(SchoolProduct.objects.filter(school=school).exists())

    def test_missing_required_column_cancels_import(self):
        response = self.upload_csv(
            'School Name,Product Name,Price,Initial Stock\n'
            'Banda Bahadur School,Shirt,450,10\n'
        )

        self.assertRedirects(response, reverse('setup_home'))
        self.assertEqual(School.objects.count(), 0)
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(SchoolProduct.objects.count(), 0)

    def test_invalid_numbers_cancel_import_without_partial_save(self):
        response = self.upload_csv(
            'School Name,Product Name,Size,Price,Initial Stock\n'
            'Banda Bahadur School,Shirt,32,450,10\n'
            'Banda Bahadur School,Pant,34,550,-5\n'
        )

        self.assertRedirects(response, reverse('setup_home'))
        self.assertEqual(School.objects.count(), 0)
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(SchoolProduct.objects.count(), 0)

    def test_duplicate_rows_cancel_import(self):
        response = self.upload_csv(
            'School Name,Product Name,Size,Price,Initial Stock\n'
            'Banda Bahadur School,Shirt,32,450,10\n'
            'Banda Bahadur School,Shirt,32,450,20\n'
        )

        self.assertRedirects(response, reverse('setup_home'))
        self.assertEqual(SchoolProduct.objects.count(), 0)

    def test_existing_stock_can_be_updated_to_zero(self):
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

        response = self.upload_csv(
            'School Name,Product Name,Size,Price,Initial Stock\n'
            'Banda Bahadur School,Shirt,32,450,0\n'
        )

        self.assertRedirects(response, reverse('setup_home'))
        item.refresh_from_db()
        self.assertEqual(item.stock, 0)

    def test_suspicious_product_typo_cancels_import(self):
        school = School.objects.create(name='Banda Bahadur School', code='BBS')
        Product.objects.create(name='Shirt')

        response = self.upload_csv(
            'School Name,Product Name,Size,Price,Initial Stock\n'
            'Banda Bahadur School,Shrit,32,450,10\n'
        )

        self.assertRedirects(response, reverse('setup_home'))
        self.assertEqual(Product.objects.count(), 1)
        self.assertFalse(SchoolProduct.objects.filter(school=school).exists())

    def test_rejects_excel_file_extension(self):
        response = self.upload_csv(
            'not really xlsx',
            filename='inventory.xlsx',
        )

        self.assertRedirects(response, reverse('setup_home'))
        self.assertEqual(SchoolProduct.objects.count(), 0)

    def test_blank_rows_are_ignored(self):
        response = self.upload_csv(
            'School Name,Product Name,Size,Price,Initial Stock\n'
            'Banda Bahadur School,Shirt,32,450,10\n'
            ',,,,\n'
        )

        self.assertRedirects(response, reverse('setup_home'))
        self.assertEqual(School.objects.count(), 1)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(SchoolProduct.objects.count(), 1)


class InventoryStockUpdateTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='stock-editor',
            password='password123',
        )
        self.client.force_login(user)
        self.school = School.objects.create(name='Banda Bahadur School', code='BBS')
        self.product = Product.objects.create(name='Shirt')
        self.size = Size.objects.create(product=self.product, size_value='32')
        self.item = SchoolProduct.objects.create(
            school=self.school,
            product=self.product,
            size=self.size,
            price='450',
            stock=10,
        )

    def test_direct_stock_update_sets_absolute_stock_and_records_adjustment(self):
        response = self.client.post(
            reverse('inventory_update_stock', args=[self.item.pk]),
            {'stock': '4'},
        )

        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 4)
        tx = StockTransaction.objects.get(school_product=self.item)
        self.assertEqual(tx.transaction_type, 'ADJUSTMENT')
        self.assertEqual(tx.quantity, -6)
        self.assertIn('10 -> 4', tx.note)

    def test_direct_stock_update_rejects_negative_stock(self):
        response = self.client.post(
            reverse('inventory_update_stock', args=[self.item.pk]),
            {'stock': '-1'},
        )

        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 10)
        self.assertFalse(StockTransaction.objects.exists())
