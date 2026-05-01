from django.core.management.base import BaseCommand
from products.models import Product
from sizes.models import Size
from schools.models import School, SchoolProduct


SCHOOLS = [
    ('Kali Devi School', 'KDS'),
    ('DPS', 'DPS'),
    ('Banda Bhadur School', 'BBS'),
    ('SD Modern', 'SDM'),
    ('Hindu School', 'HS'),
    ('EPS', 'EPS'),
    ('Happy Public School', 'HPS'),
    ('Bhagat Singh School', 'BSS'),
]

PRODUCTS_SIZES = {
    'Pant':         ['22','24','26','28','30','32','34','36','38','40','42','42-32','42-34','42-36','42-38','42-40'],
    'Shirt':        [str(s) for s in range(24, 54, 2)],
    'Nicker':       ['12','13','14','15','16','17','18','20'],
    'Skirt':        [str(s) for s in range(12, 28, 2)],
    'Divider':      ['18','20','22','24','26'],
    'T-Shirt':      [str(s) for s in range(22, 48, 2)],
    'Shoes':        [str(s) for s in range(6, 14)] + ['1B','2B','3B','4B','5B','6B','7B','8B','9B','10B'],
    'Socks':        ['2','3','4','5','6','7'],
    'Tie':          ['12','14','16','56'],
    'Belt':         ['FREE SIZE'],
    'Slax':         [str(s) for s in range(22, 44, 2)],
    'Blazer':       [str(s) for s in range(28, 46, 2)],
    'Jacket':       [str(s) for s in range(28, 46, 2)],
    'Bag':          ['FREE SIZE'],
    'Cap':          ['FREE SIZE'],
    'House T-Shirt': [str(s) for s in range(22, 48, 2)],
}


class Command(BaseCommand):
    help = 'Seed master data: schools, products, sizes, and all SchoolProduct entries'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding Schools...')
        schools = {}
        for name, code in SCHOOLS:
            obj, created = School.objects.get_or_create(name=name, defaults={'code': code})
            schools[name] = obj
            if created:
                self.stdout.write(f'  Created school: {name}')

        self.stdout.write('Seeding Products & Sizes...')
        product_size_map = {}
        for pname, size_values in PRODUCTS_SIZES.items():
            product, _ = Product.objects.get_or_create(name=pname)
            sizes = []
            for sv in size_values:
                size, _ = Size.objects.get_or_create(product=product, size_value=sv)
                sizes.append(size)
            product_size_map[pname] = (product, sizes)
            self.stdout.write(f'  Product: {pname} - {len(sizes)} sizes')

        self.stdout.write('Seeding SchoolProducts (all combinations)...')
        count = 0
        for school in schools.values():
            for pname, (product, sizes) in product_size_map.items():
                for size in sizes:
                    _, created = SchoolProduct.objects.get_or_create(
                        school=school,
                        product=product,
                        size=size,
                        defaults={'stock': 0, 'low_stock_threshold': 5},
                    )
                    if created:
                        count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done! Created {count} SchoolProduct entries across {len(schools)} schools.'
        ))
