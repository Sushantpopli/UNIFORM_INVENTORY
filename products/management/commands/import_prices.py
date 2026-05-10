import csv
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand
from schools.models import SchoolProduct

class Command(BaseCommand):
    help = 'Imports prices from the inventory_setup.csv file'

    def handle(self, *args, **options):
        filename = 'inventory_setup.csv'
        count = 0
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        item_id = row['ID']
                        price_val = row['Price'].strip()
                        
                        if price_val:
                            # Update the item by ID
                            SchoolProduct.objects.filter(id=item_id).update(price=Decimal(price_val))
                            count += 1
                    except (KeyError, InvalidOperation, ValueError):
                        continue
            
            self.stdout.write(self.style.SUCCESS(f'Successfully updated prices for {count} items!'))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File {filename} not found. Did you run export_inventory first?'))
