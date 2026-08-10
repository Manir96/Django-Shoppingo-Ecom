from decimal import Decimal

from django.db.models import Count, Prefetch
from django.db.models.functions import Length

from accounts.models import CountryName

from .models import (
    Cart,
    Category,
    Coupon,
    PersonalInfo,
    ShippingCharge,
    SubCategory,
    Tag,
)


# Footer "Popular Tags" — keep column height even with other footer columns
POPULAR_TAGS_LIMIT = 12


def global_categories(request):
    categories = (
        Category.objects
        .filter(is_active=True)
        .exclude(slug="")
        .exclude(slug__isnull=True)
        .prefetch_related(
            Prefetch(
                "subcategories",
                queryset=SubCategory.objects.filter(is_active=True)
                .exclude(slug="")
                .exclude(slug__isnull=True)
                .order_by("menu_order", "name"),
            )
        )
        .order_by("menu_order", "name")
    )
    # Compact popular tags so footer columns stay even height
    tags = (
        Tag.objects
        .annotate(product_count=Count("producttag"), name_len=Length("name"))
        .filter(product_count__gt=0, name_len__lte=22)
        .exclude(name__iexact="Shopingo")
        .order_by("-product_count", "name")[:POPULAR_TAGS_LIMIT]
    )
    personal_info = PersonalInfo.objects.last()

    return {
        "categories": categories,
        "tags": tags,
        "personal_info": personal_info,
    }


def cart_context(request):
    country_name = CountryName.objects.all()
    shipping_charge_obj = ShippingCharge.objects.first()
    shipping_charge = shipping_charge_obj.charge_amount if shipping_charge_obj else Decimal("0.00")

    if request.user.is_authenticated:
        cart_items = Cart.objects.filter(user=request.user).select_related("product")

        total_items = 0
        subtotal = Decimal("0.00")
        cart_items_with_total = []

        for item in cart_items:
            item_total = Decimal(item.quantity) * Decimal(item.product.orginal_price)
            total_items += item.quantity
            subtotal += item_total
            cart_items_with_total.append({
                "item": item,
                "item_total": item_total,
            })

        shipping = shipping_charge

        coupon_discount = Decimal("0.00")
        coupon_code = request.session.get("coupon_code")

        if coupon_code:
            try:
                coupon = Coupon.objects.get(code__iexact=coupon_code, active=True)
                if coupon.is_valid() and coupon.discount_percent:
                    coupon_discount = (
                        (subtotal * Decimal(coupon.discount_percent)) / Decimal(100)
                    ).quantize(Decimal("0.01"))
                    request.session["coupon_discount"] = str(coupon_discount)
                else:
                    request.session.pop("coupon_code", None)
                    request.session.pop("coupon_discount", None)
            except Coupon.DoesNotExist:
                request.session.pop("coupon_code", None)
                request.session.pop("coupon_discount", None)

        # Prefer selected shipping charge from draft order when available
        order_id = request.session.get("order_id")
        if order_id:
            from .models import Order
            draft = Order.objects.filter(
                id=order_id, user=request.user, status=Order.STATUS_DRAFT
            ).first()
            if draft and draft.shipping_charge is not None:
                shipping = draft.shipping_charge

        order_total = (subtotal + shipping) - coupon_discount

    else:
        cart_items_with_total = []
        total_items = 0
        subtotal = Decimal("0.00")
        shipping = Decimal("0.00")
        coupon_discount = Decimal("0.00")
        order_total = Decimal("0.00")

    return {
        "cart_items_base": cart_items_with_total,
        "cart_total_items": total_items,
        "cart_subtotal": subtotal,
        "cart_shipping": shipping,
        "cart_coupon_discount": coupon_discount,
        "cart_order_total": order_total,
        "country_name": country_name,
        "shipping_charges": shipping_charge_obj,
    }
