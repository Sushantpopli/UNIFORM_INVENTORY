from django.db import transaction as db_transaction
from django.db.models import Sum, F, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse

from schools.models import School, SchoolProduct
from products.models import Product
from sizes.models import Size
from transactions.models import StockTransaction, ManufacturingOrder


# ─── Helper ────────────────────────────────────────────────────────────────────

def _record_transaction(school_product, tx_type, qty, note=''):
    """Atomically create a transaction and update stock."""
    with db_transaction.atomic():
        StockTransaction.objects.create(
            school_product=school_product,
            transaction_type=tx_type,
            quantity=qty,
            note=note,
        )
        if tx_type in ('RESTOCK', 'RETURN', 'EXCHANGE_IN'):
            SchoolProduct.objects.filter(pk=school_product.pk).update(stock=F('stock') + qty)
        elif tx_type in ('SALE', 'EXCHANGE_OUT'):
            SchoolProduct.objects.filter(pk=school_product.pk).update(stock=F('stock') - qty)


# ─── API Endpoints (for cascading dropdowns) ───────────────────────────────────

def api_products_for_school(request):
    school_id = request.GET.get('school_id')
    products = Product.objects.filter(
        school_products__school_id=school_id
    ).distinct().values('id', 'name').order_by('name')
    return JsonResponse(list(products), safe=False)


def api_sizes_for_school_product(request):
    school_id = request.GET.get('school_id')
    product_id = request.GET.get('product_id')
    sizes = Size.objects.filter(
        school_products__school_id=school_id,
        school_products__product_id=product_id,
    ).distinct().values('id', 'size_value').order_by('size_value')
    return JsonResponse(list(sizes), safe=False)


def api_stock_check(request):
    school_id = request.GET.get('school_id')
    product_id = request.GET.get('product_id')
    size_id = request.GET.get('size_id')
    try:
        sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=size_id)
        return JsonResponse({'stock': sp.stock, 'threshold': sp.low_stock_threshold})
    except SchoolProduct.DoesNotExist:
        return JsonResponse({'stock': 0, 'threshold': 5})


# ─── Dashboard ─────────────────────────────────────────────────────────────────

def dashboard(request):
    total_skus = SchoolProduct.objects.count()
    total_stock = SchoolProduct.objects.aggregate(t=Sum('stock'))['t'] or 0
    low_stock_items = SchoolProduct.objects.filter(
        stock__lte=F('low_stock_threshold')
    ).select_related('school', 'product', 'size')
    recent_txs = StockTransaction.objects.select_related(
        'school_product__school', 'school_product__product', 'school_product__size'
    )[:12]
    pending_orders = ManufacturingOrder.objects.filter(status__in=['PENDING', 'PARTIAL']).count()

    ctx = {
        'total_skus': total_skus,
        'total_stock': total_stock,
        'low_stock_count': low_stock_items.count(),
        'low_stock_items': low_stock_items[:6],
        'recent_txs': recent_txs,
        'pending_orders': pending_orders,
        'schools_count': School.objects.count(),
    }
    return render(request, 'dashboard/index.html', ctx)


# ─── Inventory ─────────────────────────────────────────────────────────────────

def inventory_browse(request):
    qs = SchoolProduct.objects.select_related('school', 'product', 'size')
    school_id = request.GET.get('school')
    product_id = request.GET.get('product')
    status = request.GET.get('status')

    if school_id:
        qs = qs.filter(school_id=school_id)
    if product_id:
        qs = qs.filter(product_id=product_id)
    if status == 'low':
        qs = qs.filter(stock__lte=F('low_stock_threshold'), stock__gt=0)
    elif status == 'out':
        qs = qs.filter(stock=0)
    elif status == 'ok':
        qs = qs.filter(stock__gt=F('low_stock_threshold'))

    ctx = {
        'items': qs,
        'schools': School.objects.all(),
        'products': Product.objects.all(),
        'selected_school': school_id,
        'selected_product': product_id,
        'selected_status': status,
    }
    return render(request, 'inventory/browse.html', ctx)


def low_stock_report(request):
    items = SchoolProduct.objects.filter(
        stock__lte=F('low_stock_threshold')
    ).select_related('school', 'product', 'size').order_by('stock')
    return render(request, 'inventory/low_stock.html', {'items': items})


# ─── Stock IN (Restock) ────────────────────────────────────────────────────────

def stock_in(request):
    if request.method == 'POST':
        school_id = request.POST.get('school')
        product_id = request.POST.get('product')
        size_id = request.POST.get('size')
        qty = int(request.POST.get('quantity', 0))
        note = request.POST.get('note', '')
        try:
            sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=size_id)
            _record_transaction(sp, 'RESTOCK', qty, note)
            messages.success(request, f'✅ Added {qty} units to stock for {sp}')
            return redirect('stock_in')
        except SchoolProduct.DoesNotExist:
            messages.error(request, '❌ Invalid selection. This school-product-size combo does not exist.')

    return render(request, 'transactions/stock_in.html', {
        'schools': School.objects.all(),
        'action': 'stock_in',
        'page_title': 'Stock IN — Restock',
    })


# ─── Sale (Stock OUT) ──────────────────────────────────────────────────────────

def sale(request):
    if request.method == 'POST':
        school_id = request.POST.get('school')
        product_id = request.POST.get('product')
        size_id = request.POST.get('size')
        qty = int(request.POST.get('quantity', 0))
        note = request.POST.get('note', '')
        try:
            sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=size_id)
            if sp.stock < qty:
                messages.error(request, f'❌ Not enough stock. Available: {sp.stock}')
            else:
                _record_transaction(sp, 'SALE', qty, note)
                messages.success(request, f'✅ Sold {qty} units of {sp}')
                return redirect('sale')
        except SchoolProduct.DoesNotExist:
            messages.error(request, '❌ Invalid selection.')

    return render(request, 'transactions/stock_in.html', {
        'schools': School.objects.all(),
        'action': 'sale',
        'page_title': 'Sale — Stock OUT',
    })


# ─── Return ────────────────────────────────────────────────────────────────────

def return_item(request):
    if request.method == 'POST':
        school_id = request.POST.get('school')
        product_id = request.POST.get('product')
        size_id = request.POST.get('size')
        qty = int(request.POST.get('quantity', 0))
        note = request.POST.get('note', '')
        try:
            sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=size_id)
            _record_transaction(sp, 'RETURN', qty, note)
            messages.success(request, f'✅ Return recorded — {qty} units back in stock for {sp}')
            return redirect('return_item')
        except SchoolProduct.DoesNotExist:
            messages.error(request, '❌ Invalid selection.')

    return render(request, 'transactions/stock_in.html', {
        'schools': School.objects.all(),
        'action': 'return',
        'page_title': 'Return — Add back to Stock',
    })


# ─── Exchange ──────────────────────────────────────────────────────────────────

def exchange(request):
    if request.method == 'POST':
        school_id = request.POST.get('school')
        product_id = request.POST.get('product')
        old_size_id = request.POST.get('old_size')
        new_size_id = request.POST.get('new_size')
        qty = int(request.POST.get('quantity', 0))
        note = request.POST.get('note', '')
        try:
            old_sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=old_size_id)
            new_sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=new_size_id)
            if new_sp.stock < qty:
                messages.error(request, f'❌ Not enough stock for new size. Available: {new_sp.stock}')
            else:
                with db_transaction.atomic():
                    _record_transaction(old_sp, 'EXCHANGE_IN', qty, note)
                    _record_transaction(new_sp, 'EXCHANGE_OUT', qty, note)
                messages.success(request, f'✅ Exchange done — returned size {old_sp.size.size_value}, gave size {new_sp.size.size_value}')
                return redirect('exchange')
        except SchoolProduct.DoesNotExist:
            messages.error(request, '❌ Invalid selection.')

    return render(request, 'transactions/exchange.html', {
        'schools': School.objects.all(),
        'page_title': 'Exchange',
    })


# ─── Manufacturing Orders ──────────────────────────────────────────────────────

def manufacturing_list(request):
    orders = ManufacturingOrder.objects.select_related(
        'school_product__school', 'school_product__product', 'school_product__size'
    )
    return render(request, 'manufacturing/list.html', {'orders': orders})


def manufacturing_create(request):
    if request.method == 'POST':
        school_id = request.POST.get('school')
        product_id = request.POST.get('product')
        size_id = request.POST.get('size')
        qty = int(request.POST.get('quantity_ordered', 0))
        expected = request.POST.get('expected_at') or None
        notes = request.POST.get('notes', '')
        try:
            sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=size_id)
            ManufacturingOrder.objects.create(
                school_product=sp,
                quantity_ordered=qty,
                expected_at=expected,
                notes=notes,
            )
            messages.success(request, f'✅ Manufacturing order created for {sp}')
            return redirect('manufacturing_list')
        except SchoolProduct.DoesNotExist:
            messages.error(request, '❌ Invalid selection.')

    return render(request, 'manufacturing/create.html', {
        'schools': School.objects.all(),
    })


def manufacturing_receive(request, pk):
    order = get_object_or_404(ManufacturingOrder, pk=pk)
    if request.method == 'POST':
        qty = int(request.POST.get('quantity_received', 0))
        with db_transaction.atomic():
            order.quantity_received += qty
            if order.quantity_received >= order.quantity_ordered:
                order.status = 'COMPLETED'
            else:
                order.status = 'PARTIAL'
            order.save()
            _record_transaction(order.school_product, 'RESTOCK', qty, f'Manufacturing order #{order.pk} received')
        messages.success(request, f'✅ Received {qty} units — stock updated!')
        return redirect('manufacturing_list')
    return render(request, 'manufacturing/receive.html', {'order': order})
