import json
import os
from urllib import error, request
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Sum, F
from django.utils import timezone

from schools.models import School, SchoolProduct
from transactions.models import Bill, BillItem


SYSTEM_INSTRUCTIONS = """
You are Ask UniStock, a read-only inventory assistant for a school uniform shop.
Answer only from the supplied JSON context. Do not guess missing values.
Never suggest that you changed stock, price, bills, schools, products, or sizes.
If the user asks to update data, tell them you can only guide them and they must use the app controls.
Use simple business language. Keep answers concise and include exact numbers when available.
For reorder advice, prioritize low-stock items and recent sales velocity from the supplied context.
"""


def _money(value):
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def _item_label(item):
    school_name = item.school.name if item.school else 'General Items'
    return {
        'school': school_name,
        'school_code': item.school.code if item.school else 'GEN',
        'product': item.product.name,
        'size': item.size.size_value,
        'stock': item.stock,
        'price': _money(item.price),
        'low_stock_threshold': item.low_stock_threshold,
        'is_low_stock': item.is_low_stock,
        'sku_code': item.sku_code,
    }


def _matching_school(question):
    question_lower = question.lower()
    for school in School.objects.all().order_by('name'):
        if school.code and school.code.lower() in question_lower:
            return school
        if school.name and school.name.lower() in question_lower:
            return school
    return None


def build_inventory_context(question):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)

    inventory = SchoolProduct.objects.select_related('school', 'product', 'size')
    total_stock = inventory.aggregate(total=Sum('stock'))['total'] or 0
    stock_value = sum((item.stock or 0) * _money(item.price) for item in inventory)

    low_stock_items = [
        _item_label(item)
        for item in inventory.filter(stock__lte=F('low_stock_threshold')).order_by('stock', 'school__name', 'product__name')[:25]
    ]

    out_of_stock_items = [
        _item_label(item)
        for item in inventory.filter(stock=0).order_by('school__name', 'product__name')[:25]
    ]

    today_bills = Bill.objects.filter(created_at__date=today, is_void=False)
    month_bills = Bill.objects.filter(created_at__date__gte=month_start, is_void=False)

    top_products = list(
        BillItem.objects.filter(bill__is_void=False, bill__created_at__gte=thirty_days_ago)
        .values('product_name', 'size_value')
        .annotate(quantity=Sum('quantity'), revenue=Sum('line_total'))
        .order_by('-quantity')[:15]
    )
    for row in top_products:
        row['revenue'] = _money(row['revenue'])

    top_schools = list(
        Bill.objects.filter(is_void=False, created_at__gte=thirty_days_ago)
        .values('school__name', 'school__code')
        .annotate(bills=Count('id'), revenue=Sum('total_amount'))
        .order_by('-revenue')[:10]
    )
    for row in top_schools:
        row['revenue'] = _money(row['revenue'])

    matched_school = _matching_school(question)
    school_inventory = []
    if matched_school:
        school_inventory = [
            _item_label(item)
            for item in inventory.filter(school=matched_school).order_by('product__name', 'size__size_value')[:80]
        ]

    return {
        'generated_for_date': today.isoformat(),
        'scope': 'read_only_inventory_and_sales_summary',
        'question': question,
        'totals': {
            'schools': School.objects.count(),
            'skus': inventory.count(),
            'total_stock_units': total_stock,
            'estimated_stock_value': _money(stock_value),
            'today_bills': today_bills.count(),
            'today_revenue': _money(today_bills.aggregate(total=Sum('total_amount'))['total']),
            'month_bills': month_bills.count(),
            'month_revenue': _money(month_bills.aggregate(total=Sum('total_amount'))['total']),
        },
        'low_stock_items': low_stock_items,
        'out_of_stock_items': out_of_stock_items,
        'top_products_last_30_days': top_products,
        'top_schools_last_30_days': top_schools,
        'matched_school': {
            'name': matched_school.name,
            'code': matched_school.code,
            'inventory': school_inventory,
        } if matched_school else None,
    }


def ask_local_assistant(question):
    context = build_inventory_context(question)
    ollama_url = getattr(settings, 'OLLAMA_URL', '') or os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
    ollama_model = getattr(settings, 'OLLAMA_MODEL', '') or os.environ.get('OLLAMA_MODEL', 'qwen2.5:7b')
    payload = {
        'model': ollama_model,
        'stream': False,
        'messages': [
            {'role': 'system', 'content': SYSTEM_INSTRUCTIONS.strip()},
            {'role': 'user', 'content': json.dumps(context, ensure_ascii=True)},
        ],
        'options': {
            'temperature': 0.1,
            'num_predict': 700,
        },
    }
    body = json.dumps(payload).encode('utf-8')
    req = request.Request(
        f'{ollama_url.rstrip("/")}/api/chat',
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode('utf-8'))
    except error.HTTPError as e:
        if e.code == 404:
            return {
                'ok': False,
                'answer': f"The AI model ({ollama_model}) is currently downloading in the background! Please grab a coffee and try asking again in a few minutes.",
                'setup_required': True,
            }
        return {
            'ok': False,
            'answer': f'Ollama returned an error: {e.code}',
            'setup_required': True,
        }
    except error.URLError:
        return {
            'ok': False,
            'answer': (
                'Local AI is ready, but Ollama is not running. Start Ollama and pull the model: '
                f'ollama pull {ollama_model}'
            ),
            'setup_required': True,
        }
    except Exception as e:
        return {
            'ok': False,
            'answer': 'The assistant connection timed out. If the model is downloading, this is normal. Try again shortly.',
            'setup_required': True,
        }
    except json.JSONDecodeError:
        return {
            'ok': False,
            'answer': 'Ollama returned an unreadable response. Check the Ollama terminal.',
            'setup_required': True,
        }

    answer = (data.get('message') or {}).get('content', '')
    return {
        'ok': True,
        'answer': answer.strip() or 'I could not prepare an answer from the available data.',
        'setup_required': False,
    }
