from django.db import models
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from ckeditor.fields import RichTextField
import re
from smart_selects.db_fields import ChainedForeignKey
from django.contrib.auth.models import User
from django.utils import timezone
from accounts.models import CountryName, Division, District
from django.conf import settings
from decimal import Decimal
import uuid
User = get_user_model()


# ===========================
# Category Models
# ===========================
class Category(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=80,
        blank=True,
        help_text="Boxicons class, e.g. bx-laptop, bx-closet",
    )
    banner = models.ImageField(upload_to='categories/banners/', blank=True, null=True)
    featured_image = models.ImageField(upload_to='categories/featured/', blank=True, null=True)
    promo_title = models.CharField(max_length=120, blank=True)
    promo_text = models.CharField(max_length=255, blank=True)
    menu_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    # SEO
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)
    og_image = models.ImageField(upload_to='categories/og/', blank=True, null=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['menu_order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if not self.meta_title:
            self.meta_title = f"Shop {self.name} Online | Shopingo"
        if not self.meta_description and self.description:
            self.meta_description = self.description[:160]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

# ===========================
# SubCategory Models
# ===========================
class SubCategory(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="subcategories")
    description = models.TextField(blank=True)
    featured_image = models.ImageField(upload_to='subcategories/', blank=True, null=True)
    menu_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    # SEO
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = "Sub Categories"
        ordering = ['menu_order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while SubCategory.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if not self.meta_title:
            self.meta_title = f"{self.name} | {self.category.name} | Shopingo"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category.name} → {self.name}"


def product_image_upload_to(instance, filename):
    folder = 'general'
    if instance.product_id and instance.product and instance.product.category_id:
        name = (instance.product.category.name or '').lower()
        if 'electronic' in name:
            folder = 'electronics'
        elif 'fashion' in name:
            folder = 'fashion'
        elif 'home' in name or 'kitchen' in name:
            folder = 'home'
        elif 'beauty' in name or 'personal' in name:
            folder = 'beauty'
        else:
            folder = slugify(instance.product.category.name) or 'general'
    return f'products/{folder}/{filename}'


def get_random_sku_suffix():
    return uuid.uuid4().hex[:6].upper()


# ===========================
# Product Models
# ===========================
class Product(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    sku = models.CharField(max_length=64, unique=True, blank=True, null=True)
    brand_name = models.CharField(max_length=100, blank=True)
    short_description = models.CharField(max_length=300, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = RichTextField(blank=True, null=True)
    description_details = RichTextField(blank=True, null=True)
    more_information = RichTextField(blank=True, null=True)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    orginal_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=4.50)
    review_count = models.PositiveIntegerField(default=0)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products")
    subcategory = ChainedForeignKey(SubCategory, chained_field="category", chained_model_field="category", on_delete=models.CASCADE, related_name="products", null=True, blank=True, show_all=False,auto_choose=True,sort=True,)
    is_featured = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    is_bestseller = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False)
    is_popular = models.BooleanField(default=False)
    is_recommended = models.BooleanField(default=False)
    is_flash_sale = models.BooleanField(default=False)
    is_digital = models.BooleanField(default=False)
    digital_file = models.FileField(upload_to="digital_products/", blank=True, null=True)
    download_limit = models.PositiveIntegerField(
        default=5, help_text="Max downloads per purchase (0 = unlimited)"
    )
    download_expiry_days = models.PositiveIntegerField(
        default=30, help_text="Days until download link expires"
    )
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name="products")
    created_at = models.DateTimeField(auto_now_add=True)
    # SEO
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)
    og_image = models.ImageField(upload_to='products/og/', blank=True, null=True)

    class Meta:
        verbose_name_plural = "Products"

    def save(self, *args, **kwargs):
        if not self.slug:
            #  Step 1: Clean title (remove extra words)
            words = re.findall(r'\w+', self.title.lower())[:5]  # first 5 words only
            base_slug = slugify("-".join(words))

            #  Step 2: Ensure unique slug
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            #  Step 3: Assign final slug
            self.slug = slug

        if not self.sku:
            base = slugify(self.title)[:20].upper().replace('-', '')
            self.sku = f"SKU-{base}-{get_random_sku_suffix()}"

        if not self.meta_title:
            self.meta_title = f"Buy {self.title} Online | Shopingo"
        if not self.meta_description and self.short_description:
            self.meta_description = self.short_description[:160]
        
        # ✅ Smart auto calculation
        if self.price and self.orginal_price:
            # Case 1: User entered orginal price — calculate discount amount
            self.discount_price = self.price - self.orginal_price

        elif self.price and self.discount_price:
            # Case 2: User entered discount amount — calculate orginal price
            self.orginal_price = self.price - self.discount_price

        else:
            # Case 3: Only price entered
            self.orginal_price = self.price
            self.discount_price = 0

        super().save(*args, **kwargs)

    # Optional: calculate % discount easily in frontend/admin
    @property
    def discount_percent(self):
        if self.price and self.orginal_price and self.price > 0:
            return round(((self.price - self.orginal_price) / self.price) * 100, 2)
        return 0

    @property
    def primary_image(self):
        img = self.images.filter(is_primary=True).first()
        return img or self.images.first()

    def __str__(self):
        return self.title


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images", null=True, blank=True)
    image = models.ImageField(upload_to=product_image_upload_to)
    is_primary = models.BooleanField(default=False)
    is_thumbnail = models.BooleanField(default=False)
    alt_text = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"Image of {self.product.title if self.product else 'N/A'}"


# ===========================
# Variations / Filters
# ===========================
class Color(models.Model):
    name = models.CharField(max_length=50, unique=True, null=True, blank=True)
    code = models.CharField(max_length=7, blank=True, null=True)  # Hex code (optional)

    def __str__(self):
        return self.name


class Size(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True, null=True, blank=True)
    brand_logo = models.ImageField(upload_to="brands/", blank=True, null=True)
    slug = models.SlugField(max_length=150, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Variation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variations")
    color = models.ForeignKey(Color, on_delete=models.CASCADE)
    size = models.ForeignKey(Size, on_delete=models.CASCADE)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, null=False, default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2)
    price_range = models.CharField(max_length=100, blank=True, null=True)
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("product", "color", "size", "brand")
        verbose_name_plural = "Product Variations"

    def __str__(self):
        return f"{self.product.title} - {self.color.name} - {self.size.name}"


# ===========================
# Tags
# ===========================
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, null=True, blank=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductTag(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="tags", null=True, blank=True)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ("product", "tag")
        verbose_name_plural = "Product Tags"

    def __str__(self):
        return f"{self.product.title} - {self.tag.name}"


class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_reviews",
    )
    name = models.CharField(max_length=120)
    email = models.EmailField()
    rating = models.PositiveSmallIntegerField(default=5)
    comment = models.TextField()
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Product Reviews"

    def __str__(self):
        return f"{self.name} — {self.product.title} ({self.rating}★)"

    def save(self, *args, **kwargs):
        self.rating = max(1, min(5, int(self.rating or 5)))
        super().save(*args, **kwargs)
        self._refresh_product_rating()

    def delete(self, *args, **kwargs):
        product = self.product
        super().delete(*args, **kwargs)
        # Recalc after delete
        approved = product.reviews.filter(is_approved=True)
        count = approved.count()
        if count:
            avg = approved.aggregate(avg=models.Avg("rating"))["avg"] or 0
            product.rating = round(Decimal(str(avg)), 2)
            product.review_count = count
        else:
            product.review_count = 0
        product.save(update_fields=["rating", "review_count"])

    def _refresh_product_rating(self):
        approved = self.product.reviews.filter(is_approved=True)
        count = approved.count()
        if count:
            avg = approved.aggregate(avg=models.Avg("rating"))["avg"] or 0
            self.product.rating = round(Decimal(str(avg)), 2)
            self.product.review_count = count
            self.product.save(update_fields=["rating", "review_count"])


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wishlist_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.title} in {self.user.username}'s wishlist"


    

# ===========================
#Coupon Models
# ===========================

class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    discount_percent = models.PositiveIntegerField(blank=True, null=True)
    valid_from = models.DateTimeField(blank=True, null=True)
    valid_to = models.DateTimeField(blank=True, null=True)
    active = models.BooleanField(default=True, blank=True, null=True)
    products = models.ManyToManyField(Product, blank=True, )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"

    def __str__(self):
        return f"{self.code} ({self.discount_percent}% off)"

    def is_valid(self):
        """Check if the coupon is currently valid and active."""
        if not self.active or not self.discount_percent:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_to and now > self.valid_to:
            return False
        return True


# ===========================
# Cart Models
# ===========================

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cart_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    color = models.CharField(max_length=50, blank=True, null=True)
    size = models.CharField(max_length=50, blank=True, null=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.title} ({self.color or '-'} / {self.size or '-'}) in {self.user.username}'s cart"


class OrderStatus(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Order Confirmed'),
        ('processing', 'Processing'),
        ('picked', 'Picked by courier'),
        ('onway', 'On the way'),
        ('ready', 'Ready for pickup'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='confirmed')

    def __str__(self):
        return self.get_status_display()


class ShippingCharge(models.Model):
    Shipping_type_name = models.CharField(max_length=100, help_text="Shipping type or name (e.g., Standard, Express)")
    country = models.ForeignKey(CountryName, on_delete=models.CASCADE, blank=True, null=True)
    division = models.ForeignKey(Division, on_delete=models.CASCADE, blank=True, null=True)
    district = models.ForeignKey(District, on_delete=models.CASCADE, blank=True, null=True)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Minimum order amount for this rate")
    charge_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Shipping cost")
    delivery_time = models.CharField(max_length=50, blank=True, null=True)
    estimated_days = models.PositiveIntegerField(default=3, help_text="Estimated delivery time in days")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['country', 'division', 'charge_amount']
        verbose_name = "Shipping Charge"
        verbose_name_plural = "Shipping Charges"

    def __str__(self):
        return f"{self.Shipping_type_name} - {self.charge_amount}৳ ({self.country})"
    



class ShippingAddress(models.Model):
    TYPE_SHIPPING = "shipping"
    TYPE_BILLING = "billing"
    TYPE_CHOICES = (
        (TYPE_SHIPPING, "Shipping"),
        (TYPE_BILLING, "Billing"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    label = models.CharField(max_length=80, blank=True, default="Home")
    address_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SHIPPING)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    country = models.CharField(max_length=100, null=True, blank=True)
    division = models.CharField(max_length=100, null=True, blank=True)
    district = models.CharField(max_length=100, null=True, blank=True)
    zip_code = models.CharField(max_length=20, null=True, blank=True)
    address1 = models.TextField()
    address2 = models.TextField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-updated_at"]
        verbose_name_plural = "Shipping Addresses"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return f"{self.full_name} ({self.get_address_type_display()})"


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    cart = models.ForeignKey(Cart, on_delete=models.SET_NULL, null=True, blank=True)
    shipping_method = models.ForeignKey(ShippingCharge, on_delete=models.SET_NULL, null=True)
    shipping_address = models.ForeignKey(
        ShippingAddress,
        on_delete=models.SET_NULL,
        null=True,
        related_name="orders"
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=(('draft', 'Draft'), ('placed', 'Placed')),
        default='draft',
    )
    order_status = models.ForeignKey(
        OrderStatus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    placed_at = models.DateTimeField(null=True, blank=True)

    STATUS_DRAFT = 'draft'
    STATUS_PLACED = 'placed'

    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"

    @property
    def is_placed(self):
        return self.status == self.STATUS_PLACED or hasattr(self, 'completion')



class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="order_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    size = models.CharField(max_length=50, blank=True, null=True)
    color = models.CharField(max_length=50, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Unit price
    item_total = models.DecimalField(max_digits=10, decimal_places=2)  # ✅ Total price
    payment_method = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.title} in Order #{self.order.id}"




class Payment(models.Model):
    METHOD_COD = 'COD'
    METHOD_CHOICES = (
        (METHOD_COD, 'Cash on Delivery'),
        ('CARD', 'Credit / Debit Card'),
        ('PAYPAL', 'PayPal'),
        ('NETBANKING', 'Net Banking'),
    )
    STATUS_PENDING = 'pending'
    STATUS_AUTHORIZED = 'authorized'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_AUTHORIZED, 'Authorized'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    )

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    method = models.CharField(max_length=50, choices=METHOD_CHOICES, default=METHOD_COD)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=64, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payment #{self.id} for Order #{self.order_id} ({self.method}/{self.status})"


class CompletedOrder(models.Model):
    tracking_id = models.CharField(max_length=20, unique=True, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.SET_NULL, null=True, related_name="completed_orders")
    shipping_address = models.ForeignKey(ShippingAddress, on_delete=models.SET_NULL, null=True, related_name="completed_orders")
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="completion")
    order_items = models.ManyToManyField(OrderItem, related_name="completed_orders")

    # NEW — all customer info saved as snapshot
    customer_info = models.JSONField(null=True, blank=True)

    # NEW — all product info saved as snapshot
    product_info = models.JSONField(null=True, blank=True)

    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tracking_id} — Order #{self.order.id}"


class Invoice(models.Model):
    invoice_number = models.CharField(max_length=32, unique=True, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='invoice')
    completed_order = models.OneToOneField(
        CompletedOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice',
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    billing_snapshot = models.JSONField(null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return self.invoice_number


class SavedPaymentMethod(models.Model):
    """Masked/tokenized payment methods — never store full card PAN."""
    TYPE_CARD = "card"
    TYPE_PAYPAL = "paypal"
    TYPE_BANK = "bank"
    TYPE_CHOICES = (
        (TYPE_CARD, "Credit / Debit Card"),
        (TYPE_PAYPAL, "PayPal"),
        (TYPE_BANK, "Bank Account"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_payment_methods"
    )
    method_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    label = models.CharField(max_length=80, blank=True)
    # Card
    card_brand = models.CharField(max_length=40, blank=True)
    last4 = models.CharField(max_length=4, blank=True)
    exp_month = models.PositiveSmallIntegerField(null=True, blank=True)
    exp_year = models.PositiveSmallIntegerField(null=True, blank=True)
    # PayPal
    paypal_email = models.EmailField(blank=True)
    # Bank
    bank_name = models.CharField(max_length=100, blank=True)
    account_last4 = models.CharField(max_length=4, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-updated_at"]

    def __str__(self):
        return f"{self.get_method_type_display()} ({self.display_masked})"

    @property
    def display_masked(self):
        if self.method_type == self.TYPE_CARD and self.last4:
            brand = self.card_brand or "Card"
            return f"{brand} **** **** **** {self.last4}"
        if self.method_type == self.TYPE_PAYPAL:
            email = self.paypal_email or ""
            if "@" in email:
                name, domain = email.split("@", 1)
                masked = (name[:2] + "***") if len(name) > 2 else "***"
                return f"PayPal {masked}@{domain}"
            return "PayPal"
        if self.method_type == self.TYPE_BANK:
            return f"{self.bank_name or 'Bank'} ****{self.account_last4}"
        return self.get_method_type_display()


class DigitalDownload(models.Model):
    """Per-purchase download entitlement for digital products."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="digital_downloads"
    )
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="digital_downloads")
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name="digital_downloads"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="digital_downloads")
    download_count = models.PositiveIntegerField(default=0)
    download_limit = models.PositiveIntegerField(default=5)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("order_item", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Download {self.product_id} for order #{self.order_id}"

    @property
    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at)

    @property
    def remaining(self):
        if self.download_limit == 0:
            return None  # unlimited
        return max(0, self.download_limit - self.download_count)

    @property
    def can_download(self):
        if self.is_expired:
            return False
        if self.download_limit == 0:
            return bool(self.product.digital_file)
        return self.download_count < self.download_limit and bool(self.product.digital_file)


class RecentlyViewed(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recently_viewed"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="recent_views")
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "product")
        ordering = ["-viewed_at"]

    def __str__(self):
        return f"{self.user_id} viewed {self.product_id}"


class AccountNotification(models.Model):
    TYPE_ORDER = "order"
    TYPE_SHIPPING = "shipping"
    TYPE_PROMO = "promo"
    TYPE_WISHLIST = "wishlist"
    TYPE_SYSTEM = "system"
    TYPE_CHOICES = (
        (TYPE_ORDER, "Order"),
        (TYPE_SHIPPING, "Shipping"),
        (TYPE_PROMO, "Promotion"),
        (TYPE_WISHLIST, "Wishlist"),
        (TYPE_SYSTEM, "System"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account_notifications"
    )
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=255, blank=True)
    ntype = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SYSTEM)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class SupportTicket(models.Model):
    STATUS_OPEN = "open"
    STATUS_PENDING = "pending"
    STATUS_RESOLVED = "resolved"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = (
        (STATUS_OPEN, "Open"),
        (STATUS_PENDING, "Pending"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_CLOSED, "Closed"),
    )
    CAT_ORDER = "order"
    CAT_PAYMENT = "payment"
    CAT_SHIPPING = "shipping"
    CAT_ACCOUNT = "account"
    CAT_OTHER = "other"
    CATEGORY_CHOICES = (
        (CAT_ORDER, "Order issue"),
        (CAT_PAYMENT, "Payment / refund"),
        (CAT_SHIPPING, "Shipping / delivery"),
        (CAT_ACCOUNT, "Account / login"),
        (CAT_OTHER, "Other"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="support_tickets"
    )
    subject = models.CharField(max_length=200)
    message = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CAT_OTHER)
    order = models.ForeignKey(
        "Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    admin_reply = models.TextField(blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.id} {self.subject}"

    @property
    def is_open(self):
        return self.status in (self.STATUS_OPEN, self.STATUS_PENDING)


class SupportTicketReply(models.Model):
    """Conversation thread on a support ticket (customer or staff)."""

    ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="replies"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_replies",
    )
    is_staff = models.BooleanField(default=False)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Reply on #{self.ticket_id}"


class WhyChooseUs(models.Model):
    title = models.CharField(max_length=150)
    subtitle = models.CharField(max_length=255, blank=True, null=True)  # iccha hole use korba
    description = models.TextField()
    
    # icon image (admin theke upload korbe)
    icon = models.ImageField(upload_to="why_choose_us/", blank=True, null=True)

    # jodi static folder er png use korte chao:
    icon_file = models.CharField(
        max_length=100,
        blank=True,
        help_text="Example: delivery.png, money-bag.png, support.png"
    )

    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.title

class PersonalInfo(models.Model):
    phone_number = models.CharField(max_length=20, blank=True)
    address_line = models.TextField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    working_day_start = models.TimeField(null=True, blank=True)
    working_day_end = models.TimeField(null=True, blank=True)
    working_time_start = models.TimeField(null=True, blank=True)
    working_time_end = models.TimeField(null=True, blank=True)
    our_story = RichTextField(blank=True, null=True)

    def __str__(self):
        return f"Personal Info ({self.email})"

