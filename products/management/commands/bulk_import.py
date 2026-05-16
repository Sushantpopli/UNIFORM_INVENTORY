import csv
import re
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction

from products.models import Product
from schools.import_matching import FUZZY_REVIEW_THRESHOLD, find_name_match, normalize_name
from schools.models import School, SchoolProduct
from sizes.models import Size


GENERAL_SCHOOL_NAMES = {'general item', 'general items', 'general', 'none'}
HEADERS = {
    'school_name': 'School Name',
    'school_code': 'School Code',
    'product': 'Product Name',
    'size': 'Size',
    'price': 'Price',
    'stock': 'Initial Stock',
}


def make_unique_school_code(name):
    base = re.sub(r'[^A-Z0-9]', '', (name or '').upper())[:5] or 'SCH'
    code = base
    suffix = 1
    while School.objects.filter(code__iexact=code).exists():
        suffix += 1
        code = f'{base[: max(1, 5 - len(str(suffix)))]}{suffix}'
    return code


def parse_price(value, row_number, errors):
    value = (value or '').strip()
    if not value:
        errors.append(f'Row {row_number}: Price is required.')
        return None

    cleaned = value.replace(',', '')
    try:
        price = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        errors.append(f'Row {row_number}: Price "{value}" is invalid. Use numbers only, like 450 or 450.00.')
        return None

    if price < 0:
        errors.append(f'Row {row_number}: Price cannot be negative.')
        return None
    return price


def parse_stock(value, row_number, errors):
    value = (value or '').strip()
    if not value:
        errors.append(f'Row {row_number}: Initial Stock is required. Use 0 if there is no stock.')
        return None

    cleaned = value.replace(',', '')
    if not re.fullmatch(r'-?\d+', cleaned):
        errors.append(f'Row {row_number}: Initial Stock "{value}" is invalid. Use a whole number only.')
        return None

    stock = int(cleaned)
    if stock < 0:
        errors.append(f'Row {row_number}: Initial Stock cannot be negative.')
        return None
    return stock


class Command(BaseCommand):
    help = 'Strictly imports inventory from CSV after validating every row first'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **options):
        csv_file = options['csv_file']

        try:
            with open(csv_file, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)

                if reader.fieldnames:
                    reader.fieldnames = [name.strip() for name in reader.fieldnames]
                else:
                    self.stdout.write(self.style.ERROR('Import failed: the CSV file is empty or has no header row.'))
                    return

                has_name = HEADERS['school_name'] in reader.fieldnames
                has_code = HEADERS['school_code'] in reader.fieldnames
                if not has_name and not has_code:
                    self.stdout.write(self.style.ERROR(
                        f'Import failed: CSV must contain either "{HEADERS["school_name"]}" or "{HEADERS["school_code"]}".'
                    ))
                    return

                required = ['product', 'size', 'price', 'stock']
                missing = [HEADERS[key] for key in required if HEADERS[key] not in reader.fieldnames]
                if missing:
                    self.stdout.write(self.style.ERROR(
                        f'Import failed: missing required column(s): {", ".join(missing)}.'
                    ))
                    return

                planned_rows = []
                corrections = []
                errors = []
                seen_keys = {}

                for row_number, row in enumerate(reader, start=2):
                    school_name = row.get(HEADERS['school_name'], '').strip()
                    school_code = row.get(HEADERS['school_code'], '').strip()
                    product_name = row.get(HEADERS['product'], '').strip()
                    size_value = row.get(HEADERS['size'], '').strip()
                    price_value = row.get(HEADERS['price'], '').strip()
                    stock_value = row.get(HEADERS['stock'], '').strip()

                    if not any([school_name, school_code, product_name, size_value, price_value, stock_value]):
                        continue

                    if not product_name:
                        errors.append(f'Row {row_number}: Product Name is required.')
                    if not size_value:
                        errors.append(f'Row {row_number}: Size is required.')

                    price = parse_price(price_value, row_number, errors)
                    stock = parse_stock(stock_value, row_number, errors)

                    if not product_name or not size_value or price is None or stock is None:
                        continue

                    school = None
                    new_school_name = ''
                    new_school_code = ''

                    if not school_name and not school_code:
                        school_key = 'general'
                    elif school_name.lower() in GENERAL_SCHOOL_NAMES or school_code.lower() == 'general':
                        school_key = 'general'
                    else:
                        if school_code:
                            school = School.objects.filter(code__iexact=school_code).first()
                            if not school and not school_name:
                                errors.append(f'Row {row_number}: school code "{school_code}" was not found.')
                                continue

                        if not school and school_name:
                            school, corrected, matched_name, ratio = find_name_match(School, school_name)
                            if school and corrected:
                                corrections.append(f'Row {row_number}: school "{school_name}" matched to "{matched_name}".')
                            elif not school and matched_name and ratio >= FUZZY_REVIEW_THRESHOLD:
                                errors.append(
                                    f'Row {row_number}: school "{school_name}" looks close to "{matched_name}". Fix the spelling before importing.'
                                )
                                continue
                            elif not school:
                                new_school_name = school_name
                                new_school_code = school_code or make_unique_school_code(school_name)

                        school_key = f'id:{school.pk}' if school else f'new:{normalize_name(new_school_name)}'

                    product, product_corrected, matched_product, product_ratio = find_name_match(Product, product_name)
                    if product and product_corrected:
                        corrections.append(f'Row {row_number}: product "{product_name}" matched to "{matched_product}".')
                    elif not product and matched_product and product_ratio >= FUZZY_REVIEW_THRESHOLD:
                        errors.append(
                            f'Row {row_number}: product "{product_name}" looks close to "{matched_product}". Fix the spelling or create the new product manually first.'
                        )
                        continue

                    product_key = f'id:{product.pk}' if product else f'new:{normalize_name(product_name)}'
                    duplicate_key = (school_key, product_key, normalize_name(size_value))
                    if duplicate_key in seen_keys:
                        errors.append(
                            f'Row {row_number}: duplicate of row {seen_keys[duplicate_key]} for the same school, product, and size.'
                        )
                        continue
                    seen_keys[duplicate_key] = row_number

                    planned_rows.append({
                        'school': school,
                        'school_name': new_school_name,
                        'school_code': new_school_code,
                        'product': product,
                        'product_name': product_name,
                        'size_value': size_value,
                        'price': price,
                        'stock': stock,
                    })

                if not planned_rows and not errors:
                    self.stdout.write(self.style.ERROR('Import failed: no usable data rows were found.'))
                    return

                if errors:
                    self.stdout.write(self.style.ERROR(
                        f'Import cancelled: fix {len(errors)} problem(s) in the CSV and run again. No data was changed.'
                    ))
                    for error in errors:
                        self.stdout.write(self.style.ERROR(f'  {error}'))
                    return

                created_count = 0
                updated_count = 0

                with db_transaction.atomic():
                    school_cache = {}
                    product_cache = {}
                    size_cache = {}

                    for row in planned_rows:
                        school = row['school']
                        if not school and row['school_name']:
                            school_key = normalize_name(row['school_name'])
                            if school_key not in school_cache:
                                code = row['school_code']
                                if School.objects.filter(code__iexact=code).exists():
                                    code = make_unique_school_code(row['school_name'])
                                school_cache[school_key] = School.objects.create(
                                    name=row['school_name'],
                                    code=code,
                                )
                            school = school_cache[school_key]

                        product = row['product']
                        if not product:
                            product_key = normalize_name(row['product_name'])
                            if product_key not in product_cache:
                                product_cache[product_key] = Product.objects.create(name=row['product_name'])
                            product = product_cache[product_key]

                        size_key = (product.pk, row['size_value'].lower())
                        if size_key not in size_cache:
                            size, _ = Size.objects.get_or_create(
                                product=product,
                                size_value__iexact=row['size_value'],
                                defaults={'size_value': row['size_value']},
                            )
                            size_cache[size_key] = size
                        size = size_cache[size_key]

                        sp, created = SchoolProduct.objects.get_or_create(
                            school=school,
                            product=product,
                            size=size,
                            defaults={'price': row['price'], 'stock': row['stock']},
                        )

                        if created:
                            created_count += 1
                        else:
                            needs_update = False
                            if sp.price != row['price']:
                                sp.price = row['price']
                                needs_update = True
                            if sp.stock != row['stock']:
                                sp.stock = row['stock']
                                needs_update = True
                            if needs_update:
                                sp.save()
                                updated_count += 1

                self.stdout.write(self.style.SUCCESS(
                    f'Import complete. Created {created_count} new item(s). Updated {updated_count} existing item(s).'
                ))
                for correction in corrections:
                    self.stdout.write(self.style.WARNING(f'  {correction}'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File {csv_file} not found.'))
        except UnicodeDecodeError:
            self.stdout.write(self.style.ERROR(
                'Import failed: this does not look like a valid CSV file. Save the Excel sheet as CSV UTF-8 and run again.'
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {e}'))
