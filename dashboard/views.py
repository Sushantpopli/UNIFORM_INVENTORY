from django.db import transaction as db_transaction
from django.db.models import Sum, F, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

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


def _safe_int(value, default=0, minimum=0):
    """Safely parse an integer from form input."""
    try:
        v = int(value)
        return max(v, minimum)
    except (TypeError, ValueError):
        return default


# ─── API Endpoints (cascading dropdowns) ───────────────────────────────────────

def api_products_for_school(request):
    school_id = request.GET.get('school_id')
    if not school_id:
        return JsonResponse([], safe=False)
    products = Product.objects.filter(
        school_products__school_id=school_id
    ).distinct().values('id', 'name').order_by('name')
    return JsonResponse(list(products), safe=False)


def api_sizes_for_school_product(request):
    school_id = request.GET.get('school_id')
    product_id = request.GET.get('product_id')
    if not school_id or not product_id:
        return JsonResponse([], safe=False)
    sizes = Size.objects.filter(
        school_products__school_id=school_id,
        school_products__product_id=product_id,
    ).distinct().values('id', 'size_value').order_by('size_value')
    return JsonResponse(list(sizes), safe=False)


def api_stock_check(request):
    school_id = request.GET.get('school_id')
    product_id = request.GET.get('product_id')
    size_id = request.GET.get('size_id')
    if not all([school_id, product_id, size_id]):
        return JsonResponse({'stock': 0, 'threshold': 5})
    try:
        sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=size_id)
        return JsonResponse({'stock': sp.stock, 'threshold': sp.low_stock_threshold})
    except SchoolProduct.DoesNotExist:
        return JsonResponse({'stock': 0, 'threshold': 5})


# ─── Dashboard ─────────────────────────────────────────────────────────────────

def dashboard(request):
    total_skus = SchoolProduct.objects.count()
    total_stock = SchoolProduct.objects.aggregate(t=Sum('stock'))['t'] or 0
    low_stock_qs = SchoolProduct.objects.filter(
        stock__lte=F('low_stock_threshold')
    ).select_related('school', 'product', 'size')
    low_stock_count = low_stock_qs.count()
    recent_txs = StockTransaction.objects.filter(is_void=False).select_related(
        'school_product__school', 'school_product__product', 'school_product__size'
    )[:10]
    pending_orders = ManufacturingOrder.objects.filter(status__in=['PENDING', 'PARTIAL']).count()

    ctx = {
        'total_skus': total_skus,
        'total_stock': total_stock,
        'low_stock_count': low_stock_count,
        'low_stock_items': low_stock_qs[:6],
        'recent_txs': recent_txs,
        'pending_orders': pending_orders,
        'schools': School.objects.all(),
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

    paginator = Paginator(qs, 30)
    page = request.GET.get('page', 1)
    items = paginator.get_page(page)

    ctx = {
        'items': items,
        'schools': School.objects.all(),
        'products': Product.objects.all(),
        'selected_school': school_id or '',
        'selected_product': product_id or '',
        'selected_status': status or '',
        'total_count': paginator.count,
    }
    return render(request, 'inventory/browse.html', ctx)


def low_stock_report(request):
    qs = SchoolProduct.objects.filter(
        stock__lte=F('low_stock_threshold')
    ).select_related('school', 'product', 'size').order_by('stock')

    paginator = Paginator(qs, 30)
    page = request.GET.get('page', 1)
    items = paginator.get_page(page)

    return render(request, 'inventory/low_stock.html', {'items': items, 'total_count': paginator.count})


# ─── Stock IN (Add Stock) ──────────────────────────────────────────────────────

def stock_in(request):
    if request.method == 'POST':
        school_id = request.POST.get('school')
        product_id = request.POST.get('product')
        size_id = request.POST.get('size')
        qty = _safe_int(request.POST.get('quantity'), minimum=1)
        note = request.POST.get('note', '').strip()

        if qty < 1:
            messages.error(request, 'Please enter a valid quantity (at least 1).')
        else:
            try:
                sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=size_id)
                _record_transaction(sp, 'RESTOCK', qty, note)
                sp.refresh_from_db()
                messages.success(request, f'Added {qty} units. New stock: {sp.stock}')
                return redirect('stock_in')
            except SchoolProduct.DoesNotExist:
                messages.error(request, 'Invalid selection. Please pick school, product and size.')

    return render(request, 'transactions/stock_in.html', {
        'schools': School.objects.all(),
        'action': 'stock_in',
        'page_title': 'Add Stock',
        'page_desc': 'Select the school, product and size, then enter how many pieces arrived.',
        'btn_label': 'Add Stock',
        'btn_icon': 'plus',
    })


# ─── Sale (Stock OUT) ──────────────────────────────────────────────────────────

def sale(request):
    if request.method == 'POST':
        school_id = request.POST.get('school')
        product_id = request.POST.get('product')
        size_id = request.POST.get('size')
        qty = _safe_int(request.POST.get('quantity'), minimum=1)
        note = request.POST.get('note', '').strip()

        if qty < 1:
            messages.error(request, 'Please enter a valid quantity (at least 1).')
        else:
            try:
                sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=size_id)
                if sp.stock < qty:
                    messages.error(request, f'Not enough stock! Only {sp.stock} available.')
                else:
                    _record_transaction(sp, 'SALE', qty, note)
                    sp.refresh_from_db()
                    messages.success(request, f'Sold {qty} units. Remaining stock: {sp.stock}')
                    return redirect('sale')
            except SchoolProduct.DoesNotExist:
                messages.error(request, 'Invalid selection. Please pick school, product and size.')

    return render(request, 'transactions/stock_in.html', {
        'schools': School.objects.all(),
        'action': 'sale',
        'page_title': 'Record Sale',
        'page_desc': 'Select the item sold and enter the quantity.',
        'btn_label': 'Confirm Sale',
        'btn_icon': 'sale',
    })


# ─── Return ────────────────────────────────────────────────────────────────────

def return_item(request):
    if request.method == 'POST':
        school_id = request.POST.get('school')
        product_id = request.POST.get('product')
        size_id = request.POST.get('size')
        qty = _safe_int(request.POST.get('quantity'), minimum=1)
        note = request.POST.get('note', '').strip()

        if qty < 1:
            messages.error(request, 'Please enter a valid quantity (at least 1).')
        else:
            try:
                sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=size_id)
                _record_transaction(sp, 'RETURN', qty, note)
                sp.refresh_from_db()
                messages.success(request, f'Return recorded. {qty} units back in stock. New stock: {sp.stock}')
                return redirect('return_item')
            except SchoolProduct.DoesNotExist:
                messages.error(request, 'Invalid selection. Please pick school, product and size.')

    return render(request, 'transactions/stock_in.html', {
        'schools': School.objects.all(),
        'action': 'return',
        'page_title': 'Return Item',
        'page_desc': 'Select the returned item. Stock will be added back.',
        'btn_label': 'Confirm Return',
        'btn_icon': 'return',
    })


# ─── Exchange ──────────────────────────────────────────────────────────────────

def exchange(request):
    if request.method == 'POST':
        school_id = request.POST.get('school')
        product_id = request.POST.get('product')
        old_size_id = request.POST.get('old_size')
        new_size_id = request.POST.get('new_size')
        qty = _safe_int(request.POST.get('quantity'), minimum=1)
        note = request.POST.get('note', '').strip()

        if old_size_id == new_size_id:
            messages.error(request, 'Old size and new size cannot be the same.')
        elif qty < 1:
            messages.error(request, 'Please enter a valid quantity.')
        else:
            try:
                old_sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=old_size_id)
                new_sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=new_size_id)
                if new_sp.stock < qty:
                    messages.error(request, f'Not enough stock for new size! Only {new_sp.stock} available.')
                else:
                    with db_transaction.atomic():
                        _record_transaction(old_sp, 'EXCHANGE_IN', qty, note)
                        _record_transaction(new_sp, 'EXCHANGE_OUT', qty, note)
                    messages.success(request, f'Exchange done. Size {old_sp.size.size_value} returned, size {new_sp.size.size_value} given.')
                    return redirect('exchange')
            except SchoolProduct.DoesNotExist:
                messages.error(request, 'Invalid selection. Please check all fields.')

    return render(request, 'transactions/exchange.html', {
        'schools': School.objects.all(),
        'page_title': 'Size Exchange',
    })


# ─── Transaction History ───────────────────────────────────────────────────────

def transaction_history(request):
    qs = StockTransaction.objects.select_related(
        'school_product__school', 'school_product__product', 'school_product__size'
    )

    # Filters
    school_id = request.GET.get('school')
    product_id = request.GET.get('product')
    tx_type = request.GET.get('type')
    date_range = request.GET.get('range', '')
    show_void = request.GET.get('void', '')

    if school_id:
        qs = qs.filter(school_product__school_id=school_id)
    if product_id:
        qs = qs.filter(school_product__product_id=product_id)
    if tx_type:
        qs = qs.filter(transaction_type=tx_type)
    if not show_void:
        qs = qs.filter(is_void=False)
    if date_range == 'today':
        qs = qs.filter(created_at__date=timezone.now().date())
    elif date_range == 'week':
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=7))
    elif date_range == 'month':
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=30))

    paginator = Paginator(qs, 30)
    page = request.GET.get('page', 1)
    txs = paginator.get_page(page)

    ctx = {
        'txs': txs,
        'schools': School.objects.all(),
        'products': Product.objects.all(),
        'selected_school': school_id or '',
        'selected_product': product_id or '',
        'selected_type': tx_type or '',
        'selected_range': date_range,
        'show_void': show_void,
        'total_count': paginator.count,
    }
    return render(request, 'transactions/history.html', ctx)


def void_transaction(request, pk):
    tx = get_object_or_404(StockTransaction, pk=pk)
    if tx.is_void:
        messages.error(request, 'This entry is already cancelled.')
        return redirect('transaction_history')

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        with db_transaction.atomic():
            # Reverse the stock change
            sp = tx.school_product
            if tx.transaction_type in ('RESTOCK', 'RETURN', 'EXCHANGE_IN'):
                SchoolProduct.objects.filter(pk=sp.pk).update(stock=F('stock') - tx.quantity)
            elif tx.transaction_type in ('SALE', 'EXCHANGE_OUT'):
                SchoolProduct.objects.filter(pk=sp.pk).update(stock=F('stock') + tx.quantity)
            tx.is_void = True
            tx.void_reason = reason or 'Cancelled'
            tx.save()
        messages.success(request, f'Entry cancelled. Stock has been corrected.')
        return redirect('transaction_history')

    return render(request, 'transactions/void_confirm.html', {'tx': tx})


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
        qty = _safe_int(request.POST.get('quantity_ordered'), minimum=1)
        expected = request.POST.get('expected_at') or None
        notes = request.POST.get('notes', '').strip()
        try:
            sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=size_id)
            ManufacturingOrder.objects.create(
                school_product=sp, quantity_ordered=qty, expected_at=expected, notes=notes,
            )
            messages.success(request, f'Manufacturing order created for {sp}')
            return redirect('manufacturing_list')
        except SchoolProduct.DoesNotExist:
            messages.error(request, 'Invalid selection.')

    return render(request, 'manufacturing/create.html', {'schools': School.objects.all()})


def manufacturing_receive(request, pk):
    order = get_object_or_404(ManufacturingOrder, pk=pk)
    if request.method == 'POST':
        qty = _safe_int(request.POST.get('quantity_received'), minimum=1)
        with db_transaction.atomic():
            order.quantity_received += qty
            if order.quantity_received >= order.quantity_ordered:
                order.status = 'COMPLETED'
            else:
                order.status = 'PARTIAL'
            order.save()
            _record_transaction(order.school_product, 'RESTOCK', qty, f'Manufacturing order #{order.pk}')
        messages.success(request, f'Received {qty} units. Stock updated!')
        return redirect('manufacturing_list')
    return render(request, 'manufacturing/receive.html', {'order': order})
