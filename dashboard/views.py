from django.db import transaction as db_transaction
from django.db.models import Sum, F, Q, Count
from django.db.models.functions import TruncMonth, TruncDay
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
import json

from schools.models import School, SchoolProduct
from products.models import Product
from sizes.models import Size
from transactions.models import StockTransaction, ManufacturingOrder, Bill, BillItem
import barcode
from barcode.writer import SVGWriter


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
        elif tx_type in ('SALE', 'EXCHANGE_OUT', 'BILL_SALE'):
            SchoolProduct.objects.filter(pk=school_product.pk).update(stock=F('stock') - qty)


def _safe_int(value, default=0, minimum=0):
    """Safely parse an integer from form input."""
    try:
        v = int(value)
        if v < minimum:
            return default
        return v
    except (TypeError, ValueError):
        return default


# ─── API Endpoints (cascading dropdowns) ───────────────────────────────────────

def api_products_for_school(request):
    school_id = request.GET.get('school_id')
    if not school_id:
        return JsonResponse([], safe=False)
    
    if school_id == 'general':
        products = Product.objects.filter(school_products__school__isnull=True)
    else:
        products = Product.objects.filter(school_products__school_id=school_id)
        
    products = products.distinct().values('id', 'name').order_by('name')
    return JsonResponse(list(products), safe=False)


def api_sizes_for_school_product(request):
    school_id = request.GET.get('school_id')
    product_id = request.GET.get('product_id')
    if not school_id or not product_id:
        return JsonResponse([], safe=False)
        
    if school_id == 'general':
        sizes = Size.objects.filter(school_products__school__isnull=True, school_products__product_id=product_id)
    else:
        sizes = Size.objects.filter(school_products__school_id=school_id, school_products__product_id=product_id)
        
    sizes = sizes.distinct().values('id', 'size_value').order_by('size_value')
    return JsonResponse(list(sizes), safe=False)


def api_stock_check(request):
    school_id = request.GET.get('school_id')
    product_id = request.GET.get('product_id')
    size_id = request.GET.get('size_id')
    if not all([school_id, product_id, size_id]):
        return JsonResponse({'stock': 0, 'threshold': 5})
    try:
        if school_id == 'general':
            stock_data = SchoolProduct.objects.filter(
                school__isnull=True, product_id=product_id, size_id=size_id
            ).values_list('stock', 'low_stock_threshold').first()
        else:
            stock_data = SchoolProduct.objects.filter(
                school_id=school_id, product_id=product_id, size_id=size_id
            ).values_list('stock', 'low_stock_threshold').first()
        
        if stock_data:
            return JsonResponse({'stock': stock_data[0], 'threshold': stock_data[1]})
        return JsonResponse({'stock': 0, 'threshold': 5})
    except Exception:
        return JsonResponse({'stock': 0, 'threshold': 5})


def api_barcode_lookup(request):
    code = request.GET.get('code', '').strip()
    if not code:
        return JsonResponse({'error': 'No code provided'}, status=400)
    try:
        sp = SchoolProduct.objects.select_related('school', 'product', 'size').get(sku_code__iexact=code)
        return JsonResponse({
            'id': sp.id,
            'school_id': sp.school_id or 'general',
            'school_name': sp.school.name if sp.school else 'General Item',
            'product_id': sp.product_id,
            'product_name': sp.product.name,
            'size_id': sp.size_id,
            'size_value': sp.size.size_value,
            'price': str(sp.price) if sp.price else '0.00',
            'stock': sp.stock,
        })
    except SchoolProduct.DoesNotExist:
        return JsonResponse({'error': 'Item not found'}, status=404)


def api_item_lookup(request):
    """Fetch full item details by school_id, product_id, size_id for manual billing."""
    school_id = request.GET.get('school_id')
    product_id = request.GET.get('product_id')
    size_id = request.GET.get('size_id')
    if not all([school_id, product_id, size_id]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    try:
        if school_id == 'general':
            sp = SchoolProduct.objects.select_related('product', 'size').get(
                school__isnull=True, product_id=product_id, size_id=size_id
            )
        else:
            sp = SchoolProduct.objects.select_related('school', 'product', 'size').get(
                school_id=school_id, product_id=product_id, size_id=size_id
            )
        return JsonResponse({
            'id': sp.id,
            'school_id': sp.school_id or 'general',
            'school_name': sp.school.name if sp.school else 'General Item',
            'product_id': sp.product_id,
            'product_name': sp.product.name,
            'size_id': sp.size_id,
            'size_value': sp.size.size_value,
            'price': str(sp.price) if sp.price else '0.00',
            'stock': sp.stock,
        })
    except SchoolProduct.DoesNotExist:
        return JsonResponse({'error': 'Item not found'}, status=404)


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
        if school_id == 'general':
            qs = qs.filter(school__isnull=True)
        else:
            qs = qs.filter(school_id=school_id)
    if product_id:
        qs = qs.filter(product_id=product_id)
    if status == 'low':
        qs = qs.filter(stock__lte=F('low_stock_threshold'), stock__gt=0)
    elif status == 'out':
        qs = qs.filter(stock=0)
    elif status == 'ok':
        qs = qs.filter(stock__gt=F('low_stock_threshold'))

    paginator = Paginator(qs, 100)
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


def inventory_update_price(request, pk):
    if request.method == 'POST':
        from decimal import Decimal, InvalidOperation
        item = get_object_or_404(SchoolProduct, pk=pk)
        price_val = request.POST.get('price', '').strip()
        if price_val:
            try:
                item.price = Decimal(price_val)
                item.save()
                messages.success(request, f'Price updated for {item.product.name} ({item.size.size_value}).')
            except (InvalidOperation, ValueError):
                messages.error(request, 'Invalid price format.')
        else:
            item.price = None
            item.save()
            messages.success(request, f'Price removed for {item.product.name} ({item.size.size_value}).')
            
    # Redirect back to where they came from
    referer = request.META.get('HTTP_REFERER', 'inventory_browse')
    return redirect(referer)


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
                if school_id == 'general':
                    sp = SchoolProduct.objects.get(school__isnull=True, product_id=product_id, size_id=size_id)
                else:
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
                if school_id == 'general':
                    sp = SchoolProduct.objects.get(school__isnull=True, product_id=product_id, size_id=size_id)
                else:
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
                if school_id == 'general':
                    sp = SchoolProduct.objects.get(school__isnull=True, product_id=product_id, size_id=size_id)
                else:
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
                if school_id == 'general':
                    old_sp = SchoolProduct.objects.get(school__isnull=True, product_id=product_id, size_id=old_size_id)
                    new_sp = SchoolProduct.objects.get(school__isnull=True, product_id=product_id, size_id=new_size_id)
                else:
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
            elif tx.transaction_type in ('SALE', 'EXCHANGE_OUT', 'BILL_SALE'):
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
            if school_id == 'general':
                sp = SchoolProduct.objects.get(school__isnull=True, product_id=product_id, size_id=size_id)
            else:
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


# ─── Billing System ────────────────────────────────────────────────────────────

def bill_create(request):
    if request.method == 'POST':
        school_id = request.POST.get('school', '').strip()
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        payment_mode = request.POST.get('payment_mode', 'CASH')

        item_ids = request.POST.getlist('item_id[]')
        qtys     = request.POST.getlist('qty[]')

        if not item_ids:
            messages.error(request, 'Please add at least one item to the bill.')
            return redirect('bill_create')
        if len(item_ids) != len(qtys):
            messages.error(request, 'Bill item data is incomplete. Please review the bill and try again.')
            return redirect('bill_create')

        # Resolve school — 'general' or empty means a general-items-only bill.
        # We still need a School FK. Detect the school from the first school-specific item.
        school = None
        if school_id and school_id != 'general':
            try:
                school = School.objects.get(id=school_id)
            except School.DoesNotExist:
                messages.error(request, 'Invalid school selected.')
                return redirect('bill_create')

        # If no school yet, scan items to find one
        if school is None:
            for sp_id in item_ids:
                try:
                    sp_check = SchoolProduct.objects.select_related('school').get(id=sp_id)
                    if sp_check.school is not None:
                        school = sp_check.school
                        break
                except SchoolProduct.DoesNotExist:
                    pass

        # Still no school → all items are general. Use a sentinel "General" school or error.
        if school is None:
            messages.error(request, 'Could not determine school. Please select a school or add at least one school-specific item.')
            return redirect('bill_create')

        with db_transaction.atomic():
            bill = Bill.objects.create(
                bill_number=Bill.generate_bill_number(),
                school=school,
                customer_name=customer_name,
                customer_phone=customer_phone,
                payment_mode=payment_mode,
                total_amount=0,
            )

            total_amount = 0

            for i in range(len(item_ids)):
                sp_id = item_ids[i]
                qty   = _safe_int(qtys[i], minimum=1)
                if qty < 1:
                    messages.error(request, 'Please enter a valid quantity for every bill item.')
                    db_transaction.set_rollback(True)
                    return redirect('bill_create')

                try:
                    sp = SchoolProduct.objects.select_related('school', 'product', 'size').get(id=sp_id)
                except SchoolProduct.DoesNotExist:
                    continue

                if sp.stock < qty:
                    messages.error(request, f'Not enough stock for {sp.product.name} ({sp.size.size_value}). Only {sp.stock} in stock.')
                    db_transaction.set_rollback(True)
                    return redirect('bill_create')

                price      = sp.price or 0
                line_total = price * qty
                total_amount += line_total

                BillItem.objects.create(
                    bill=bill,
                    school_product=sp,
                    product_name=sp.product.name,
                    size_value=sp.size.size_value,
                    quantity=qty,
                    unit_price=price,
                    line_total=line_total,
                )
                _record_transaction(sp, 'BILL_SALE', qty, f'Bill #{bill.bill_number}')

            if total_amount == 0:
                messages.error(request, 'Bill total is ₹0. Make sure items have prices set.')
                db_transaction.set_rollback(True)
                return redirect('bill_create')

            bill.total_amount = total_amount
            bill.save()

        messages.success(request, f'Bill {bill.bill_number} generated successfully!')
        return redirect('bill_print', pk=bill.pk)

    return render(request, 'billing/create.html', {
        'schools': School.objects.all(),
        'page_title': 'Create Bill',
    })



def bill_print(request, pk):
    bill = get_object_or_404(Bill.objects.prefetch_related('items__school_product__school'), pk=pk)
    return render(request, 'billing/print.html', {'bill': bill})


def bill_void(request, pk):
    """Void a bill and restore stock for every item."""
    bill = get_object_or_404(Bill, pk=pk)
    if bill.is_void:
        messages.error(request, f'Bill {bill.bill_number} is already voided.')
        return redirect('bill_history')

    if request.method == 'POST':
        with db_transaction.atomic():
            for item in bill.items.select_related('school_product').all():
                # Restore stock
                SchoolProduct.objects.filter(pk=item.school_product_id).update(
                    stock=F('stock') + item.quantity
                )
                # Mark the associated BILL_SALE transaction as void too
                item.school_product.transactions.filter(
                    transaction_type='BILL_SALE',
                    note__icontains=bill.bill_number,
                    is_void=False
                ).update(is_void=True, void_reason=f'Bill {bill.bill_number} voided')
            bill.is_void = True
            bill.save()
        messages.success(request, f'Bill {bill.bill_number} voided. Stock has been restored.')
    return redirect('bill_history')


def bill_history(request):
    qs = Bill.objects.prefetch_related('items__school_product__school').select_related('school')
    
    school_id = request.GET.get('school')
    date_range = request.GET.get('range', '')
    query = request.GET.get('q', '').strip()
    
    if school_id:
        qs = qs.filter(Q(school_id=school_id) | Q(items__school_product__school_id=school_id)).distinct()
    if query:
        qs = qs.filter(Q(bill_number__icontains=query) | Q(customer_phone__icontains=query) | Q(customer_name__icontains=query))
        
    if date_range == 'today':
        qs = qs.filter(created_at__date=timezone.now().date())
    elif date_range == 'week':
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=7))
    elif date_range == 'month':
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=30))
        
    paginator = Paginator(qs, 20)
    page = request.GET.get('page', 1)
    bills = paginator.get_page(page)
    
    return render(request, 'billing/history.html', {
        'bills': bills,
        'schools': School.objects.all(),
        'selected_school': school_id or '',
        'selected_range': date_range,
        'query': query,
        'total_count': paginator.count
    })


def daily_summary(request):
    today = timezone.now().date()
    # Get total sales for today (completed bills)
    bills_today = Bill.objects.filter(created_at__date=today, is_void=False)
    
    total_revenue = bills_today.aggregate(t=Sum('total_amount'))['t'] or 0
    total_bills = bills_today.count()
    
    # Items sold today via bills
    items_sold = BillItem.objects.filter(bill__in=bills_today).values(
        'product_name', 'size_value'
    ).annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum('line_total')
    ).order_by('-total_qty')
    
    # Sales by school
    school_sales = bills_today.values('school__name').annotate(
        total_revenue=Sum('total_amount'),
        bill_count=Count('id')
    ).order_by('-total_revenue')
    
    return render(request, 'dashboard/summary.html', {
        'today': today,
        'total_revenue': total_revenue,
        'total_bills': total_bills,
        'items_sold': items_sold,
        'school_sales': school_sales
    })


# ─── Barcode Labels ────────────────────────────────────────────────────────────

def labels_setup(request):
    if request.method == 'POST':
        school_id = request.POST.get('school')
        product_id = request.POST.get('product')
        size_id = request.POST.get('size')
        qty = _safe_int(request.POST.get('quantity'), minimum=1)
        
        if not all([school_id, product_id, size_id]):
            messages.error(request, 'Please select School, Product, and Size.')
            return redirect('labels_setup')
            
        try:
            if school_id == 'general':
                sp = SchoolProduct.objects.get(school__isnull=True, product_id=product_id, size_id=size_id)
            else:
                sp = SchoolProduct.objects.get(school_id=school_id, product_id=product_id, size_id=size_id)
            # Store in session to pass to print view
            request.session['print_label_data'] = {
                'sp_id': sp.id,
                'qty': qty
            }
            return redirect('labels_print')
        except SchoolProduct.DoesNotExist:
            messages.error(request, 'Item not found.')
            return redirect('labels_setup')
            
    return render(request, 'inventory/labels.html', {
        'schools': School.objects.all(),
        'page_title': 'Print Barcode Labels'
    })


def labels_print(request):
    data = request.session.get('print_label_data')
    if not data:
        messages.error(request, 'No print data found.')
        return redirect('labels_setup')
        
    sp = get_object_or_404(SchoolProduct, id=data['sp_id'])
    qty = data['qty']

    # Guard: ensure SKU is set (edge case for very old records)
    if not sp.sku_code:
        sp.sku_code = f'HSD{sp.pk:06d}'
        SchoolProduct.objects.filter(pk=sp.pk).update(sku_code=sp.sku_code)
    
    # Generate SVG Barcode
    code128 = barcode.get('code128', sp.sku_code, writer=SVGWriter())
    # We want a clean barcode without the text below it (we'll add our own text)
    options = {
        'write_text': False,
        'module_width': 0.3,
        'module_height': 8.0,
        'quiet_zone': 1.0,
    }
    svg_bytes = code128.render(options)
    svg_str = svg_bytes.decode('utf-8')
    
    # Clean up the SVG to fit our box better if needed, but injecting directly is fine.
    # The SVG generated has xml headers which we can strip out for inline HTML,
    # but modern browsers usually handle raw injected SVG strings okay if we skip the header.
    svg_str = svg_str[svg_str.find('<svg'):]
    
    # Create list of items to loop over
    stickers = range(qty)
    
    return render(request, 'inventory/labels_print.html', {
        'sp': sp,
        'stickers': stickers,
        'svg_barcode': svg_str
    })


# ─── Setup / Master Data ───────────────────────────────────────────────────────

def setup_home(request):
    """Master data management hub."""
    schools = School.objects.all().order_by('name')
    products = Product.objects.all().order_by('name')
    sizes = Size.objects.select_related('product').order_by('product__name', 'size_value')
    return render(request, 'setup/home.html', {
        'schools': schools,
        'products': products,
        'sizes': sizes,
        'school_count': schools.count(),
        'product_count': products.count(),
        'sku_count': SchoolProduct.objects.count(),
    })


def setup_school_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        if not name or not code:
            messages.error(request, 'School name and code are required.')
            return redirect('setup_home')
        if School.objects.filter(name__iexact=name).exists():
            messages.error(request, f'School "{name}" already exists.')
            return redirect('setup_home')
        School.objects.create(name=name, code=code)
        messages.success(request, f'School "{name}" added successfully.')
    return redirect('setup_home')


def setup_school_delete(request, pk):
    if request.method == 'POST':
        school = School.objects.filter(pk=pk).first()
        if school:
            name = school.name
            if school.bills.exists() or StockTransaction.objects.filter(school_product__school=school).exists() or ManufacturingOrder.objects.filter(school_product__school=school).exists():
                messages.error(request, f'Cannot delete "{name}" — it has existing bills, orders, or stock records. Remove those first.')
            else:
                school.delete()
                messages.success(request, f'School "{name}" deleted.')
        else:
            messages.warning(request, 'School was already deleted.')
    return redirect('setup_home')


def setup_product_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Product name is required.')
            return redirect('setup_home')
        if Product.objects.filter(name__iexact=name).exists():
            messages.error(request, f'Product "{name}" already exists.')
            return redirect('setup_home')
        Product.objects.create(name=name)
        messages.success(request, f'Product "{name}" added.')
    return redirect('setup_home')


def setup_product_delete(request, pk):
    if request.method == 'POST':
        product = Product.objects.filter(pk=pk).first()
        if product:
            name = product.name
            if StockTransaction.objects.filter(school_product__product=product).exists() or BillItem.objects.filter(school_product__product=product).exists() or ManufacturingOrder.objects.filter(school_product__product=product).exists():
                messages.error(request, f'Cannot delete "{name}" — it has existing transactions, bills, or orders.')
            else:
                product.delete()
                messages.success(request, f'Product "{name}" deleted.')
        else:
            messages.warning(request, 'Product was already deleted.')
    return redirect('setup_home')


def setup_size_add(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        size_value = request.POST.get('size_value', '').strip()
        if not product_id or not size_value:
            messages.error(request, 'Product and size value are required.')
            return redirect('setup_home')
        product = get_object_or_404(Product, pk=product_id)
        if Size.objects.filter(product=product, size_value__iexact=size_value).exists():
            messages.error(request, f'Size "{size_value}" already exists for {product.name}.')
            return redirect('setup_home')
        Size.objects.create(product=product, size_value=size_value)
        messages.success(request, f'Size "{size_value}" added for {product.name}.')
    return redirect('setup_home')


def setup_size_delete(request, pk):
    if request.method == 'POST':
        size = Size.objects.filter(pk=pk).first()
        if size:
            label = str(size)
            if StockTransaction.objects.filter(school_product__size=size).exists() or BillItem.objects.filter(school_product__size=size).exists() or ManufacturingOrder.objects.filter(school_product__size=size).exists():
                messages.error(request, f'Cannot delete size "{label}" — it is used in transactions, bills, or orders.')
            else:
                size.delete()
                messages.success(request, f'Size "{label}" deleted.')
        else:
            messages.warning(request, 'Size was already deleted.')
    return redirect('setup_home')


def setup_link_add(request):
    """Link a school + product + size together with a price."""
    if request.method == 'POST':
        school_id   = request.POST.get('school_id')
        product_id  = request.POST.get('product_id')
        size_id     = request.POST.get('size_id')
        price       = request.POST.get('price', '').strip()

        if not all([school_id, product_id, size_id]):
            messages.error(request, 'School, product, and size are all required.')
            return redirect('setup_home')

        if school_id == 'general':
            school = None
            school_name = 'General Items'
        else:
            school = get_object_or_404(School, pk=school_id)
            school_name = school.name
            
        product = get_object_or_404(Product, pk=product_id)
        size    = get_object_or_404(Size, pk=size_id)

        if SchoolProduct.objects.filter(school=school, product=product, size=size).exists():
            messages.error(request, f'This combination already exists.')
            return redirect('setup_home')

        sp = SchoolProduct.objects.create(
            school=school, product=product, size=size,
            price=price if price else None,
            stock=0,
        )
        messages.success(request, f'Added: {school_name} → {product.name} ({size.size_value}). SKU: {sp.sku_code}')
    return redirect('setup_home')


def setup_link_bulk(request):
    """Bulk-link: add a product+all-its-sizes to a school at once."""
    if request.method == 'POST':
        school_id  = request.POST.get('school_id')
        product_id = request.POST.get('product_id')
        price      = request.POST.get('price', '').strip()

        if school_id == 'general':
            school = None
            school_name = 'General Items'
        else:
            school  = get_object_or_404(School, pk=school_id)
            school_name = school.name
            
        product = get_object_or_404(Product, pk=product_id)
        sizes   = Size.objects.filter(product=product)

        if not sizes.exists():
            messages.error(request, f'No sizes defined for {product.name}. Add sizes first.')
            return redirect('setup_home')

        created = 0
        for size in sizes:
            obj, made = SchoolProduct.objects.get_or_create(
                school=school, product=product, size=size,
                defaults={'price': price if price else None, 'stock': 0}
            )
            if made:
                created += 1

        messages.success(request, f'{created} size(s) linked for {school_name} → {product.name}.')
    return redirect('setup_home')


# ─── Analytics Dashboard ───────────────────────────────────────────────────────

def analytics_dashboard(request):
    from datetime import date as date_type
    import calendar

    valid_bills = Bill.objects.filter(is_void=False)
    today       = timezone.now().date()

    # ── Available Years ──────────────────────────────────────────
    year_list = sorted(set(
        valid_bills.values_list('created_at__year', flat=True).distinct()
    )) or [today.year]

    # ── GET params ───────────────────────────────────────────────
    sel_year     = int(request.GET.get('year',      today.year))
    sel_month    = request.GET.get('month',    '')
    sel_day      = request.GET.get('day',      '')
    sel_week_day = request.GET.get('week_day', '')  # date string YYYY-MM-DD

    # ── LAST 7 DAYS STRIP ────────────────────────────────────────
    week_days = []
    for i in range(6, -1, -1):               # 6 days ago → today
        d = today - timedelta(days=i)
        rev = valid_bills.filter(created_at__date=d).aggregate(r=Sum('total_amount'))['r'] or 0
        week_days.append({
            'date':     d,
            'date_str': str(d),
            'label':    d.strftime('%a'),     # Mon, Tue …
            'num':      d.day,
            'day_num':  d.day,
            'revenue':  float(rev),
            'is_today': d == today,
        })

    # Selected week-day detail
    week_day_rev   = 0
    week_day_bills = 0
    week_day_obj   = None
    if sel_week_day:
        try:
            wd = date_type.fromisoformat(sel_week_day)
            week_day_obj   = wd
            qs_wd          = valid_bills.filter(created_at__date=wd)
            week_day_rev   = qs_wd.aggregate(r=Sum('total_amount'))['r'] or 0
            week_day_bills = qs_wd.count()
        except ValueError:
            pass

    # ── YEARLY total ─────────────────────────────────────────────
    qs_year        = valid_bills.filter(created_at__year=sel_year)
    yearly_revenue = qs_year.aggregate(r=Sum('total_amount'))['r'] or 0
    yearly_bills   = qs_year.count()

    # ── MONTHLY GRID ─────────────────────────────────────────────
    monthly_rows = (
        qs_year.annotate(m=TruncMonth('created_at'))
        .values('m')
        .annotate(revenue=Sum('total_amount'), bills=Count('id'))
        .order_by('m')
    )
    month_map = {r['m'].month: {'revenue': float(r['revenue']), 'bills': r['bills']}
                 for r in monthly_rows}
    months_data = [
        {'num': mn, 'name': calendar.month_abbr[mn],
         'revenue': month_map.get(mn, {}).get('revenue', 0),
         'bills':   month_map.get(mn, {}).get('bills',   0)}
        for mn in range(1, 13)
    ]

    # ── MONTHLY DETAIL ───────────────────────────────────────────
    monthly_revenue = 0
    monthly_bills   = 0
    daily_rows      = []
    if sel_month:
        mn      = int(sel_month)
        qs_m    = valid_bills.filter(created_at__year=sel_year, created_at__month=mn)
        monthly_revenue = qs_m.aggregate(r=Sum('total_amount'))['r'] or 0
        monthly_bills   = qs_m.count()
        daily_rows = [
            {'day': r['d'].day, 'revenue': float(r['revenue']), 'bills': r['bills']}
            for r in (
                qs_m.annotate(d=TruncDay('created_at'))
                .values('d')
                .annotate(revenue=Sum('total_amount'), bills=Count('id'))
                .order_by('d')
            )
        ]

    # ── DAILY DETAIL (from monthly table click) ───────────────────
    day_revenue = 0
    day_bills   = 0
    if sel_month and sel_day:
        dd          = date_type(sel_year, int(sel_month), int(sel_day))
        qs_d        = valid_bills.filter(created_at__date=dd)
        day_revenue = qs_d.aggregate(r=Sum('total_amount'))['r'] or 0
        day_bills   = qs_d.count()

    # ── SEASONAL — only Summer & Winter ──────────────────────────
    def s_rev(months_list):
        return float(
            valid_bills.filter(created_at__year=sel_year, created_at__month__in=months_list)
            .aggregate(r=Sum('total_amount'))['r'] or 0
        )

    seasons = [
        {'name': 'Summer', 'months': 'Apr – Sep', 'rev': s_rev([4,5,6,7,8,9]),    'icon': '☀️', 'color': '#f59e0b'},
        {'name': 'Winter', 'months': 'Oct – Mar', 'rev': s_rev([10,11,12,1,2,3]), 'icon': '❄️', 'color': '#3b82f6'},
    ]

    # ── Chart data ────────────────────────────────────────────────
    chart_labels = json.dumps([m['name'] for m in months_data])
    chart_data   = json.dumps([m['revenue'] for m in months_data])

    ctx = {
        'today':            today,
        'year_list':        year_list,
        'sel_year':         sel_year,
        'sel_month':        sel_month,
        'sel_month_name':   calendar.month_name[int(sel_month)] if sel_month else '',
        'sel_day':          sel_day,
        'sel_week_day':     sel_week_day,
        # 7-day strip
        'week_days':        week_days,
        'week_day_rev':     week_day_rev,
        'week_day_bills':   week_day_bills,
        'week_day_obj':     week_day_obj,
        # Yearly
        'yearly_revenue':   yearly_revenue,
        'yearly_bills':     yearly_bills,
        # Monthly
        'months_data':      months_data,
        'monthly_revenue':  monthly_revenue,
        'monthly_bills':    monthly_bills,
        'daily_rows':       daily_rows,
        # Day detail
        'day_revenue':      day_revenue,
        'day_bills':        day_bills,
        # Seasonal
        'seasons':          seasons,
        # Chart
        'chart_labels':     chart_labels,
        'chart_data':       chart_data,
    }
    return render(request, 'dashboard/analytics.html', ctx)
