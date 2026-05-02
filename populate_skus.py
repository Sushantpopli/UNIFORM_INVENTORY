import os
import django
import sys

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'uniform_project.settings')
django.setup()

from schools.models import SchoolProduct

def run():
    products = SchoolProduct.objects.filter(sku_code__isnull=True)
    count = products.count()
    print(f"Found {count} products without sku_code.")
    
    updated = 0
    for sp in products:
        sp.sku_code = f"HSD{sp.pk:06d}"
        sp.save(update_fields=['sku_code'])
        updated += 1
        
    print(f"Successfully generated SKU codes for {updated} products.")

if __name__ == '__main__':
    run()
