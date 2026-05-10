import csv
from django.core.management.base import BaseCommand
from schools.models import SchoolProduct

class Command(BaseCommand):
    help = 'Exports all SchoolProducts to a CSV for price setup'

    def handle(self, *args, **options):
        filename = 'inventory_setup.csv'
        items = SchoolProduct.objects.select_related('school', 'product', 'size').all()
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # We include the ID so the import tool knows exactly which record to update
            writer.writerow(['ID', 'School', 'Product', 'Size', 'Price', 'Stock'])
            
            for item in items:
                writer.writerow([
                    item.id,
                    item.school.name if item.school else 'General Items',
                    item.product.name,
                    item.size.size_value,
                    item.price or 0,
                    item.stock
                ])
        
        self.stdout.write(self.style.SUCCESS(f'Successfully exported {len(items)} items to {filename}'))
        self.stdout.write('Open this file in Excel, fill the Price column, and save it.' )
