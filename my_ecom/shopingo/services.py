"""Checkout, stock, payment, invoice, and order-email helpers."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string

from .models import (
    Cart,
    CompletedOrder,
    Invoice,
    Order,
    OrderStatus,
    Payment,
    Product,
    Variation,
)


class StockError(Exception):
    """Raised when requested quantity exceeds available stock."""


def resolve_variation(product: Product, color: str | None = None, size: str | None = None):
    qs = Variation.objects.filter(product=product)
    if color:
        qs = qs.filter(color__name__iexact=str(color).strip())
    if size:
        qs = qs.filter(size__name__iexact=str(size).strip())
    return qs.select_related('color', 'size').first()


def get_available_stock(product: Product, color: str | None = None, size: str | None = None) -> int:
    variation = resolve_variation(product, color=color, size=size)
    if variation is not None:
        return int(variation.stock or 0)
    return int(product.stock or 0)


def validate_quantity_against_stock(product, quantity, color=None, size=None, extra_in_cart=0):
    available = get_available_stock(product, color=color, size=size)
    needed = int(quantity) + int(extra_in_cart)
    if needed > available:
        raise StockError(
            f'Only {available} unit(s) of "{product.title}" available in stock.'
        )
    return available


def validate_cart_stock(user):
    """Validate every cart line. Returns list of error messages (empty if OK)."""
    errors = []
    for item in Cart.objects.filter(user=user).select_related('product'):
        try:
            validate_quantity_against_stock(
                item.product,
                item.quantity,
                color=item.color,
                size=item.size,
            )
        except StockError as exc:
            errors.append(str(exc))
    return errors


@transaction.atomic
def reduce_stock_for_order(order: Order):
    """Decrement product/variation stock for each order item. Raises StockError if insufficient."""
    for item in order.items.select_related('product'):
        product = Product.objects.select_for_update().get(pk=item.product_id)
        variation = resolve_variation(product, color=item.color, size=item.size)
        if variation is not None:
            variation = Variation.objects.select_for_update().get(pk=variation.pk)
            if variation.stock < item.quantity:
                raise StockError(
                    f'Insufficient stock for "{product.title}" '
                    f'({item.color or "-"} / {item.size or "-"}).'
                )
            variation.stock -= item.quantity
            variation.save(update_fields=['stock'])
            product.stock = max(0, product.stock - item.quantity)
            product.save(update_fields=['stock'])
        else:
            if product.stock < item.quantity:
                raise StockError(f'Insufficient stock for "{product.title}".')
            product.stock -= item.quantity
            product.save(update_fields=['stock'])


def ensure_payment(order: Order, method: str, amount: Decimal | None = None) -> Payment:
    amount = amount if amount is not None else order.total_amount
    method = (method or Payment.METHOD_COD).upper()
    allowed = {c[0] for c in Payment.METHOD_CHOICES}
    if method not in allowed:
        method = Payment.METHOD_COD

    payment, _ = Payment.objects.update_or_create(
        order=order,
        defaults={
            'method': method,
            'status': Payment.STATUS_PENDING,
            'amount': amount,
        },
    )
    return payment


def create_invoice(order: Order, completed_order: CompletedOrder | None = None) -> Invoice:
    if hasattr(order, 'invoice'):
        return order.invoice

    invoice_number = f"INV-{timezone.now().strftime('%Y%m%d')}-{order.id:05d}-{get_random_string(4).upper()}"
    address = order.shipping_address
    billing_snapshot = {
        'order_id': order.id,
        'customer': f'{address.first_name} {address.last_name}' if address else '',
        'email': address.email if address else '',
        'phone': address.phone if address else '',
        'address1': address.address1 if address else '',
        'address2': address.address2 if address else '',
        'district': address.district if address else '',
        'division': address.division if address else '',
        'country': address.country if address else '',
    }
    return Invoice.objects.create(
        invoice_number=invoice_number,
        order=order,
        completed_order=completed_order,
        subtotal=order.subtotal,
        discount=order.discount,
        shipping_charge=order.shipping_charge,
        total_amount=order.total_amount,
        billing_snapshot=billing_snapshot,
    )


def send_order_confirmation_email(order: Order, completed_order: CompletedOrder, invoice: Invoice):
    address = order.shipping_address
    to_email = (address.email if address and address.email else None) or getattr(order.user, 'email', None)
    if not to_email:
        return False

    payment = getattr(order, 'payment', None)
    payment_line = f"{payment.method} ({payment.get_status_display()})" if payment else 'N/A'
    lines = [
        f"Thank you for your order #{order.id}!",
        '',
        f"Tracking ID: {completed_order.tracking_id}",
        f"Invoice: {invoice.invoice_number}",
        f"Payment: {payment_line}",
        f"Total: {order.total_amount}",
        '',
        'Items:',
    ]
    for item in order.items.select_related('product'):
        lines.append(
            f"- {item.quantity} x {item.product.title} "
            f"({item.color or '-'} / {item.size or '-'}) = {item.item_total}"
        )
    lines.extend([
        '',
        'We will notify you as your order progresses.',
        'You can track your order using the Tracking ID above.',
    ])

    send_mail(
        subject=f'Order Confirmation #{order.id} — {completed_order.tracking_id}',
        message='\n'.join(lines),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
        fail_silently=True,
    )
    return True


@transaction.atomic
def finalize_order(order: Order) -> tuple[CompletedOrder, Invoice, Payment]:
    """Validate stock, place order, reduce inventory, invoice, mark payment."""
    order = Order.objects.select_for_update().get(pk=order.pk)

    if order.status == Order.STATUS_PLACED and hasattr(order, 'completion'):
        return order.completion, order.invoice, order.payment

    order_items = list(order.items.select_related('product'))
    if not order_items:
        raise StockError('No items in your order.')

    # Re-validate stock from current inventory
    for item in order_items:
        validate_quantity_against_stock(
            item.product,
            item.quantity,
            color=item.color,
            size=item.size,
        )

    reduce_stock_for_order(order)

    confirmed_status, _ = OrderStatus.objects.get_or_create(status='confirmed')
    order.status = Order.STATUS_PLACED
    order.order_status = confirmed_status
    order.placed_at = timezone.now()
    order.save(update_fields=['status', 'order_status', 'placed_at'])

    payment = getattr(order, 'payment', None)
    if payment is None:
        payment = ensure_payment(order, Payment.METHOD_COD, order.total_amount)

    payment.amount = order.total_amount
    if not payment.transaction_id:
        payment.transaction_id = get_random_string(16).upper()

    if payment.method == Payment.METHOD_COD:
        # COD: authorized at place-order; paid on delivery
        payment.status = Payment.STATUS_AUTHORIZED
        payment.paid_at = None
    else:
        # Online methods already completed (or pending) at payment step — keep completed
        if payment.status == Payment.STATUS_PENDING:
            payment.status = Payment.STATUS_COMPLETED
        if not payment.paid_at and payment.status == Payment.STATUS_COMPLETED:
            payment.paid_at = timezone.now()
    payment.save()

    address = order.shipping_address
    product_info = [
        {
            'title': item.product.title,
            'quantity': item.quantity,
            'price': float(item.item_total),
            'size': item.size,
            'color': item.color,
        }
        for item in order_items
    ]
    customer_info = {
        'name': f'{address.first_name} {address.last_name}' if address else '',
        'phone': address.phone if address else '',
        'email': address.email if address else '',
        'address1': address.address1 if address else '',
        'address2': address.address2 if address else '',
        'district': address.district if address else '',
        'division': address.division if address else '',
        'country': address.country if address else '',
    }

    tracking_id = get_random_string(length=12).upper()
    while CompletedOrder.objects.filter(tracking_id=tracking_id).exists():
        tracking_id = get_random_string(length=12).upper()

    completed_order = CompletedOrder.objects.create(
        tracking_id=tracking_id,
        shipping_address=address,
        order=order,
        total_amount=order.total_amount,
        customer_info=customer_info,
        product_info=product_info,
    )
    completed_order.order_items.set(order_items)

    invoice = create_invoice(order, completed_order)

    # Account side-effects: digital downloads + notification
    try:
        from accounts.account_services import create_notification, ensure_digital_downloads
        ensure_digital_downloads(order)
        create_notification(
            order.user,
            f"Order #{order.id} placed",
            f"Tracking ID: {completed_order.tracking_id}. Total: {order.total_amount}.",
            f"/account-orders/{completed_order.id}/",
            ntype="order",
        )
    except Exception:
        pass

    return completed_order, invoice, payment
