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
from django.utils.crypto import get_random_string
from django.core.paginator import Paginator
from django.db.models import Count, Q, F


# Create your views here.


from django.db.models import Count

def home(request):
    main_tags = ["Men Wear", "Women Wear", "Kids Wear"]

    tag_data = []

    for tag_name in main_tags:
        tag = Tag.objects.filter(name__iexact=tag_name).first()

        if not tag:
            tag = Tag.objects.exclude(name__in=main_tags).first()

        if tag:
            product = (
                Product.objects.filter(tags__tag=tag)
                .order_by("price")
                .first()
            )

            tag_data.append({
                "tag": tag,
                "product": product
            })

    # Featured section er jonno
    featured_products = (
        Product.objects.filter(is_featured=True)
        .prefetch_related("images")[:10]
    )

    # New Arrivals (main slider)
    new_arrivals = (
        Product.objects.all()
        .prefetch_related("images")
        .order_by("-created_at")[:10]
    )

    # Category carousel
    cat = (
        Category.objects
        .annotate(product_count=Count("products"))
        .filter(product_count__gt=0)
        .prefetch_related("products__images")
    )

    # ---------- BOTTOM 4 LISTS ----------

    # 1) Best Selling Products (orderitem related_name use kore)
    best_selling_products = (
        Product.objects
        .annotate(total_sold=Count("orderitem"))
        .prefetch_related("images")
        .order_by("-total_sold", "-id")[:4]
    )

    # 2) Featured Products (nicher choto list er jonno)
    bottom_featured_products = featured_products[:4]

    # 3) New Arrivals (nicher list er jonno)
    bottom_new_arrivals = new_arrivals[:4]

    # 4) Top Rated Products (wishlist count diye approx rating)
    top_rated_products = (
        Product.objects
        .annotate(wishlist_count=Count("wishlist"))
        .prefetch_related("images")
        .order_by("-wishlist_count", "-id")[:4]
    )

    context = {
        "tag_data": tag_data,
        "featured_products": featured_products,
        "new_arrivals": new_arrivals,
        "categories": cat,

        # bottom lists
        "best_selling_products": best_selling_products,
        "bottom_featured_products": bottom_featured_products,
        "bottom_new_arrivals": bottom_new_arrivals,
        "top_rated_products": top_rated_products,
    }

    return render(request, "index.html", context)




def shop_grid_top(request):
    category_slug = request.GET.get('category')
    subcategory_slug = request.GET.get('subcategory')
    products = Product.objects.all()

    if category_slug:
        products = products.filter(category__slug=category_slug)
    if subcategory_slug:
        products = products.filter(subcategory__slug=subcategory_slug)
    return render(request, 'products/shop-grid-filter-on-top.html')

def shop_grid_left_sidebar(request):
    return render(request, 'products/shop-grid-left-sidebar.html')

def shop_list_left_sidebar(request):
    return render(request, 'products/shop-list-left-sidebar.html')

def shop_categories(request):
    return render(request, 'products/shop-categories.html')

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    
    variations = product.variations.all()
    colors = variations.values('color__name', 'color__code').distinct()
    sizes = variations.values_list('size__name', flat=True).distinct()
    default_variation = variations.first()
    quantity_range = range(1, default_variation.stock + 1) if default_variation and default_variation.stock > 0 else []
    
     # -------- Similar Products Logic --------
    similar_products = []

    # Step 1️⃣: প্রথমে একই category এর product খুঁজো
    if product.category:
        similar_products = list(
            Product.objects.filter(category=product.category)
            .exclude(slug=product.slug)
            .order_by('-id')[:8]
        )

    # Step 2️⃣: যদি ৮টার কম হয়, তাহলে অন্য random product দাও
    if len(similar_products) < 8:
        extra_needed = 8 - len(similar_products)
        extra_products = list(
            Product.objects.exclude(
                Q(slug=product.slug) | Q(id__in=[p.id for p in similar_products])
            ).order_by('-id')[:extra_needed]
        )
        similar_products += extra_products

    # Step 3️⃣: যদি মোট database এ ৮টার কম product থাকে, তাহলে যতটা আছে সব দেখাবে
    if not similar_products:
        similar_products = list(
            Product.objects.exclude(slug=product.slug).order_by('-id')
        )

    # Step 4️⃣: প্রতিটি product এ প্রথম image attach করো
    for p in similar_products:
        p.first_image = ProductImage.objects.filter(product=p).first()

    
    context = {
        'product': product,
        'quantity_range': quantity_range,   
        'colors': colors,
        'sizes': sizes, 
        'similar_products': similar_products,
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
        cart_item, created = Cart.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={"quantity": quantity, "color": color, "size": size},
        )
        if not created:
            # If already exists, increment or update quantity as you prefer
            try:
                cart_item.quantity += int(quantity)
            except Exception:
                cart_item.quantity = (cart_item.quantity or 0) + 1
                cart_item.color = color
                cart_item.size = size
                cart_item.save()

        # Remove from wishlist if present
        Wishlist.objects.filter(user=request.user, product=product).delete()

        success_message = f"{product.title} added to your cart!"
        if is_ajax:
            # return optional redirect_url if you want front-end to navigate
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

    # Delete the item
    order_item.delete()

    # Recalculate order totals
    order_items = order.items.all()

    if order_items.exists():
        order.subtotal = sum(item.item_total for item in order_items)
    else:
        order.subtotal = 0

    # Shipping stays same (if fixed)
    shipping = order.shipping_charge

    # Coupon apply থাকলে discount পুনঃগণনা
    if order.discount > 0:
        # ধরুন percentage ভিত্তিক coupon ছিল
        order.discount = (order.subtotal * order.coupon.discount_percent / 100) if order.subtotal > 0 else 0

    # Total amount update
    order.total_amount = order.subtotal + shipping - order.discount

    order.save()

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
        return redirect('shopping-cart')

    # --- Cart Totals ---
    cart_data = cart_context(request)
    subtotal = cart_data['cart_subtotal']
    shipping_amount = cart_data['cart_shipping']
    coupon_discount = cart_data['cart_coupon_discount']
    total = cart_data['cart_order_total']

    # --- Handle POST request ---
    if request.method == "POST":
        # Form Data Receive
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        country_id = request.POST.get('country_id')
        division_name = request.POST.get('division_id')
        district_name = request.POST.get('district_id')
        zip_code = request.POST.get('zip_code')
        address1 = request.POST.get('address1')
        address2 = request.POST.get('address2')

        # Resolve Country Name
        country_name_value = None
        if country_id:
            try:
                country = CountryName.objects.get(id=country_id)
                country_name_value = country.nameName
            except CountryName.DoesNotExist:
                pass

        # --- Save to Session ---
        request.session['shipping_info'] = {
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

        # --- Save to ShippingAddress Table ---
        ShippingAddress.objects.create(
            user=request.user,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            country=country_name_value,
            division=division_name,
            district=district_name,
            zip_code=zip_code,
            address1=address1,
            address2=address2,
        )

        # --- Next Step Redirect ---
        return redirect('checkout-shipping')

    # --- GET Request ---
    shipping_info = request.session.get('shipping_info', {})

    # --- Division & District Display ---
    division_display = None
    district_display = None

    if shipping_info.get('division_id'):
        try:
            division = Division.objects.get(id=shipping_info['division_id'])
            division_display = getattr(division, 'name', None) or getattr(division, 'division_name', None)
        except Division.DoesNotExist:
            pass

    if shipping_info.get('district_id'):
        try:
            district = District.objects.get(id=shipping_info['district_id'])
            district_display = getattr(district, 'name', None) or getattr(district, 'district_name', None)
        except District.DoesNotExist:
            pass

    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping_amount': shipping_amount,
        'coupon_discount': coupon_discount,
        'order_total': total,
        'country_name': CountryName.objects.all(),
        'shipping_info': shipping_info,
        'division_display': division_display,
        'district_display': district_display,
    }
    return render(request, 'checkout/checkout-details.html', context)



@login_required(login_url='customer_login')
def checkout_shipping(request):
    shipping_methods = ShippingCharge.objects.filter(active=True)
    country_name = CountryName.objects.all()

    cart_data = cart_context(request)
    subtotal = cart_data['cart_subtotal']
    coupon_discount = cart_data['cart_coupon_discount']

    # --- Get shipping info from session ---
    shipping_info = request.session.get('shipping_info', {})

    # 🟢 Retrieve latest ShippingAddress from DB
    shipping_address = ShippingAddress.objects.filter(user=request.user).order_by('-created_at').first()

    if request.method == "POST":
        selected_method_id = request.POST.get("shipping_method")
        if selected_method_id:
            try:
                shipping_method = ShippingCharge.objects.get(id=selected_method_id)
            except ShippingCharge.DoesNotExist:
                messages.error(request, "Invalid shipping method.")
                return redirect("checkout-shipping")

            total_with_shipping = subtotal + shipping_method.charge_amount - coupon_discount

            # 🟢 Create Order with shipping_address linked
            order = Order.objects.create(
                user=request.user,
                shipping_method=shipping_method,
                shipping_address=shipping_address,   # ✅ FIXED LINE
                subtotal=subtotal,
                discount=coupon_discount,
                shipping_charge=shipping_method.charge_amount,
                total_amount=total_with_shipping,
            )

            # --- Save order id in session ---
            request.session['order_id'] = order.id
            messages.success(request, "Order created successfully!")

            # --- Redirect to Payment Page ---
            return redirect("checkout-payment")

    context = {
        'country_name': country_name,
        'shipping_methods': shipping_methods,
        'subtotal': subtotal,
        'coupon_discount': coupon_discount,
        'shipping_info': shipping_info,
    }
    return render(request, 'checkout/checkout-shipping.html', context)


@login_required
def checkout_payment(request):
    order_id = request.session.get('order_id')
    if not order_id:
        messages.error(request, "No order found. Please select a shipping method first.")
        return redirect('checkout-shipping')

    order = get_object_or_404(Order, id=order_id, user=request.user)

    if request.method == "POST":
        payment_method = request.POST.get('payment_method')
        if not payment_method:
            messages.error(request, "Please select a payment method.")
            return redirect('checkout-payment')

        order.payment_method = payment_method

        # --- Coupon / discount logic ---
        coupon_code = request.session.get('coupon_code')
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code__iexact=coupon_code, active=True)
                now = timezone.now()
                if coupon.valid_from <= now <= coupon.valid_to:
                    discount_amount = (order.subtotal * Decimal(coupon.discount_percent)) / 100
                    order.discount = discount_amount
            except Coupon.DoesNotExist:
                order.discount = Decimal('0.00')
        else:
            order.discount = Decimal('0.00')

        # --- Calculate totals ---
        order.total_amount = order.subtotal + order.shipping_charge - order.discount
        order.save()

        # --- Create OrderItems if they don't exist yet ---
        cart_items = Cart.objects.filter(user=request.user)
        for item in cart_items:
            # Avoid creating duplicates if user revisits payment page
            if not OrderItem.objects.filter(order=order, product=item.product, user=request.user).exists():
                unit_price = item.product.orginal_price
                total_price = unit_price * item.quantity
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    user=request.user,
                    color=item.color,
                    size=item.size,
                    price=unit_price,
                    item_total=total_price,
                    payment_method=payment_method
                )

        # ✅ Do NOT clear cart yet

        messages.success(request, "Payment method saved. Review your order before completing.")
        return redirect('checkout-review')
    
    context = {
    'order': order,
    'order_data': order,  # same data, different name
    }

    return render(request, 'checkout/checkout-payment.html', context)


@login_required(login_url='customer_login')
def checkout_review(request):
    order_id = request.session.get('order_id')
    if not order_id:
        messages.error(request, "No order found.")
        return redirect('shopping-cart')

    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.all()
    address = order.shipping_address

    # Coupon check
    coupon_code = request.session.get("coupon_code")
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code, active=True)
            now = timezone.now()
            if coupon.valid_from <= now <= coupon.valid_to:
                discount_amount = (order.subtotal * coupon.discount_percent) / 100
                order.discount = discount_amount
                order.total_amount = order.subtotal + order.shipping_charge - discount_amount
            else:
                messages.warning(request, "Coupon expired.")
        except Coupon.DoesNotExist:
            messages.warning(request, "Invalid coupon code.")
    else:
        order.discount = 0
        order.total_amount = order.subtotal + order.shipping_charge

    order.save(update_fields=["discount", "total_amount"])

    context = {
    "order": order,
    "order_items": order_items,
    "address": address,  # ✅ এখন null হবে না
    }
    return render(request, "checkout/checkout-review.html", context)





@login_required(login_url='customer_login')
def checkout_complete(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.all()
    address = order.shipping_address

    if not order_items.exists():
        messages.error(request, "No items in your order.")
        return redirect('shopping-cart')

    # Prepare snapshot data
    product_info = []
    for item in order_items:
        product_info.append({
            "title": item.product.title,
            "quantity": item.quantity,
            "price": float(item.item_total),
            "size": item.size,
            "color": item.color,
        })

    customer_info = {
        "name": f"{address.first_name} {address.last_name}" if address else "",
        "phone": address.phone if address else "",
        "email": address.email if address else "",
        "address1": address.address1 if address else "",
        "address2": address.address2 if address else "",
        "district": address.district if address else "",
        "division": address.division if address else "",
        "country": address.country if address else "",
    }

    tracking_id = get_random_string(length=12).upper()

    completed_order = CompletedOrder.objects.create(
        tracking_id=tracking_id,
        shipping_address=address,
        order=order,
        total_amount=order.total_amount,
        customer_info=customer_info,
        product_info=product_info
    )

    completed_order.order_items.set(order_items)

    # 🟢 Clear order items
    # order.items.all().delete()

    # 🟢 Clear cart items
    Cart.objects.filter(user=request.user).delete()

    # 🟢 Clear session data (optional)
    request.session.pop('order_id', None)
    request.session.pop('coupon_code', None)
    request.session.pop('shipping_info', None)

    return render(request, "checkout/checkout-complete.html", {"completed_order": completed_order})



def order_tracking(request):
    order_data = CompletedOrder.objects.first()

    return render(request, 'orders/order-tracking.html', {'order_data': order_data})


def about_page(request):
    return render(request, 'about.html')

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



# def produc_subCategory_view(request, slug):
#     view_type = request.GET.get('view', 'top')  # 'top', 'left', or 'list'
#     subCategory = get_object_or_404(SubCategory, slug=slug)
#     products = subCategory.products.all()
    

#     # Choose template dynamically
#     if view_type == 'left':
#         template = 'products/subCategory/shop-grid-left-sidebar.html'
#     elif view_type == 'list':
#         template = 'products/subCategory/shop-list-left-sidebar.html'
#     else:
#         template = 'products/subCategory/shop-grid-filter-on-top.html'

#     context = {
#         'subCategory': subCategory,
#         'products': products,
#     }
#     return render(request, template, context)





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
        item = Cart.objects.get(id=item_id, user=request.user)
        quantity = int(quantity)
        if quantity < 1:
            quantity = 1
        item.quantity = quantity
        item.save()

        # Calculate updated totals
        item_total = item.product.orginal_price * item.quantity
        cart_items = Cart.objects.filter(user=request.user)
        cart_subtotal = sum(i.product.orginal_price * i.quantity for i in cart_items)
        cart_total_items = sum(i.quantity for i in cart_items)

        return JsonResponse({
            "success": True,
            "item_total": f"{item_total:.2f}",
            "cart_subtotal": f"{cart_subtotal:.2f}",
            "cart_total_items": cart_total_items
        })
    except Cart.DoesNotExist:
        return JsonResponse({"success": False, "message": "Item not found."})

def apply_coupon(request):
    if request.method == "POST":
        code = request.POST.get("coupon_code", "").strip()
        if not code:
            messages.warning(request, "Please enter a coupon code.")
            return redirect(request.META.get("HTTP_REFERER", "cart"))

        try:
            coupon = Coupon.objects.get(code__iexact=code)
        except Coupon.DoesNotExist:
            messages.error(request, "Invalid coupon code.")
            return redirect(request.META.get("HTTP_REFERER", "cart"))

        # Check if coupon is valid
        now = timezone.now()
        if not coupon.active or not (coupon.valid_from <= now <= coupon.valid_to):
            messages.error(request, "This coupon is not valid or expired.")
            return redirect(request.META.get("HTTP_REFERER", "cart"))

        # Save coupon in session
        request.session["coupon_code"] = coupon.code
        messages.success(request, f"Coupon '{coupon.code}' applied successfully ({coupon.discount_percent}% off).")

    return redirect(request.META.get("HTTP_REFERER", "cart"))

from shopingo.context_processors import cart_context

def remove_coupon(request):
    request.session.pop("coupon_code", None)
    request.session.pop("coupon_discount", None)
    messages.success(request, "Coupon removed.")

    # 🧮 Recalculate totals
    cart_data = cart_context(request)
    subtotal = cart_data['cart_subtotal']
    shipping = cart_data['cart_shipping']

    # Optional: যদি তুমি order instance আপডেট করতে চাও
    if 'order_id' in request.session:
        from .models import Order
        try:
            order = Order.objects.get(id=request.session['order_id'])
            order.discount = 0
            order.total_amount = subtotal + shipping
            order.save()
        except Order.DoesNotExist:
            pass

    return redirect(request.META.get("HTTP_REFERER", "shop-cart"))





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






