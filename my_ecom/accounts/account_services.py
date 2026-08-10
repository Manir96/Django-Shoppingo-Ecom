"""Helpers for the My Account area."""
from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal

from django.db.models import Prefetch, Sum
from django.utils import timezone

from shopingo.models import (
    AccountNotification,
    Cart,
    CompletedOrder,
    DigitalDownload,
    Order,
    OrderItem,
    OrderStatus,
    RecentlyViewed,
    ShippingAddress,
    Wishlist,
)

PHONE_RE = re.compile(r"^[+]?[\d\s\-()]{8,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def user_orders_qs(user):
    return (
        CompletedOrder.objects.filter(order__user=user)
        .select_related(
            "order",
            "order__order_status",
            "order__payment",
            "order__invoice",
            "order__shipping_method",
            "shipping_address",
        )
        .prefetch_related(
            Prefetch(
                "order_items",
                queryset=OrderItem.objects.select_related("product").prefetch_related("product__images"),
            )
        )
        .order_by("-completed_at")
    )


def get_owned_completed_order(user, completed_id: int) -> CompletedOrder | None:
    return user_orders_qs(user).filter(id=completed_id).first()


def order_status_slug(order: Order) -> str:
    if order.order_status_id and order.order_status:
        return order.order_status.status
    return "confirmed"


def dashboard_stats(user) -> dict:
    completed = list(
        CompletedOrder.objects.filter(order__user=user).select_related("order__order_status")
    )
    total = len(completed)
    counts = {
        "pending": 0,
        "processing": 0,
        "delivered": 0,
        "cancelled": 0,
        "shipped": 0,
    }
    spending = Decimal("0.00")
    for co in completed:
        spending += Decimal(co.total_amount or 0)
        slug = order_status_slug(co.order)
        if slug in ("pending", "confirmed"):
            counts["pending"] += 1
        elif slug in ("onway", "picked"):
            counts["shipped"] += 1
            counts["processing"] += 1
        elif slug in ("processing", "ready"):
            counts["processing"] += 1
        elif slug == "delivered":
            counts["delivered"] += 1
        elif slug == "cancelled":
            counts["cancelled"] += 1
        else:
            counts["processing"] += 1

    # Membership + loyalty from lifetime spend
    spend_f = float(spending)
    if spend_f >= 2000:
        membership = "Premium"
        tier_min, tier_max = 2000, 2000
        next_tier = None
        progress = 100
    elif spend_f >= 500:
        membership = "Gold"
        tier_min, tier_max = 500, 2000
        next_tier = "Premium"
        progress = min(100, int(((spend_f - tier_min) / (tier_max - tier_min)) * 100))
    else:
        membership = "Silver"
        tier_min, tier_max = 0, 500
        next_tier = "Gold"
        progress = min(100, int((spend_f / tier_max) * 100)) if tier_max else 0

    reward_points = int(spending)  # 1 point per $1 spent

    return {
        "total_orders": total,
        "pending_orders": counts["pending"],
        "processing_orders": counts["processing"],
        "shipped_orders": counts["shipped"],
        "delivered_orders": counts["delivered"],
        "cancelled_orders": counts["cancelled"],
        "wishlist_count": Wishlist.objects.filter(user=user).count(),
        "cart_count": Cart.objects.filter(user=user).aggregate(n=Sum("quantity"))["n"] or 0,
        "total_spending": spending,
        "reward_points": reward_points,
        "membership": membership,
        "next_tier": next_tier,
        "tier_progress": progress,
        "tier_max": tier_max,
    }


def profile_completion(user) -> int:
    checks = [
        bool(user.first_name),
        bool(user.last_name),
        bool(user.phone),
        bool(getattr(user, "avatar", None) and user.avatar),
        bool(user.gender),
        bool(user.date_of_birth),
        ShippingAddress.objects.filter(user=user).exists(),
    ]
    return int((sum(1 for c in checks if c) / len(checks)) * 100)


def time_greeting() -> str:
    hour = timezone.localtime().hour
    if hour < 12:
        return "Good Morning"
    if hour < 17:
        return "Good Afternoon"
    return "Good Evening"


def recommended_products(user, limit=8):
    from shopingo.models import Product

    purchased_ids = list(
        OrderItem.objects.filter(order__user=user, order__status=Order.STATUS_PLACED)
        .values_list("product_id", flat=True)
        .distinct()[:20]
    )
    qs = (
        Product.objects.filter(is_featured=True)
        .exclude(id__in=purchased_ids)
        .prefetch_related("images")
        .order_by("-id")
    )
    products = list(qs[:limit])
    if len(products) < limit:
        extra = list(
            Product.objects.exclude(id__in=[p.id for p in products] + purchased_ids)
            .prefetch_related("images")
            .order_by("-is_bestseller", "-id")[: limit - len(products)]
        )
        products.extend(extra)
    return products


def validate_address_payload(data: dict) -> list[str]:
    errors = []
    required = {
        "first_name": "First name",
        "last_name": "Last name",
        "email": "Email",
        "phone": "Phone",
        "country": "Country",
        "division": "Division / State",
        "district": "City / District",
        "zip_code": "Postal code",
        "address1": "Address",
    }
    for key, label in required.items():
        if not str(data.get(key) or "").strip():
            errors.append(f"{label} is required.")
    email = str(data.get("email") or "").strip()
    if email and not EMAIL_RE.match(email):
        errors.append("Enter a valid email address.")
    phone = str(data.get("phone") or "").strip()
    if phone and not PHONE_RE.match(phone):
        errors.append("Enter a valid phone number.")
    return errors


def set_default_address(user, address: ShippingAddress):
    ShippingAddress.objects.filter(
        user=user, address_type=address.address_type, is_default=True
    ).exclude(pk=address.pk).update(is_default=False)
    address.is_default = True
    address.save(update_fields=["is_default", "updated_at"])


def create_notification(user, title: str, message: str = "", link: str = "", ntype: str = "system"):
    return AccountNotification.objects.create(
        user=user, title=title, message=message, link=link, ntype=ntype or "system"
    )


def track_recently_viewed(user, product):
    if not user.is_authenticated:
        return
    RecentlyViewed.objects.update_or_create(
        user=user, product=product, defaults={"viewed_at": timezone.now()}
    )
    # Keep last 20
    ids = list(
        RecentlyViewed.objects.filter(user=user)
        .order_by("-viewed_at")
        .values_list("id", flat=True)[20:]
    )
    if ids:
        RecentlyViewed.objects.filter(id__in=ids).delete()


def ensure_digital_downloads(order: Order):
    """Create download entitlements for digital line items."""
    for item in order.items.select_related("product"):
        product = item.product
        if not product.is_digital or not product.digital_file:
            continue
        expires = None
        if product.download_expiry_days:
            expires = timezone.now() + timedelta(days=product.download_expiry_days)
        DigitalDownload.objects.get_or_create(
            user=order.user,
            order_item=item,
            defaults={
                "order": order,
                "product": product,
                "download_limit": product.download_limit,
                "expires_at": expires,
            },
        )


def can_cancel_order(order: Order) -> bool:
    slug = order_status_slug(order)
    return slug in ("pending", "confirmed", "processing")


def cancel_order(order: Order) -> bool:
    if not can_cancel_order(order):
        return False
    status, _ = OrderStatus.objects.get_or_create(status="cancelled")
    order.order_status = status
    order.save(update_fields=["order_status"])
    create_notification(
        order.user,
        "Order cancelled",
        f"Order #{order.id} has been cancelled.",
        f"/account-orders/{order.completion.id}/" if hasattr(order, "completion") else "/account-orders/",
    )
    return True


def reorder_to_cart(user, completed: CompletedOrder) -> int:
    added = 0
    for item in completed.order_items.select_related("product"):
        cart_item, created = Cart.objects.get_or_create(
            user=user,
            product=item.product,
            color=item.color or "",
            size=item.size or "",
            defaults={"quantity": item.quantity},
        )
        if not created:
            cart_item.quantity += item.quantity
            cart_item.save(update_fields=["quantity"])
        added += 1
    return added


def default_checkout_address(user) -> ShippingAddress | None:
    return (
        ShippingAddress.objects.filter(user=user, address_type="shipping", is_default=True).first()
        or ShippingAddress.objects.filter(user=user, address_type="shipping").first()
        or ShippingAddress.objects.filter(user=user).first()
    )
