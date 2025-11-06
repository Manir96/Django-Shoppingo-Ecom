from django.shortcuts import render
from .models import *
from django.shortcuts import get_object_or_404, render
from accounts.models import CountryName
from decimal import Decimal
from django.utils import timezone

def global_categories(request):
    categories = Category.objects.prefetch_related('subcategories').all()
    tag = Tag.objects.all()



    return {
        'categories': categories,
        'tags': tag,
        }




def cart_context(request):
    country_name = CountryName.objects.all()
    shipping_charge_obj = ShippingCharge.objects.first()
    shipping_charge = shipping_charge_obj.charge_amount if shipping_charge_obj else Decimal("0.00")

    if request.user.is_authenticated:
        cart_items = Cart.objects.filter(user=request.user).select_related('product')

        total_items = 0
        subtotal = Decimal("0.00")
        cart_items_with_total = []

        for item in cart_items:
            item_total = Decimal(item.quantity) * Decimal(item.product.orginal_price)
            total_items += item.quantity
            subtotal += item_total
            cart_items_with_total.append({
                'item': item,
                'item_total': item_total,
            })

        # ---------- Shipping ----------
        if subtotal >= 100:
            shipping = shipping_charge  # তোমার সেটিং অনুযায়ী
        else:
            shipping = shipping_charge

        # ---------- Coupon ----------
        coupon_discount = Decimal("0.00")
        coupon_code = request.session.get('coupon_code')

        if coupon_code:
            try:
                coupon = Coupon.objects.get(code__iexact=coupon_code, active=True)
                now = timezone.now()
                if coupon.valid_from <= now <= coupon.valid_to:
                    if coupon.discount_percent:
                        coupon_discount = (subtotal * Decimal(coupon.discount_percent)) / Decimal(100)
            except Coupon.DoesNotExist:
                pass

        # ---------- Total ----------
        order_total = (subtotal + shipping) - coupon_discount

    else:
        cart_items_with_total = []
        total_items = 0
        subtotal = Decimal("0.00")
        shipping = Decimal("0.00")
        coupon_discount = Decimal("0.00")
        order_total = Decimal("0.00")

    return {
        'cart_items_base': cart_items_with_total,
        'cart_total_items': total_items,
        'cart_subtotal': subtotal,
        'cart_shipping': shipping,
        'cart_coupon_discount': coupon_discount,
        'cart_order_total': order_total,
        'country_name': country_name,
        'shipping_charges': shipping_charge_obj,
    }