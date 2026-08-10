from django.contrib import admin
from .models import *
from django.utils.html import format_html
from django.urls import reverse

# ===========================
# Category Admin
# ===========================
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "menu_order", "is_active", "icon")
    search_fields = ("name", "meta_title", "meta_keywords")
    list_filter = ("is_active",)
    list_editable = ("menu_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {"fields": ("name", "slug", "description", "icon", "menu_order", "is_active")}),
        ("Images & Promo", {"fields": ("featured_image", "banner", "promo_title", "promo_text", "og_image")}),
        ("SEO", {"fields": ("meta_title", "meta_description", "meta_keywords")}),
    )


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "slug", "menu_order", "is_active")
    search_fields = ("name", "category__name", "meta_title")
    list_filter = ("category", "is_active")
    list_editable = ("menu_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {"fields": ("category", "name", "slug", "description", "menu_order", "is_active")}),
        ("Image", {"fields": ("featured_image",)}),
        ("SEO", {"fields": ("meta_title", "meta_description", "meta_keywords")}),
    )


# ===========================
# Product Image Inline
# ===========================
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "is_primary", "is_thumbnail", "alt_text")


# ===========================
# Product Admin
# ===========================
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "sku",
        "brand_name",
        "category",
        "subcategory",
        "price",
        "orginal_price",
        "stock",
        "rating",
        "is_featured",
        "is_flash_sale",
        "created_at",
    )
    search_fields = ("title", "sku", "brand_name", "category__name", "subcategory__name", "seller__username")
    list_filter = (
        "category",
        "subcategory",
        "seller",
        "is_featured",
        "is_new_arrival",
        "is_bestseller",
        "is_trending",
        "is_popular",
        "is_recommended",
        "is_flash_sale",
    )
    list_editable = ("is_featured", "is_flash_sale", "stock")
    inlines = [ProductImageInline]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at",)
    fieldsets = (
        (None, {
            "fields": (
                "title", "slug", "sku", "brand_name", "seller",
                "category", "subcategory", "short_description",
                "description", "description_details", "more_information",
            )
        }),
        ("Pricing & Stock", {"fields": ("price", "orginal_price", "discount_price", "stock", "rating", "review_count")}),
        ("Home Sections", {
            "fields": (
                "is_featured", "is_new_arrival", "is_bestseller",
                "is_trending", "is_popular", "is_recommended", "is_flash_sale",
            )
        }),
        ("SEO", {"fields": ("meta_title", "meta_description", "meta_keywords", "og_image")}),
        ("Meta", {"fields": ("created_at",)}),
    )

    class Media:
        js = ("admin/js/product_price_calc.js",)

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


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "rating", "is_approved", "created_at")
    list_filter = ("rating", "is_approved", "created_at")
    search_fields = ("name", "email", "comment", "product__title")
    list_editable = ("is_approved",)


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
        'status',
        'latest_shipping_address',
        'shipping_method',
        'subtotal',
        'discount',
        'shipping_charge',
        'total_amount',
        'created_at',
        'placed_at',
    )
    list_filter = ('status', 'created_at', 'placed_at')
    search_fields = ('user__username', 'user__email', 'id')

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


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'method', 'status', 'amount', 'transaction_id', 'created_at', 'paid_at')
    list_filter = ('method', 'status', 'created_at')
    search_fields = ('transaction_id', 'order__id', 'order__user__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'order', 'total_amount', 'issued_at')
    search_fields = ('invoice_number', 'order__id', 'order__user__email')
    readonly_fields = ('invoice_number', 'issued_at')
    list_filter = ('issued_at',)


@admin.register(WhyChooseUs)
class WhyChooseUsAdmin(admin.ModelAdmin):
    list_display = ("title", "order", "is_active")
    list_editable = ("order", "is_active")


@admin.register(PersonalInfo)
class PersonalInfoAdmin(admin.ModelAdmin):
    list_display = ("email", "phone_number", "working_day_start", "working_day_end")
    list_editable = ("phone_number",)


@admin.register(SavedPaymentMethod)
class SavedPaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "method_type", "display_masked", "is_default", "created_at")
    list_filter = ("method_type", "is_default")
    search_fields = ("user__email", "last4", "paypal_email", "bank_name")


@admin.register(DigitalDownload)
class DigitalDownloadAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "product", "order", "download_count", "download_limit", "expires_at")
    search_fields = ("user__email", "product__title", "order__id")


@admin.register(RecentlyViewed)
class RecentlyViewedAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "viewed_at")
    search_fields = ("user__email", "product__title")


@admin.register(AccountNotification)
class AccountNotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "ntype", "is_read", "created_at")
    list_filter = ("is_read", "ntype")
    search_fields = ("user__email", "title")


class SupportTicketReplyInline(admin.TabularInline):
    model = SupportTicketReply
    extra = 1
    fields = ("body", "is_staff", "author", "created_at")
    readonly_fields = ("created_at",)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "subject", "category", "status", "order", "created_at")
    list_filter = ("status", "category")
    search_fields = ("user__email", "subject", "message", "admin_reply")
    readonly_fields = ("created_at", "updated_at", "replied_at")
    inlines = [SupportTicketReplyInline]
    actions = ("mark_pending", "mark_resolved", "mark_closed")

    def save_model(self, request, obj, form, change):
        from django.utils import timezone

        if obj.admin_reply and not obj.replied_at:
            obj.replied_at = timezone.now()
            if obj.status == SupportTicket.STATUS_OPEN:
                obj.status = SupportTicket.STATUS_PENDING
        super().save_model(request, obj, form, change)
        # Mirror admin_reply into thread once when set from admin form
        if obj.admin_reply and not obj.replies.filter(is_staff=True, body=obj.admin_reply).exists():
            SupportTicketReply.objects.create(
                ticket=obj,
                author=request.user,
                is_staff=True,
                body=obj.admin_reply,
            )

    @admin.action(description="Mark as pending")
    def mark_pending(self, request, queryset):
        queryset.update(status=SupportTicket.STATUS_PENDING)

    @admin.action(description="Mark as resolved")
    def mark_resolved(self, request, queryset):
        queryset.update(status=SupportTicket.STATUS_RESOLVED)

    @admin.action(description="Mark as closed")
    def mark_closed(self, request, queryset):
        queryset.update(status=SupportTicket.STATUS_CLOSED)

