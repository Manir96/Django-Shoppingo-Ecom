from django.shortcuts import render, get_object_or_404, redirect
from .models import *
from django.http import JsonResponse
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from accounts.models import Division, District
from decimal import Decimal
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)


# Create your views here.


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

    return render(request, "index.html", {"tag_data": tag_data})



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
def shopping_cart(request):
    # cart_items = Cart.objects.filter(user=request.user).select_related('product')
    # subtotal = sum([item.product.orginal_price * item.quantity for item in cart_items])
    # context = {
    #     'cart_items': cart_items,
    #     'subtotal': subtotal,
    # }
    return render(request, 'products/shop-cart.html')



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


# @login_required(login_url='customer_login')
# def remove_cart_item(request, item_id):
#     cart_item = get_object_or_404(Cart, id=item_id, user=request.user)
#     cart_item.delete()
#     messages.success(request, "Item removed from cart!")
#     return redirect('shopping-cart')

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


def checkout_details(request):
    if not request.user.is_authenticated:
        return redirect('customer_login')

    cart_items = Cart.objects.filter(user=request.user).select_related('product')
    if not cart_items.exists():
        return redirect('shopping-cart')

    # --- Reuse cart context for consistency ---
    from shopingo.context_processors import cart_context
    cart_data = cart_context(request)

    subtotal = cart_data['cart_subtotal']
    shipping_amount = cart_data['cart_shipping']
    coupon_discount = cart_data['cart_coupon_discount']
    total = cart_data['cart_order_total']

    # --- Save shipping info if POST ---
    if request.method == "POST":
        request.session['shipping_info'] = {
            'country_id': request.POST.get('country_id'),
            'division_id': request.POST.get('division_id'),
            'district_id': request.POST.get('district_id'),
            'zip_code': request.POST.get('zip_code'),
        }

    shipping_info = request.session.get('shipping_info', {})

    # --- Division and District names ---
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




def order_tracking(request):
    return render(request, 'orders/order-tracking.html')


@login_required
def checkout_shipping(request):
    country_name = CountryName.objects.all()
    shipping_methods = ShippingCharge.objects.filter(active=True)
    from shopingo.context_processors import cart_context
    cart_data = cart_context(request)

    subtotal = cart_data['cart_subtotal']
    coupon_discount = cart_data['cart_coupon_discount']

    if request.method == "POST":
        selected_method_id = request.POST.get("shipping_method")
        if selected_method_id:
            shipping_method = ShippingCharge.objects.get(id=selected_method_id)
            total_with_shipping = subtotal + shipping_method.charge_amount - coupon_discount

            # Create the order
            order = Order.objects.create(
                user=request.user,
                shipping_method=shipping_method,
                subtotal=subtotal,
                discount=coupon_discount,
                shipping_charge=shipping_method.charge_amount,
                total_amount=total_with_shipping
            )

            # Save order id in session to use in payment page
            request.session['order_id'] = order.id
            messages.success(request, "Order created successfully!")
            
            # Redirect to payment page
            return redirect("checkout-payment")

    context = {
        'country_name': country_name,
        'shipping_methods': shipping_methods,
        'subtotal': subtotal,
        'coupon_discount': coupon_discount,
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

        # Order total update with coupon
        coupon_code = request.session.get('coupon_code')
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code__iexact=coupon_code, active=True)
                now = timezone.now()
                if coupon.valid_from <= now <= coupon.valid_to:
                    discount_amount = (order.subtotal * Decimal(coupon.discount_percent)) / 100
                    order.discount = discount_amount
            except:
                order.discount = Decimal('0.00')

        order.total_amount = order.subtotal + order.shipping_charge - order.discount
        order.save()

        # Save OrderItems
        cart_items = Cart.objects.filter(user=request.user)
        if not cart_items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect('checkout-payment')

        for item in cart_items:
            unit_price = item.product.price
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

        # Clear cart
        cart_items.delete()

        # Success → redirect to checkout-complete page
        messages.success(request, "Order completed successfully.")
        return redirect('checkout-complete', order_id=order.id)  # Pass order_id if needed

    # GET request → render checkout-payment page
    return render(request, 'checkout/checkout-payment.html', {'order': order})



@login_required
def checkout_review(request):
    order_id = request.session.get('order_id')
    if not order_id:
        messages.error(request, "No order found.")
        return redirect('shopping-cart')

    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.all()  # related_name="items" থেকে

    return render(request, 'checkout/checkout-review.html', {
        'order': order,
        'order_items': order_items
    })

@login_required
def checkout_complete(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'checkout/checkout-complete.html', {'order': order})




def about_page(request):
    return render(request, 'about.html')

def contact_page(request):
    return render(request, 'contact.html')




def produc_category_view(request, slug):
    view_type = request.GET.get('view', 'top')  # 'top', 'left', or 'list'
    category = get_object_or_404(Category, slug=slug)
    products = category.products.all()
    

    # Choose template dynamically
    if view_type == 'left':
        template = 'products/category/shop-grid-left-sidebar.html'
    elif view_type == 'list':
        template = 'products/category/shop-list-left-sidebar.html'
    else:
        template = 'products/category/shop-grid-filter-on-top.html'

    context = {
        'category': category,
        'products': products,
    }
    return render(request, template, context)



def produc_subCategory_view(request, slug):
    view_type = request.GET.get('view', 'top')  # 'top', 'left', or 'list'
    subCategory = get_object_or_404(SubCategory, slug=slug)
    products = subCategory.products.all()
    

    # Choose template dynamically
    if view_type == 'left':
        template = 'products/subCategory/shop-grid-left-sidebar.html'
    elif view_type == 'list':
        template = 'products/subCategory/shop-list-left-sidebar.html'
    else:
        template = 'products/subCategory/shop-grid-filter-on-top.html'

    context = {
        'subCategory': subCategory,
        'products': products,
    }
    return render(request, template, context)


def produc_tag_view(request, slug):
    view_type = request.GET.get('view', 'top')  # 'top', 'left', or 'list'
    tag = get_object_or_404(Tag, slug=slug)
    product_ids = ProductTag.objects.filter(tag=tag).values_list('product_id', flat=True)
    products = Product.objects.filter(id__in=product_ids)

    # Choose template dynamically
    if view_type == 'left':
        template = 'products/tag/shop-grid-left-sidebar.html'
    elif view_type == 'list':
        template = 'products/tag/shop-list-left-sidebar.html'
    else:
        template = 'products/tag/shop-grid-filter-on-top.html'

    context = {
        'tag': tag,
        'products': products,
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






