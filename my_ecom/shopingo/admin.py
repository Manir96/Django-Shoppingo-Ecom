from django.contrib import admin
from .models import *
from django.utils.html import format_html
from django.urls import reverse

# ===========================
# Category Admin
# ===========================
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}  # auto slug from name


# ===========================
# SubCategory Admin
# ===========================
@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "slug")
    search_fields = ("name", "category__name")
    list_filter = ("category",)
    prepopulated_fields = {"slug": ("name",)}


# ===========================
# Product Image Inline
# ===========================
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


# ===========================
# Product Admin
# ===========================
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "subcategory",
        "price",
        "orginal_price",
        "discount_price",
        "discount_percent_display",
        "stock",
        "created_at",
    )
    search_fields = ("title", "category__name", "subcategory__name", "seller__username")
    list_filter = ("category", "subcategory", "seller")
    inlines = [ProductImageInline]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at",)

    class Media:
        js = ("admin/js/product_price_calc.js",)  # ✅ include your JS file

    def discount_percent_display(self, obj):
        return f"{obj.discount_percent}%"
    discount_percent_display.short_description = "Discount %"

    def save_model(self, request, obj, form, change):
        obj.save()



# ===========================
# Variation Admin
# ===========================
@admin.register(Variation)
class VariationAdmin(admin.ModelAdmin):
    list_display = ("product", "color", "size", "brand", "price", "discount_price", 'price_range', "stock")
    search_fields = ("product__title", "brand__name")
    list_filter = ("color", "size", "brand")


# ===========================
# Color Admin
# ===========================
@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name",)


# ===========================
# Size Admin
# ===========================
@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


# ===========================
# Brand Admin
# ===========================
@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


# ===========================
# Tag Admin
# ===========================
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


# ===========================
# Product Tag Admin
# ===========================
@admin.register(ProductTag)
class ProductTagAdmin(admin.ModelAdmin):
    list_display = ("product", "tag")
    search_fields = ("product__title", "tag__name")


# ===========================
# Cart Admin (Read-only)
# ===========================
@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'quantity', 'color', 'size', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('user__username', 'product__title')
    
    # Prevent deletion
    def has_delete_permission(self, request, obj=None):
        return False

    # Prevent editing
    def has_change_permission(self, request, obj=None):
        return False

# ===========================
# Wishlist Admin (Read-only)
# ===========================
@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('user__username', 'product__title')
    
    # Prevent deletion
    def has_delete_permission(self, request, obj=None):
        return False

    # Prevent editing
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percent', 'valid_from', 'valid_to', 'active')
    list_filter = ('active', 'valid_from', 'valid_to')
    search_fields = ('code',)
    filter_horizontal = ('products',)


# ===========================
# Shipping Charge Admin
@admin.register(ShippingCharge)
class ShippingChargeAdmin(admin.ModelAdmin):
    list_display = (
        'Shipping_type_name',
        'country',
        'division',
        'min_order_amount',
        'charge_amount',
        'delivery_time',
        'estimated_days',
        'active',
    )
    list_filter = ('country', 'division', 'active')
    search_fields = ('Shipping_type_name', 'country__name', 'division__name')
    ordering = ('country', 'division', 'charge_amount')
    list_editable = ('charge_amount', 'active')

    fieldsets = (
        (None, {
            'fields': (
                'Shipping_type_name',
                'country',
                'division',
                'min_order_amount',
                'charge_amount',
                'delivery_time',
                'estimated_days',
                'active',
            )
        }),
    )
@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'country', 'division', 'district', 'created_at')
    search_fields = ('first_name', 'last_name', 'country', 'division', 'district')



@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'latest_shipping_address',
        'shipping_method',
        'subtotal',
        'discount',
        'shipping_charge',
        'total_amount',
        'created_at',   # payment_method বাদ দেওয়া হয়েছে
    )
    list_filter = ('created_at',)   # payment_method filter মুছে দেওয়া
    search_fields = ('user__username', 'id')

    def latest_shipping_address(self, obj):
        """Show only this user's latest ShippingAddress"""
        latest_address = (
            ShippingAddress.objects
            .filter(user=obj.user)
            .order_by('-created_at')
            .first()
        )
        if latest_address:
            url = reverse('admin:shopingo_shippingaddress_change', args=[latest_address.id])
            address_text = f"{latest_address.address1}"
            if latest_address.address2:
                address_text += f", {latest_address.address2}"
            if latest_address.district:
                address_text += f", {latest_address.district}"
            if latest_address.division:
                address_text += f", {latest_address.division}"
            if latest_address.country:
                address_text += f", {latest_address.country}"
            return format_html('<a href="{}">{}</a>', url, address_text)
        return "No address found"

    latest_shipping_address.short_description = "Latest Shipping Address"

    # Order এডিট/ক্রিয়েট করার সময় dropdown ফিল্টার করা
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "shipping_address":
            order_id = request.resolver_match.kwargs.get("object_id")
            if order_id:
                try:
                    order = Order.objects.get(pk=order_id)
                    kwargs["queryset"] = ShippingAddress.objects.filter(user=order.user)
                except Order.DoesNotExist:
                    pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        'order',
        'user',
        'product',
        'quantity',
        'size',
        'color',
        'price',
        'item_total',
        'order_total_amount',  # ✅ custom method
    )

    def order_total_amount(self, obj):
        """Show total_amount from related Order"""
        return obj.order.total_amount

    order_total_amount.short_description = "Order Total Amount"



@admin.register(CompletedOrder)
class CompletedOrderAdmin(admin.ModelAdmin):
    list_display = (
        "tracking_id",
        "order",
        "total_amount",
        "completed_at",
    )
    list_filter = ("completed_at",)
    search_fields = ("tracking_id", "order__id", "shipping_address__first_name", "shipping_address__phone")
    readonly_fields = ("tracking_id", "completed_at")

    # Optional: ManyToMany field editable in admin
    filter_horizontal = ("order_items",)


@admin.register(OrderStatus)
class OrderStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'get_status_display_name')
    list_filter = ('status',)
    search_fields = ('status',)

    def get_status_display_name(self, obj):
        return dict(obj.STATUS_CHOICES).get(obj.status, "Unknown")
    get_status_display_name.short_description = "Display Name"
