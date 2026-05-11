import csv
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand
from products.models import Product
from sizes.models import Size
from schools.models import School, SchoolProduct
from django.db.models import Q

class Command(BaseCommand):
    help = 'Bulk imports inventory from CSV (School Name, Product Name, Size, Price, Initial Stock)'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        count = 0
        
        try:
            with open(csv_file, 'r', encoding='utf-8-sig') as f: # Use sig to handle Byte Order Mark from Excel
                reader = csv.DictReader(f)
                
                # Normalize column names (strip whitespace)
                reader.fieldnames = [name.strip() for name in reader.fieldnames]
                
                # Support the exact headers from user's screenshot + School Code
                headers = {
                    'school_name': 'School Name',
                    'school_code': 'School Code',
                    'product': 'Product Name',
                    'size': 'Size',
                    'price': 'Price',
                    'stock': 'Initial Stock'
                }

                # Verify headers
                missing = [v for k, v in headers.items() if v not in reader.fieldnames and k != 'school_code']
                if missing:
                    self.stdout.write(self.style.ERROR(f'CSV is missing columns: {", ".join(missing)}'))
                    return

                for row in reader:
                    try:
                        s_name = row[headers['school_name']].strip()
                        s_code = row.get(headers['school_code'], '').strip()
                        p_name = row[headers['product']].strip()
                        sz_val = row[headers['size']].strip()
                        pr_val = row[headers['price']].strip()
                        st_val = row[headers['stock']].strip()

                        if not p_name or not sz_val:
                            continue

                        # 1. Determine School
                        target_school = None
                        if s_name and s_name.lower() != 'general':
                            # Try to find school by name first
                            target_school = School.objects.filter(name__iexact=s_name).first()
                            
                            # If not found by name, try by code (if code provided)
                            if not target_school and s_code:
                                target_school = School.objects.filter(code__iexact=s_code).first()
                            
                            if not target_school:
                                self.stdout.write(self.style.WARNING(f'  School "{s_name}" not found. Skipping row.'))
                                continue

                        # 2. Get or Create Product
                        product, _ = Product.objects.get_or_create(name=p_name)
                        
                        # 3. Get or Create Size
                        size, _ = Size.objects.get_or_create(product=product, size_value=sz_val)
                        
                        # 4. Create or Update Link
                        defaults = {
                            'stock': int(float(st_val)) if st_val else 0,
                            'price': Decimal(pr_val) if pr_val else None,
                            'low_stock_threshold': 5
                        }
                        
                        sp, created = SchoolProduct.objects.update_or_create(
                            school=target_school,
                            product=product,
                            size=size,
                            defaults=defaults
                        )
                        
                        loc = target_school.name if target_school else "General Items"
                        action = "Created" if created else "Updated"
                        self.stdout.write(f'  [{loc}] {action}: {p_name} ({sz_val})')
                        count += 1
                        
                    except (InvalidOperation, ValueError, TypeError) as e:
                        self.stdout.write(self.style.WARNING(f'  Skipping row: {row} - Error: {e}'))
                        continue
            
            self.stdout.write(self.style.SUCCESS(f'\nSuccessfully processed {count} entries!'))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File {csv_file} not found.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {e}'))
