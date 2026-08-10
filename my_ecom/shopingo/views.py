from django.shortcuts import render, get_object_or_404, redirect
from .models import *
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from accounts.models import *
from decimal import Decimal
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)
from shopingo.context_processors import cart_context
from shopingo.services import (
    StockError,
    finalize_order,
    send_order_confirmation_email,
    validate_cart_stock,
    validate_quantity_against_stock,
)
from shopingo.checkout_utils import (
    apply_coupon_to_order,
    get_valid_coupon,
    process_demo_payment,
    require_details,
    require_draft_order,
    require_payment_selected,
    validate_shipping_details,
)
from django.utils.crypto import get_random_string
from django.core.paginator import Paginator
from django.db.models import Count, Q, F
from django.views.decorators.http import require_http_methods


# Create your views here.


from django.db.models import Count

def home(request):
    main_tags = ["Electronics", "Fashion", "Home & Kitchen", "Beauty", "Men Wear", "Women Wear", "Kids Wear"]

    tag_data = []
    for tag_name in main_tags:
        tag = Tag.objects.filter(name__iexact=tag_name).first()
        if not tag:
            continue
        product = (
            Product.objects.filter(tags__tag=tag)
            .prefetch_related("images")
            .order_by("-is_featured", "-id")
            .first()
        )
        if product:
            tag_data.append({"tag": tag, "product": product})
        if len(tag_data) >= 3:
            break

    if len(tag_data) < 3:
        for tag in Tag.objects.all()[:6]:
            if any(t["tag"].id == tag.id for t in tag_data):
                continue
            product = Product.objects.filter(tags__tag=tag).prefetch_related("images").first()
            if product:
                tag_data.append({"tag": tag, "product": product})
            if len(tag_data) >= 3:
                break

    featured_products = Product.objects.filter(is_featured=True).prefetch_related("images")[:12]
    if not featured_products.exists():
        featured_products = Product.objects.all().prefetch_related("images")[:12]

    new_arrivals = (
        Product.objects.filter(is_new_arrival=True)
        .prefetch_related("images")
        .order_by("-created_at")[:12]
    )
    if not new_arrivals.exists():
        new_arrivals = Product.objects.all().prefetch_related("images").order_by("-created_at")[:12]

    trending_products = Product.objects.filter(is_trending=True).prefetch_related("images")[:12]
    popular_products = Product.objects.filter(is_popular=True).prefetch_related("images")[:12]
    recommended_products = Product.objects.filter(is_recommended=True).prefetch_related("images")[:12]
    flash_sale_products = Product.objects.filter(is_flash_sale=True).prefetch_related("images")[:12]

    cat = (
        Category.objects
        .annotate(product_count=Count("products"))
        .filter(product_count__gt=0, is_active=True)
        .prefetch_related("products__images")
        .order_by("menu_order", "name")
    )

    best_selling_products = (
        Product.objects.filter(is_bestseller=True).prefetch_related("images")[:8]
    )
    if not best_selling_products.exists():
        best_selling_products = (
            Product.objects
            .annotate(total_sold=Count("orderitem"))
            .prefetch_related("images")
            .order_by("-total_sold", "-id")[:8]
        )

    bottom_best_selling_products = list(best_selling_products[:4])
    bottom_featured_products = list(featured_products[:4])
    bottom_new_arrivals = list(new_arrivals[:4])
    top_rated_products = (
        Product.objects.prefetch_related("images").order_by("-rating", "-review_count")[:4]
    )

    context = {
        "tag_data": tag_data,
        "featured_products": featured_products,
        "new_arrivals": new_arrivals,
        "categories": cat,
        "trending_products": trending_products,
        "popular_products": popular_products,
        "recommended_products": recommended_products,
        "flash_sale_products": flash_sale_products,
        "best_selling_products": best_selling_products,
        "bottom_best_selling_products": bottom_best_selling_products,
        "bottom_featured_products": bottom_featured_products,
        "bottom_new_arrivals": bottom_new_arrivals,
        "top_rated_products": top_rated_products,
    }

    return render(request, "index.html", context)



def shop_categories(request):
    return render(request, 'products/shop-categories.html')

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if request.user.is_authenticated:
        from accounts.account_services import track_recently_viewed
        track_recently_viewed(request.user, product)

    if request.method == "POST" and request.POST.get("form_type") == "product_review":
        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        rating = request.POST.get("rating") or "5"
        comment = (request.POST.get("comment") or "").strip()

        if not name or not email or not comment:
            messages.error(request, "Please fill in your name, email, and review.")
        else:
            try:
                rating_int = int(rating)
            except (TypeError, ValueError):
                rating_int = 5
            rating_int = max(1, min(5, rating_int))

            ProductReview.objects.create(
                product=product,
                user=request.user if request.user.is_authenticated else None,
                name=name[:120],
                email=email,
                rating=rating_int,
                comment=comment,
                is_approved=True,
            )
            messages.success(request, "Thank you! Your review has been submitted.")
            return redirect(f"{request.path}?tab=reviews")

        return redirect(f"{request.path}?tab=reviews")

    variations = product.variations.select_related("color", "size").all()
    colors = list(
        variations.exclude(color__isnull=True)
        .exclude(color__code__isnull=True)
        .exclude(color__code="")
        .values("color__name", "color__code")
        .distinct()
    )
    sizes = list(
        variations.exclude(size__isnull=True)
        .exclude(size__name__isnull=True)
        .exclude(size__name="")
        .values_list("size__name", flat=True)
        .distinct()
    )
    default_variation = variations.first()

    # Prefer product-level stock for the qty picker; cart validates per size/color
    available_stock = 0
    if product.stock and product.stock > 0:
        available_stock = int(product.stock)
    elif default_variation and default_variation.stock > 0:
        available_stock = int(default_variation.stock)

    max_qty = min(available_stock, 20) if available_stock else 0
    quantity_range = range(1, max_qty + 1) if max_qty else []
    has_sizes = bool(sizes)
    has_colors = bool(colors)

    # -------- Similar Products Logic --------
    similar_products = []

    if product.category:
        similar_products = list(
            Product.objects.filter(category=product.category)
            .exclude(slug=product.slug)
            .order_by('-id')[:8]
        )

    if len(similar_products) < 8:
        extra_needed = 8 - len(similar_products)
        extra_products = list(
            Product.objects.exclude(
                Q(slug=product.slug) | Q(id__in=[p.id for p in similar_products])
            ).order_by('-id')[:extra_needed]
        )
        similar_products += extra_products

    if not similar_products:
        similar_products = list(
            Product.objects.exclude(slug=product.slug).order_by('-id')
        )

    for p in similar_products:
        p.first_image = ProductImage.objects.filter(product=p).first()

    reviews = product.reviews.filter(is_approved=True).order_by("-created_at")
    review_count = reviews.count()
    show_reviews_tab = request.GET.get("tab") == "reviews"

    context = {
        'product': product,
        'quantity_range': quantity_range,
        'colors': colors,
        'sizes': sizes,
        'has_sizes': has_sizes,
        'has_colors': has_colors,
        'available_stock': available_stock,
        'similar_products': similar_products,
        'reviews': reviews,
        'review_count': review_count,
        'show_reviews_tab': show_reviews_tab,
    }
    return render(request, 'products/product-details.html', context)

def product_comparison(request):
    return render(request, 'products/product-comparison')

def starter_page(request):
    return render(request, 'products/starter-page.html')






@login_required(login_url='customer_login')
def handle_product_action(request):
    if request.method != "POST":
        # Non-POST requests go home (or adjust as you wish)
        return redirect("home")

    product_id = request.POST.get("product_id")
    quantity = request.POST.get("quantity", 1)
    color = request.POST.get("color", "")
    size = request.POST.get("size", "")
    action = request.POST.get("action", "").strip()

    # Support multiple action names (aliases) for compatibility:
    # "cart" and "add_to_cart" -> add to cart
    # "wishlist" and "add_to_wishlist" -> add to wishlist
    # "remove_wishlist" remains the same
    if not product_id or not action:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": "Invalid request."})
        messages.error(request, "Invalid request.")
        return redirect("home")

    product = get_object_or_404(Product, id=product_id)

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

    # ---- ADD TO CART ----
    if action in ("cart", "add_to_cart"):
        try:
            qty = max(1, int(quantity))
        except (TypeError, ValueError):
            qty = 1

        cart_item = Cart.objects.filter(user=request.user, product=product).first()
        existing_qty = cart_item.quantity if cart_item else 0
        try:
            validate_quantity_against_stock(
                product, qty, color=color, size=size, extra_in_cart=existing_qty
            )
        except StockError as exc:
            if is_ajax:
                return JsonResponse({"success": False, "message": str(exc)})
            messages.error(request, str(exc))
            return redirect(request.META.get("HTTP_REFERER", "home"))

        if cart_item:
            cart_item.quantity = existing_qty + qty
            cart_item.color = color or cart_item.color
            cart_item.size = size or cart_item.size
            cart_item.save()
        else:
            Cart.objects.create(
                user=request.user,
                product=product,
                quantity=qty,
                color=color,
                size=size,
            )

        # Remove from wishlist if present
        Wishlist.objects.filter(user=request.user, product=product).delete()

        success_message = f"{product.title} added to your cart!"
        if is_ajax:
            return JsonResponse({"success": True, "message": success_message, "redirect_url": None})
        messages.success(request, success_message)
        return redirect("shopping-cart")

    # ---- REMOVE FROM WISHLIST ----
    elif action == "remove_wishlist":
        Wishlist.objects.filter(user=request.user, product=product).delete()
        success_message = f"{product.title} removed from your wishlist!"
        if is_ajax:
            return JsonResponse({"success": True, "message": success_message})
        messages.success(request, success_message)
        return redirect("wishlist")

    # ---- ADD TO WISHLIST ----
    elif action in ("wishlist", "add_to_wishlist"):
        wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
        if created:
            success_message = f"{product.title} added to your wishlist!"
            if is_ajax:
                return JsonResponse({"success": True, "message": success_message})
            messages.success(request, success_message)
        else:
            info_message = f"{product.title} already in your wishlist!"
            if is_ajax:
                return JsonResponse({"success": False, "message": info_message})
            messages.info(request, info_message)
        return redirect("wishlist")

    # ---- Unknown action ----
    if is_ajax:
        return JsonResponse({"success": False, "message": "Invalid action."})
    messages.error(request, "Invalid action.")
    return redirect("home")


@login_required(login_url='customer_login')
def wishlist(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    return render(request, 'products/wishlist.html', {'wishlist_items': wishlist_items})



@login_required(login_url='customer_login')
def delete_order_item(request, item_id):
    order_item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
    order = order_item.order
    if order.status == Order.STATUS_PLACED:
        messages.error(request, "Placed orders cannot be modified.")
        return redirect("checkout-review")

    order_item.delete()

    order_items = order.items.all()
    order.subtotal = sum(item.item_total for item in order_items) if order_items.exists() else Decimal("0.00")

    coupon_code = request.session.get("coupon_code")
    discount = Decimal("0.00")
    if coupon_code and order.subtotal > 0:
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code, active=True)
            now = timezone.now()
            if coupon.valid_from <= now <= coupon.valid_to and coupon.discount_percent:
                discount = (order.subtotal * Decimal(coupon.discount_percent)) / Decimal("100")
        except Coupon.DoesNotExist:
            pass

    order.discount = discount
    order.total_amount = order.subtotal + order.shipping_charge - order.discount
    order.save(update_fields=["subtotal", "discount", "total_amount"])

    return redirect("checkout-review")


@login_required(login_url='customer_login')
def remove_to_wishlist(request, item_id):
    cart_item = get_object_or_404(Cart, id=item_id, user=request.user)

    # Cart থেকে item delete করার আগে Wishlist-এ add করা
    wishlist_item, created = Wishlist.objects.get_or_create(
        user=request.user,
        product=cart_item.product,
    )
    cart_item.delete()
    messages.success(request, f"{wishlist_item.product.title} moved to wishlist!")
    return redirect('wishlist')



@login_required(login_url='customer_login')
def remove_cart_item(request, item_id):
    cart_item = get_object_or_404(Cart, id=item_id, user=request.user)
    cart_item.delete()

    # Check if AJAX
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        # recalculate cart totals
        cart_items = Cart.objects.filter(user=request.user)
        total_items = sum(item.quantity for item in cart_items)
        subtotal = sum(item.product.orginal_price * item.quantity for item in cart_items)

        return JsonResponse({
            "success": True,
            "cart_total_items": total_items,
            "cart_subtotal": f"{subtotal:.2f}"
        })

    # Normal redirect for non-AJAX requests
    messages.success(request, "Item removed from cart!")
    return redirect('shopping-cart')


@login_required(login_url='customer_login')
def shopping_cart(request):
    if request.method == "POST":
        stock_errors = validate_cart_stock(request.user)
        if stock_errors:
            for err in stock_errors:
                messages.error(request, err)
            return redirect('shopping-cart')

        # shipping তথ্য সেভ করব session-এ
        country_id = request.POST.get('country_id')
        division_id = request.POST.get('division_id')
        district_id = request.POST.get('district_id')
        zip_code = request.POST.get('zip_code')

        request.session['shipping_info'] = {
            'country_id': country_id,
            'division_id': division_id,
            'district_id': district_id,
            'zip_code': zip_code,
        }

        # এখন কার্টের তথ্য সেভ করব
        cart_items = Cart.objects.filter(user=request.user).select_related('product')
        if not cart_items.exists():
            messages.warning(request, "Your cart is empty.")
            return redirect('shopping-cart')

        cart_data = []
        for item in cart_items:
            cart_data.append({
                'product_id': item.product.id,
                'title': item.product.title,
                'quantity': item.quantity,
                'color': item.color,
                'size': item.size,
                'price': str(item.product.orginal_price),
            })

        request.session['cart_data'] = cart_data

        # checkout page এ redirect
        return redirect('checkout-details')

    # GET request হলে শুধু কার্ট পেজ দেখাও
    return render(request, 'products/shop-cart.html')



@login_required(login_url='customer_login')
def checkout_details(request):
    cart_items = Cart.objects.filter(user=request.user).select_related('product')
    if not cart_items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect('shopping-cart')

    cart_data = cart_context(request)
    from accounts.account_services import default_checkout_address
    last_address = default_checkout_address(request.user)
    shipping_info = dict(request.session.get('shipping_info') or {})

    # Prefill from session, else default saved address, else user profile
    if not shipping_info.get('first_name') and last_address:
        shipping_info = {
            'first_name': last_address.first_name,
            'last_name': last_address.last_name,
            'email': last_address.email,
            'phone': last_address.phone,
            'country_id': shipping_info.get('country_id', ''),
            'country_name': last_address.country or '',
            'division_id': last_address.division or '',
            'district_id': last_address.district or '',
            'zip_code': last_address.zip_code or '',
            'address1': last_address.address1 or '',
            'address2': last_address.address2 or '',
        }
    if not shipping_info.get('first_name'):
        shipping_info.setdefault('first_name', request.user.first_name or '')
        shipping_info.setdefault('last_name', request.user.last_name or '')
        shipping_info.setdefault('email', request.user.email or '')

    if request.method == "POST":
        first_name = (request.POST.get('first_name') or '').strip()
        last_name = (request.POST.get('last_name') or '').strip()
        email = (request.POST.get('email') or '').strip()
        phone = (request.POST.get('phone') or '').strip()
        country_id = (request.POST.get('country_id') or '').strip()
        division_name = (request.POST.get('division_id') or '').strip()
        district_name = (request.POST.get('district_id') or '').strip()
        zip_code = (request.POST.get('zip_code') or '').strip()
        address1 = (request.POST.get('address1') or '').strip()
        address2 = (request.POST.get('address2') or '').strip()

        country_name_value = ''
        if country_id:
            try:
                country_name_value = CountryName.objects.get(id=country_id).nameName
            except (CountryName.DoesNotExist, ValueError):
                country_name_value = ''

        form_data = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'phone': phone,
            'country_id': country_id,
            'division': division_name,
            'district': district_name,
            'zip_code': zip_code,
            'address1': address1,
        }
        errors = validate_shipping_details(form_data)
        if not country_name_value:
            errors.append("Please select a valid country.")

        shipping_info = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'phone': phone,
            'country_id': country_id,
            'country_name': country_name_value,
            'division_id': division_name,
            'district_id': district_name,
            'zip_code': zip_code,
            'address1': address1,
            'address2': address2,
        }

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            request.session['shipping_info'] = shipping_info
            request.session.modified = True
            addr = ShippingAddress.objects.create(
                user=request.user,
                label="Checkout",
                address_type=ShippingAddress.TYPE_SHIPPING,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                country=country_name_value,
                division=division_name,
                district=district_name,
                zip_code=zip_code,
                address1=address1,
                address2=address2 or address1,
                is_default=not ShippingAddress.objects.filter(
                    user=request.user, address_type=ShippingAddress.TYPE_SHIPPING, is_default=True
                ).exists(),
            )
            messages.success(request, "Shipping details saved.")
            return redirect('checkout-shipping')

    context = {
        'cart_items': cart_items,
        'subtotal': cart_data['cart_subtotal'],
        'shipping_amount': cart_data['cart_shipping'],
        'coupon_discount': cart_data['cart_coupon_discount'],
        'order_total': cart_data['cart_order_total'],
        'country_name': CountryName.objects.all(),
        'shipping_info': shipping_info,
        'division_display': shipping_info.get('division_id', ''),
        'district_display': shipping_info.get('district_id', ''),
    }
    return render(request, 'checkout/checkout-details.html', context)


@login_required(login_url='customer_login')
def checkout_shipping(request):
    blocked = require_details(request)
    if blocked:
        return blocked

    shipping_methods = ShippingCharge.objects.filter(active=True)
    cart_data = cart_context(request)
    subtotal = cart_data['cart_subtotal']
    coupon_discount = cart_data['cart_coupon_discount']
    shipping_info = request.session.get('shipping_info', {})
    shipping_address = ShippingAddress.objects.filter(user=request.user).order_by('-created_at').first()
    selected_id = None
    order_id = request.session.get('order_id')
    if order_id:
        draft = Order.objects.filter(id=order_id, user=request.user, status=Order.STATUS_DRAFT).first()
        if draft and draft.shipping_method_id:
            selected_id = draft.shipping_method_id

    if request.method == "POST":
        stock_errors = validate_cart_stock(request.user)
        if stock_errors:
            for err in stock_errors:
                messages.error(request, err)
            return redirect("shopping-cart")

        selected_method_id = request.POST.get("shipping_method")
        if not selected_method_id:
            messages.error(request, "Please select a shipping method.")
            return redirect("checkout-shipping")

        try:
            shipping_method = ShippingCharge.objects.get(id=selected_method_id, active=True)
        except ShippingCharge.DoesNotExist:
            messages.error(request, "Invalid shipping method.")
            return redirect("checkout-shipping")

        if not shipping_address:
            messages.error(request, "Please add a shipping address first.")
            return redirect("checkout-details")

        total_with_shipping = subtotal + shipping_method.charge_amount - coupon_discount

        order = None
        if order_id:
            order = Order.objects.filter(
                id=order_id, user=request.user, status=Order.STATUS_DRAFT
            ).first()

        if order:
            order.shipping_method = shipping_method
            order.shipping_address = shipping_address
            order.subtotal = subtotal
            order.discount = coupon_discount
            order.shipping_charge = shipping_method.charge_amount
            order.total_amount = total_with_shipping
            order.save()
        else:
            order = Order.objects.create(
                user=request.user,
                shipping_method=shipping_method,
                shipping_address=shipping_address,
                subtotal=subtotal,
                discount=coupon_discount,
                shipping_charge=shipping_method.charge_amount,
                total_amount=total_with_shipping,
                status=Order.STATUS_DRAFT,
            )

        request.session['order_id'] = order.id
        request.session['coupon_discount'] = str(coupon_discount)
        request.session.modified = True
        messages.success(request, "Shipping method saved.")
        return redirect("checkout-payment")

    shipping_amount = Decimal('0.00')
    if selected_id:
        m = shipping_methods.filter(id=selected_id).first()
        if m:
            shipping_amount = m.charge_amount

    context = {
        'country_name': CountryName.objects.all(),
        'shipping_methods': shipping_methods,
        'subtotal': subtotal,
        'coupon_discount': coupon_discount,
        'shipping_info': shipping_info,
        'shipping_amount': shipping_amount,
        'order_total': subtotal + shipping_amount - coupon_discount,
        'selected_shipping_id': selected_id,
    }
    return render(request, 'checkout/checkout-shipping.html', context)


@login_required(login_url='customer_login')
def checkout_payment(request):
    order_or_redirect = require_draft_order(request)
    if not isinstance(order_or_redirect, Order):
        return order_or_redirect
    order = order_or_redirect

    if request.method == "POST":
        payment_method = (request.POST.get('payment_method') or '').upper()
        if not payment_method:
            messages.error(request, "Please select a payment method.")
            return redirect('checkout-payment')

        stock_errors = validate_cart_stock(request.user)
        if stock_errors:
            for err in stock_errors:
                messages.error(request, err)
            return redirect('shopping-cart')

        apply_coupon_to_order(order, request)

        order.items.all().delete()
        cart_items = Cart.objects.filter(user=request.user).select_related('product')
        if not cart_items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect('shopping-cart')

        for item in cart_items:
            unit_price = item.product.orginal_price or item.product.price
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                user=request.user,
                color=item.color or '',
                size=item.size or '',
                price=unit_price,
                item_total=unit_price * item.quantity,
                payment_method=payment_method,
            )

        payment, errors = process_demo_payment(order, payment_method, request.POST)
        if errors:
            for err in errors:
                messages.error(request, err)
            return redirect('checkout-payment')

        messages.success(
            request,
            f"Payment method saved: {payment.get_method_display()}. Review your order."
        )
        return redirect('checkout-review')

    apply_coupon_to_order(order, request)
    context = {
        'order': order,
        'order_data': order,
        'payment': getattr(order, 'payment', None),
        'selected_method': getattr(getattr(order, 'payment', None), 'method', 'COD'),
    }
    return render(request, 'checkout/checkout-payment.html', context)


@login_required(login_url='customer_login')
def checkout_review(request):
    order_or_redirect = require_payment_selected(request)
    if not isinstance(order_or_redirect, Order):
        return order_or_redirect
    order = order_or_redirect

    if order.status == Order.STATUS_PLACED and hasattr(order, 'completion'):
        return redirect('checkout-complete', order_id=order.id)

    apply_coupon_to_order(order, request)
    payment = getattr(order, 'payment', None)
    # Keep payment amount in sync with totals
    if payment:
        payment.amount = order.total_amount
        payment.save(update_fields=['amount'])

    context = {
        "order": order,
        "order_items": order.items.select_related('product'),
        "address": order.shipping_address,
        "payment": payment,
        "shipping_method": order.shipping_method,
    }
    return render(request, "checkout/checkout-review.html", context)


@login_required(login_url='customer_login')
@require_http_methods(["GET", "POST"])
def checkout_complete(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Idempotent: already placed
    if order.status == Order.STATUS_PLACED and hasattr(order, 'completion'):
        invoice = getattr(order, 'invoice', None)
        return render(
            request,
            "checkout/checkout-complete.html",
            {
                "completed_order": order.completion,
                "invoice": invoice,
                "payment": getattr(order, 'payment', None),
            },
        )

    if request.method != "POST":
        return redirect('checkout-review')

    if not order.items.exists():
        messages.error(request, "No items in your order.")
        return redirect('shopping-cart')

    stock_errors = validate_cart_stock(request.user)
    if stock_errors:
        for err in stock_errors:
            messages.error(request, err)
        return redirect('shopping-cart')

    try:
        completed_order, invoice, payment = finalize_order(order)
    except StockError as exc:
        messages.error(request, str(exc))
        return redirect('shopping-cart')

    Cart.objects.filter(user=request.user).delete()
    request.session.pop('order_id', None)
    request.session.pop('coupon_code', None)
    request.session.pop('shipping_info', None)
    request.session.pop('cart_data', None)

    send_order_confirmation_email(order, completed_order, invoice)
    messages.success(request, "Your order has been placed successfully.")

    return render(
        request,
        "checkout/checkout-complete.html",
        {
            "completed_order": completed_order,
            "invoice": invoice,
            "payment": payment,
        },
    )


def order_tracking(request):
    order_data = None
    tracking_id = (request.GET.get('tracking_id') or request.POST.get('tracking_id') or '').strip()

    if request.method == "POST" or tracking_id:
        if not tracking_id:
            messages.error(request, "Please enter a tracking ID.")
        else:
            order_data = (
                CompletedOrder.objects
                .select_related(
                    'order',
                    'order__order_status',
                    'shipping_address',
                    'order__payment',
                    'order__invoice',
                )
                .filter(tracking_id__iexact=tracking_id)
                .first()
            )
            if not order_data:
                messages.error(request, "No order found for that tracking ID.")

    return render(
        request,
        'orders/order-tracking.html',
        {
            'order_data': order_data,
            'tracking_id': tracking_id,
        },
    )


@login_required(login_url='customer_login')
def invoice_detail(request, invoice_number):
    invoice = get_object_or_404(
        Invoice.objects.select_related('order', 'completed_order', 'order__payment', 'order__shipping_address'),
        invoice_number=invoice_number,
        order__user=request.user,
    )
    return render(
        request,
        'orders/invoice.html',
        {
            'invoice': invoice,
            'order': invoice.order,
            'completed_order': invoice.completed_order,
            'payment': getattr(invoice.order, 'payment', None),
            'items': invoice.order.items.select_related('product'),
        },
    )


def about_page(request):
    why_items = WhyChooseUs.objects.filter(is_active=True)
    context = {
        'why_items': why_items,
    }
    return render(request, 'about.html', context)

def contact_page(request):
    return render(request, 'contact.html')



def produc_category_view(request, slug):
    view_type = request.GET.get('view', 'top')
    current_category = get_object_or_404(Category, slug=slug)

    # Start with all products
    products = Product.objects.all().prefetch_related("variations", "images")

    # -------- Sidebar filter values --------
    selected_category_ids = request.GET.getlist("category")
    selected_brand_ids = request.GET.getlist("brand")
    selected_color_ids = request.GET.getlist("color")
    min_price = request.GET.get("min_price") or ""
    max_price = request.GET.get("max_price") or ""
    selected_discount = request.GET.get("discount") or ""
    selected_sort = request.GET.get("sort") or ""

    # -------- Top toolbox filters --------
    selected_size = request.GET.get("size") or ""
    top_color = request.GET.get("top_color") or ""
    price_range = request.GET.get("price_range") or ""
    per_page = request.GET.get("per_page") or "12"

    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 12

    # ----------------- PRODUCT FILTERING -----------------

    # Category
    if selected_category_ids:
        products = products.filter(category_id__in=selected_category_ids)
    else:
        products = products.filter(category=current_category)

    # Brand
    if selected_brand_ids:
        products = products.filter(variations__brand_id__in=selected_brand_ids)

    # Sidebar Color
    if selected_color_ids:
        products = products.filter(variations__color_id__in=selected_color_ids)

    # Size (top toolbox)
    if selected_size:
        products = products.filter(variations__size_id=selected_size)

    # Top bar color filter
    if top_color:
        products = products.filter(variations__color_id=top_color)

    # Price range -> convert to min/max only if manual min/max not given
    if price_range and not (min_price or max_price):
        mapping = {
            "5-49": (5, 49),
            "49-99": (49, 99),
            "99-149": (99, 149),
            "149-300": (149, 300),
            "300-500": (300, 500),
            "1000+": (1000, None),
        }
        pr_min, pr_max = mapping.get(price_range, (None, None))
        if pr_min is not None:
            min_price = pr_min
        if pr_max is not None:
            max_price = pr_max

    # Price filter based on discount_price (same as your original)
    if min_price:
        products = products.filter(variations__discount_price__gte=min_price)
    if max_price:
        products = products.filter(variations__discount_price__lte=max_price)

    # --------- keep copy before discount filter (for counts) ---------
    products_before_discount = products.distinct()

    # ----------------- DISCOUNT FILTER (BUCKET BASED like 1st view) -----------------
    if selected_discount:
        try:
            selected_discount_int = int(selected_discount)
        except ValueError:
            selected_discount_int = None

        if selected_discount_int is not None:
            start = (selected_discount_int - 10) + 1 if selected_discount_int > 10 else 0
            end = selected_discount_int if selected_discount_int < 90 else 100

            products = products.filter(
                variations__discount_price__gte=start,
                variations__discount_price__lte=end
            )

    products = products.distinct()

    # ----------------- SORTING (same key names you used) -----------------
    if selected_sort == "price_asc":
        products = products.order_by("price")          # যদি Product এ price থাকে
    elif selected_sort == "price_desc":
        products = products.order_by("-price")
    elif selected_sort == "newest":
        products = products.order_by("-id")

    # ----------------- PAGINATION (with per_page) -----------------
    paginator = Paginator(products, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ----------------- COUNT ANNOTATIONS -----------------
    categoriess = Category.objects.annotate(product_count=Count('products', distinct=True))
    brands = Brand.objects.annotate(product_count=Count('variation__product', distinct=True))
    colors = Color.objects.annotate(product_count=Count('variation__product', distinct=True))
    sizes = Size.objects.all()

    # ----------------- DISCOUNT BUCKET COUNT (same style as 1st view) -----------------
    discount_ranges = [10, 20, 30, 40, 50, 60, 70, 80, 90]

    # count এর জন্য discount filter ছাড়া products ব্যবহার করছি
    filtered_variations = Variation.objects.filter(product__in=products_before_discount)

    discount_data = []
    for d in discount_ranges:
        start = (d - 10) + 1 if d > 10 else 0
        end = d if d < 90 else 100   # 90% = 90–100

        count = filtered_variations.filter(
            discount_price__gte=start,
            discount_price__lte=end
        ).count()

        discount_data.append({
            "value": d,
            "count": count,
        })
    # চাইলে এখানে zero গুলোই বাদ দিতে পারো, তবে তুমি টেমপ্লেটে if দিয়ে already করছো
    # discount_data = [item for item in discount_data if item["count"] > 0]

    # ----------------- TEMPLATE SELECTION -----------------
    if view_type == 'left':
        template = 'products/category/shop-grid-left-sidebar.html'
    elif view_type == 'list':
        template = 'products/category/shop-list-left-sidebar.html'
    else:
        template = 'products/category/shop-grid-filter-on-top.html'

    # ----------------- CONTEXT -----------------
    context = {
        'category': current_category,
        'products': page_obj,
        'page_obj': page_obj,

        'categoriess': categoriess,
        'brands': brands,
        'colors': colors,
        'sizes': sizes,

        # Sidebar state
        'selected_category_ids': selected_category_ids,
        'selected_brand_ids': selected_brand_ids,
        'selected_color_ids': selected_color_ids,
        'min_price': min_price,
        'max_price': max_price,
        'selected_discount': selected_discount,
        'selected_sort': selected_sort,

        # Top toolbox state
        'selected_size': selected_size,
        'top_color': top_color,
        'price_range': price_range,
        'per_page': per_page,
        'per_page_list': [9, 12, 16, 20, 50, 100],

        'view_type': view_type,
        'discount_ranges': discount_ranges,
        'discount_data': discount_data,
    }

    return render(request, template, context)







def produc_subCategory_view(request, slug):
    view_type = request.GET.get('view', 'top')  # 'top', 'left', or 'list'

    subCategory = get_object_or_404(SubCategory, slug=slug)

    # ---------- BASE QUERY: only this subcategory ----------
    products = Product.objects.filter(
        subcategory=subCategory
    ).prefetch_related("variations", "images")

    # -------- Sidebar filter values --------
    selected_brand_ids = [b for b in request.GET.getlist("brand") if b]
    selected_color_ids = [c for c in request.GET.getlist("color") if c]
    min_price = request.GET.get("min_price") or ""
    max_price = request.GET.get("max_price") or ""
    selected_discount = request.GET.get("discount") or ""
    selected_sort = request.GET.get("sort") or ""

    # -------- Top toolbox filters --------
    selected_size = request.GET.get("size") or ""
    top_color = request.GET.get("top_color") or ""
    price_range = request.GET.get("price_range") or ""
    per_page = request.GET.get("per_page") or "12"

    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 12

    # ----------------- PRODUCT FILTERING -----------------
    # Brand
    if selected_brand_ids:
        products = products.filter(variations__brand_id__in=selected_brand_ids)

    # Sidebar Color
    if selected_color_ids:
        products = products.filter(variations__color_id__in=selected_color_ids)

    # Size (top toolbox)
    if selected_size:
        products = products.filter(variations__size_id=selected_size)

    # Top bar color filter
    if top_color:
        products = products.filter(variations__color_id=top_color)

    # Price range -> convert to min/max only if manual min/max not given
    if price_range and not (min_price or max_price):
        mapping = {
            "5-49": (5, 49),
            "49-99": (49, 99),
            "99-149": (99, 149),
            "149-300": (149, 300),
            "300-500": (300, 500),
            "1000+": (1000, None),
        }
        pr_min, pr_max = mapping.get(price_range, (None, None))
        if pr_min is not None:
            min_price = pr_min
        if pr_max is not None:
            max_price = pr_max

    # Price filter based on Variation.discount_price
    if min_price:
        products = products.filter(variations__discount_price__gte=min_price)
    if max_price:
        products = products.filter(variations__discount_price__lte=max_price)

    # --------- keep copy before discount filter (for counts) ---------
    products_before_discount = products.distinct()

    # ----------------- DISCOUNT FILTER (BUCKET BASED) -----------------
    if selected_discount:
        try:
            selected_discount_int = int(selected_discount)
        except ValueError:
            selected_discount_int = None

        if selected_discount_int is not None:
            start = (selected_discount_int - 10) + 1 if selected_discount_int > 10 else 0
            end = selected_discount_int if selected_discount_int < 90 else 100

            products = products.filter(
                variations__discount_price__gte=start,
                variations__discount_price__lte=end
            )

    products = products.distinct()

    # ----------------- SORTING -----------------
    if selected_sort == "price_asc":
        products = products.order_by("price")
    elif selected_sort == "price_desc":
        products = products.order_by("-price")
    elif selected_sort == "newest":
        products = products.order_by("-id")

    # ----------------- PAGINATION -----------------
    paginator = Paginator(products, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ----------------- SIDEBAR COUNTS (subcategory specific) -----------------
    # subcategory er under sob subcategory list dekhate chaile:
    categoriess = SubCategory.objects.filter(
        category=subCategory.category
    ).annotate(
        product_count=Count("products", distinct=True)
    )

    # Only those variations which belong to products of this subcategory
    filtered_variations = Variation.objects.filter(
        product__in=products_before_discount
    )

    brands = Brand.objects.annotate(
        product_count=Count(
            "variation__product",
            filter=Q(variation__product__in=products_before_discount),
            distinct=True,
        )
    )

    colors = Color.objects.annotate(
        product_count=Count(
            "variation__product",
            filter=Q(variation__product__in=products_before_discount),
            distinct=True,
        )
    )

    sizes = Size.objects.all()

    # ----------------- DISCOUNT BUCKET COUNT -----------------
    discount_ranges = [10, 20, 30, 40, 50, 60, 70, 80, 90]
    discount_data = []

    for d in discount_ranges:
        start = (d - 10) + 1 if d > 10 else 0
        end = d if d < 90 else 100  # 90% = 90–100
        count = filtered_variations.filter(
            discount_price__gte=start,
            discount_price__lte=end
        ).count()
        discount_data.append({
            "value": d,
            "count": count,
        })

    # ----------------- TEMPLATE SELECTION -----------------
    if view_type == 'left':
        template = 'products/subCategory/shop-grid-left-sidebar.html'
    elif view_type == 'list':
        template = 'products/subCategory/shop-list-left-sidebar.html'
    else:
        template = 'products/subCategory/shop-grid-filter-on-top.html'

    # ----------------- CONTEXT -----------------
    context = {
        "subCategory": subCategory,
        "products": page_obj,
        "page_obj": page_obj,

        # category page er sathe same naming, jeno same sidebar template reuse kora jai
        "categoriess": categoriess,
        "brands": brands,
        "colors": colors,
        "sizes": sizes,

        # Sidebar state
        "selected_brand_ids": selected_brand_ids,
        "selected_color_ids": selected_color_ids,
        "min_price": min_price,
        "max_price": max_price,
        "selected_discount": selected_discount,
        "selected_sort": selected_sort,

        # Top toolbox state
        "selected_size": selected_size,
        "top_color": top_color,
        "price_range": price_range,
        "per_page": per_page,
        "per_page_list": [9, 12, 16, 20, 50, 100],
        "view_type": view_type,

        "discount_ranges": discount_ranges,
        "discount_data": discount_data,
    }

    return render(request, template, context)






def produc_tag_view(request, slug):
    view_type = request.GET.get('view', 'top')
    tag = get_object_or_404(Tag, slug=slug)

    # 1) Tag er under e sob product
    product_ids = ProductTag.objects.filter(tag=tag).values_list('product_id', flat=True)
    products = Product.objects.filter(id__in=product_ids).prefetch_related("variations", "images")

    # -------- Sidebar filter values (category er moto) --------
    selected_brand_ids = [b for b in request.GET.getlist("brand") if b]
    selected_color_ids = [c for c in request.GET.getlist("color") if c]
    min_price = request.GET.get("min_price") or ""
    max_price = request.GET.get("max_price") or ""
    selected_discount = request.GET.get("discount") or ""
    selected_sort = request.GET.get("sort") or ""

    # -------- Top toolbox filters --------
    selected_size = request.GET.get("size") or ""
    top_color = request.GET.get("top_color") or ""
    price_range = request.GET.get("price_range") or ""
    per_page = request.GET.get("per_page") or "12"

    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 12

    # ----------------- PRODUCT FILTERING -----------------

    # Brand
    if selected_brand_ids:
        products = products.filter(variations__brand_id__in=selected_brand_ids)

    # Sidebar Color
    if selected_color_ids:
        products = products.filter(variations__color_id__in=selected_color_ids)

    # Size (top toolbox)
    if selected_size:
        products = products.filter(variations__size_id=selected_size)

    # Top bar color filter
    if top_color:
        products = products.filter(variations__color_id=top_color)

    # Price range -> convert to min/max only if manual min/max not given
    if price_range and not (min_price or max_price):
        mapping = {
            "5-49": (5, 49),
            "49-99": (49, 99),
            "99-149": (99, 149),
            "149-300": (149, 300),
            "300-500": (300, 500),
            "1000+": (1000, None),
        }
        pr_min, pr_max = mapping.get(price_range, (None, None))
        if pr_min is not None:
            min_price = pr_min
        if pr_max is not None:
            max_price = pr_max

    # Price filter based on discount_price
    if min_price:
        products = products.filter(variations__discount_price__gte=min_price)
    if max_price:
        products = products.filter(variations__discount_price__lte=max_price)

    # --------- copy before discount filter (for counts) ---------
    products_before_discount = products.distinct()

    # ----------------- DISCOUNT FILTER (bucket) -----------------
    if selected_discount:
        try:
            selected_discount_int = int(selected_discount)
        except ValueError:
            selected_discount_int = None

        if selected_discount_int is not None:
            start = (selected_discount_int - 10) + 1 if selected_discount_int > 10 else 0
            end = selected_discount_int if selected_discount_int < 90 else 100

            products = products.filter(
                variations__discount_price__gte=start,
                variations__discount_price__lte=end
            )

    products = products.distinct()

    # ----------------- SORTING -----------------
    if selected_sort == "price_asc":
        products = products.order_by("price")
    elif selected_sort == "price_desc":
        products = products.order_by("-price")
    elif selected_sort == "newest":
        products = products.order_by("-id")

    # ----------------- PAGINATION -----------------
    paginator = Paginator(products, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ----------------- SIDEBAR COUNTS (tag specific) -----------------
    # Tag specific variations for discount counts
    filtered_variations = Variation.objects.filter(product__in=products_before_discount)

    brands = Brand.objects.annotate(
        product_count=Count(
            "variation__product",
            filter=Q(variation__product__in=products_before_discount),
            distinct=True
        )
    )

    colors = Color.objects.annotate(
        product_count=Count(
            "variation__product",
            filter=Q(variation__product__in=products_before_discount),
            distinct=True
        )
    )

    sizes = Size.objects.all()

    # ----------------- DISCOUNT BUCKET COUNT -----------------
    discount_ranges = [10, 20, 30, 40, 50, 60, 70, 80, 90]
    discount_data = []

    for d in discount_ranges:
        start = (d - 10) + 1 if d > 10 else 0
        end = d if d < 90 else 100

        count = filtered_variations.filter(
            discount_price__gte=start,
            discount_price__lte=end
        ).count()

        discount_data.append({
            "value": d,
            "count": count,
        })

    # ----------------- TEMPLATE SELECT -----------------
    if view_type == 'left':
        template = 'products/tag/shop-grid-left-sidebar.html'
    elif view_type == 'list':
        template = 'products/tag/shop-list-left-sidebar.html'
    else:
        template = 'products/tag/shop-grid-filter-on-top.html'

    # ----------------- CONTEXT -----------------
    context = {
        "tag": tag,
        "products": page_obj,
        "page_obj": page_obj,

        "brands": brands,
        "colors": colors,
        "sizes": sizes,

        # Sidebar state
        "selected_brand_ids": selected_brand_ids,
        "selected_color_ids": selected_color_ids,
        "min_price": min_price,
        "max_price": max_price,
        "selected_discount": selected_discount,
        "selected_sort": selected_sort,

        # Top toolbox state
        "selected_size": selected_size,
        "top_color": top_color,
        "price_range": price_range,
        "per_page": per_page,
        "per_page_list": [9, 12, 16, 20, 50, 100],

        "view_type": view_type,
        "discount_ranges": discount_ranges,
        "discount_data": discount_data,
    }

    return render(request, template, context)




def quick_view_product(request, slug):
    product = get_object_or_404(Product, slug=slug)

    # Get variations
    variations = product.variations.all()
    colors = variations.values('color__name', 'color__code').distinct()
    sizes = variations.values_list('size__name', flat=True).distinct()
    default_variation = variations.first()
    quantity_range = range(1, default_variation.stock + 1) if default_variation and default_variation.stock > 0 else []
    

    html = render(request, 'partials/quick_view_content.html', {
        'product': product,
        'colors': colors,
        'sizes': sizes,
        'quantity_range': quantity_range,
    }).content.decode('utf-8')

    return JsonResponse({'html': html})




@require_POST
@login_required(login_url='customer_login')
def update_cart_quantity(request):
    item_id = request.POST.get("item_id")
    quantity = request.POST.get("quantity")

    try:
        item = Cart.objects.select_related('product').get(id=item_id, user=request.user)
        quantity = int(quantity)
        if quantity < 1:
            quantity = 1
        try:
            validate_quantity_against_stock(
                item.product, quantity, color=item.color, size=item.size
            )
        except StockError as exc:
            return JsonResponse({"success": False, "message": str(exc)})

        item.quantity = quantity
        item.save()

        data = cart_context(request)
        item_total = (item.product.orginal_price or item.product.price) * item.quantity
        return JsonResponse({
            "success": True,
            "item_total": f"{item_total:.2f}",
            "cart_subtotal": f"{data['cart_subtotal']:.2f}",
            "cart_shipping": f"{data['cart_shipping']:.2f}",
            "cart_coupon_discount": f"{data['cart_coupon_discount']:.2f}",
            "cart_order_total": f"{data['cart_order_total']:.2f}",
            "cart_total_items": data["cart_total_items"],
        })
    except Cart.DoesNotExist:
        return JsonResponse({"success": False, "message": "Item not found."})
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "message": "Invalid quantity."})

@login_required(login_url='customer_login')
@require_POST
def apply_coupon(request):
    code = (request.POST.get("coupon_code") or "").strip()
    referer = request.META.get("HTTP_REFERER") or "/shopping-cart/"
    if not code:
        messages.warning(request, "Please enter a coupon code.")
        return redirect(referer)

    coupon = get_valid_coupon(code)
    if not coupon:
        # Distinguish invalid vs expired
        exists = Coupon.objects.filter(code__iexact=code).exists()
        messages.error(
            request,
            "This coupon is expired or inactive." if exists else "Invalid coupon code.",
        )
        return redirect(referer)

    request.session["coupon_code"] = coupon.code
    # Refresh discount amount via cart context
    data = cart_context(request)
    request.session["coupon_discount"] = str(data["cart_coupon_discount"])
    request.session.modified = True

    order_id = request.session.get("order_id")
    if order_id:
        order = Order.objects.filter(
            id=order_id, user=request.user, status=Order.STATUS_DRAFT
        ).first()
        if order:
            apply_coupon_to_order(order, request)

    messages.success(
        request,
        f"Coupon '{coupon.code}' applied ({coupon.discount_percent}% off).",
    )
    return redirect(referer)


@login_required(login_url='customer_login')
@require_POST
def remove_coupon(request):
    request.session.pop("coupon_code", None)
    request.session.pop("coupon_discount", None)
    request.session.modified = True
    messages.success(request, "Coupon removed.")

    cart_data = cart_context(request)
    order_id = request.session.get("order_id")
    if order_id:
        order = Order.objects.filter(
            id=order_id, user=request.user, status=Order.STATUS_DRAFT
        ).first()
        if order:
            order.discount = Decimal("0.00")
            order.total_amount = order.subtotal + order.shipping_charge
            order.save(update_fields=["discount", "total_amount"])

    return redirect(request.META.get("HTTP_REFERER") or "/shopping-cart/")





# def remove_coupon(request):
#     request.session.pop("coupon_code", None)
#     request.session.pop("coupon_discount", None)
#     messages.success(request, "Coupon removed.")
#     return redirect(request.META.get("HTTP_REFERER", "shop-cart"))

def get_divisions(request):
    country_id = request.GET.get("country_id")
    divisions = Division.objects.filter(country_id=country_id).values("id", "division_name")
    return JsonResponse(list(divisions), safe=False)

def get_districts(request):
    division_id = request.GET.get("division_id")
    districts = District.objects.filter(division_id=division_id).values("id", "district_name")
    return JsonResponse(list(districts), safe=False)






