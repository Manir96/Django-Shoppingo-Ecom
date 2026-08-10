"""Checkout validation, step guards, coupon helpers, and demo payment processing."""
from __future__ import annotations

import re
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.crypto import get_random_string

from .models import Cart, Coupon, Order, Payment, ShippingAddress

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[+]?[\d\s\-()]{8,20}$")
CARD_RE = re.compile(r"^\d{13,19}$")
CVV_RE = re.compile(r"^\d{3,4}$")

# Demo decline card (Stripe-style test number)
DECLINE_CARD = "4000000000000002"


def cart_not_empty(user) -> bool:
    return Cart.objects.filter(user=user).exists()


def has_shipping_details(session) -> bool:
    info = session.get("shipping_info") or {}
    required = ("first_name", "last_name", "email", "phone", "address1", "country_name")
    return all(str(info.get(k) or "").strip() for k in required)


def require_cart(request):
    if not cart_not_empty(request.user):
        messages.warning(request, "Your cart is empty.")
        return redirect("shopping-cart")
    return None


def require_details(request):
    blocked = require_cart(request)
    if blocked:
        return blocked
    if not has_shipping_details(request.session):
        messages.error(request, "Please complete your shipping details first.")
        return redirect("checkout-details")
    if not ShippingAddress.objects.filter(user=request.user).exists():
        messages.error(request, "Please save a shipping address first.")
        return redirect("checkout-details")
    return None


def require_draft_order(request):
    blocked = require_details(request)
    if blocked:
        return blocked
    order_id = request.session.get("order_id")
    if not order_id:
        messages.error(request, "Please select a shipping method first.")
        return redirect("checkout-shipping")
    order = Order.objects.filter(
        id=order_id, user=request.user, status=Order.STATUS_DRAFT
    ).first()
    if not order:
        request.session.pop("order_id", None)
        messages.error(request, "Your draft order expired. Please select shipping again.")
        return redirect("checkout-shipping")
    return order


def require_payment_selected(request):
    order = require_draft_order(request)
    if not isinstance(order, Order):
        return order  # redirect
    if not hasattr(order, "payment") or order.payment is None:
        messages.error(request, "Please select a payment method first.")
        return redirect("checkout-payment")
    if not order.items.exists():
        messages.error(request, "Please select a payment method to sync your cart items.")
        return redirect("checkout-payment")
    return order


def validate_shipping_details(data: dict) -> list[str]:
    errors = []
    required_labels = {
        "first_name": "First name",
        "last_name": "Last name",
        "email": "Email",
        "phone": "Phone number",
        "country_id": "Country",
        "division": "Division / State",
        "district": "City / District",
        "address1": "Address",
        "zip_code": "Postal code",
    }
    for key, label in required_labels.items():
        if not str(data.get(key) or "").strip():
            errors.append(f"{label} is required.")

    email = str(data.get("email") or "").strip()
    if email and not EMAIL_RE.match(email):
        errors.append("Please enter a valid email address.")

    phone = str(data.get("phone") or "").strip()
    if phone and not PHONE_RE.match(phone):
        errors.append("Please enter a valid phone number.")

    return errors


def get_valid_coupon(code: str | None) -> Coupon | None:
    if not code:
        return None
    try:
        coupon = Coupon.objects.get(code__iexact=code.strip())
    except Coupon.DoesNotExist:
        return None
    if not coupon.is_valid():
        return None
    return coupon


def coupon_discount_for_subtotal(request, subtotal: Decimal) -> Decimal:
    coupon = get_valid_coupon(request.session.get("coupon_code"))
    if not coupon or not coupon.discount_percent:
        return Decimal("0.00")
    return (Decimal(subtotal) * Decimal(coupon.discount_percent) / Decimal("100")).quantize(
        Decimal("0.01")
    )


def apply_coupon_to_order(order: Order, request) -> None:
    discount = coupon_discount_for_subtotal(request, order.subtotal)
    order.discount = discount
    order.total_amount = order.subtotal + order.shipping_charge - discount
    order.save(update_fields=["discount", "total_amount"])
    request.session["coupon_discount"] = str(discount)


def validate_card_fields(post) -> list[str]:
    errors = []
    name = (post.get("card_owner") or "").strip()
    number = re.sub(r"\s+", "", post.get("card_number") or "")
    mm = (post.get("card_exp_mm") or "").strip()
    yy = (post.get("card_exp_yy") or "").strip()
    cvv = (post.get("card_cvv") or "").strip()

    if not name or len(name) < 2:
        errors.append("Cardholder name is required.")
    if not CARD_RE.match(number):
        errors.append("Enter a valid card number (13–19 digits).")
    if not (mm.isdigit() and 1 <= int(mm) <= 12):
        errors.append("Enter a valid expiry month (MM).")
    if not (yy.isdigit() and len(yy) in (2, 4)):
        errors.append("Enter a valid expiry year (YY).")
    if not CVV_RE.match(cvv):
        errors.append("Enter a valid CVV (3–4 digits).")
    if number == DECLINE_CARD:
        errors.append("Payment declined by the card issuer. Please try another card.")
    return errors


def process_demo_payment(order: Order, method: str, post) -> tuple[Payment | None, list[str]]:
    """Validate method-specific fields and create/update Payment (demo gateway)."""
    method = (method or "").upper()
    allowed = {c[0] for c in Payment.METHOD_CHOICES}
    if method not in allowed:
        return None, ["Invalid payment method."]

    errors: list[str] = []
    notes = ""

    if method == "CARD":
        errors = validate_card_fields(post)
        notes = f"Card ending {(post.get('card_number') or '')[-4:]}"
    elif method == "PAYPAL":
        acct = (post.get("paypal_account_type") or "").strip()
        if acct not in ("domestic", "international"):
            errors.append("Select a PayPal account type.")
        notes = f"PayPal ({acct})"
    elif method == "NETBANKING":
        bank = (post.get("bank_name") or "").strip()
        if not bank:
            errors.append("Please select a bank.")
        notes = f"Net Banking — {bank}"
    elif method == Payment.METHOD_COD:
        notes = "Cash on Delivery"

    if errors:
        return None, errors

    payment = ensure_payment_safe(order, method, order.total_amount)
    payment.notes = notes
    payment.transaction_id = payment.transaction_id or get_random_string(16).upper()

    if method == Payment.METHOD_COD:
        payment.status = Payment.STATUS_AUTHORIZED
        payment.paid_at = None
    else:
        # Demo gateway success (no real charge)
        payment.status = Payment.STATUS_COMPLETED
        payment.paid_at = timezone.now()
    payment.save()
    return payment, []


def ensure_payment_safe(order, method, amount):
    from .services import ensure_payment

    return ensure_payment(order, method, amount)
