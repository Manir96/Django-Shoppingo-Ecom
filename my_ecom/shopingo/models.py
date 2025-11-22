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
import uuid
from django.contrib.postgres.fields import JSONField  

User = get_user_model()


# ===========================
# Category Models
# ===========================
class Category(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)

    class Meta:
        verbose_name_plural = "Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
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

    class Meta:
        verbose_name_plural = "Sub Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while SubCategory.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category.name} → {self.name}"


# ===========================
# Product Models
# ===========================
class Product(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = RichTextField(blank=True, null=True)
    description_details = RichTextField(blank=True, null=True)
    more_information = RichTextField(blank=True, null=True)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    orginal_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products")
    subcategory = ChainedForeignKey(SubCategory, chained_field="category", chained_model_field="category", on_delete=models.CASCADE, related_name="products", null=True, blank=True, show_all=False,auto_choose=True,sort=True,)
    is_featured = models.BooleanField(default=False)
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name="products")
    created_at = models.DateTimeField(auto_now_add=True)

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

    def __str__(self):
        return self.title


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images", null=True, blank=True)
    image = models.ImageField(upload_to="products/")

    def __str__(self):
        return f"Image of {self.product.title}"


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
        """Check if the coupon is currently valid and active"""
        now = timezone.now()
        return self.active and self.valid_from <= now <= self.valid_to


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
        return f"{self.product.title} ({self.color}, {self.size})"
    
    def __str__(self):
        return f"{self.product.title} in {self.user.username}'s cart"


class OrderStatus(models.Model):
    STATUS_CHOICES = (
        ('confirmed', 'Order Confirmed'),
        ('picked', 'Picked by courier'),
        ('onway', 'On the way'),
        ('ready', 'Ready for pickup'),
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='confirmed')


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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
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
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


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
    order_status = models.ForeignKey(
        OrderStatus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"



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






