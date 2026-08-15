"""My Account module audit tests."""
from datetime import timedelta
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role
from django.contrib.auth import get_user_model
from shopingo.models import (
    AccountNotification,
    Cart,
    Category,
    CompletedOrder,
    DigitalDownload,
    Invoice,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    Product,
    RecentlyViewed,
    SavedPaymentMethod,
    ShippingAddress,
    ShippingCharge,
    SubCategory,
    Wishlist,
)

User = get_user_model()


class AccountModuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        role, _ = Role.objects.get_or_create(
            name="customer", defaults={"display_name": "Customer", "is_active": True}
        )
        cls.user = User.objects.create_user(
            email="acct@demo.com",
            password="Password@123",
            role=role,
            first_name="Amina",
            last_name="Rahman",
            username="amina",
        )
        cls.other = User.objects.create_user(
            email="other@demo.com",
            password="Password@123",
            role=role,
            first_name="Other",
            username="otheruser",
        )
        cls.cat = Category.objects.create(name="Books")
        cls.sub = SubCategory.objects.create(name="Ebooks", category=cls.cat)
        cls.product = Product.objects.create(
            title="Demo Ebook",
            slug="demo-ebook",
            price=Decimal("50"),
            orginal_price=Decimal("40"),
            stock=10,
            category=cls.cat,
            subcategory=cls.sub,
            seller=cls.user,
            is_digital=True,
            download_limit=3,
            download_expiry_days=30,
        )
        cls.product.digital_file.save(
            "ebook.txt",
            SimpleUploadedFile("ebook.txt", b"hello digital"),
            save=True,
        )
        cls.ship = ShippingCharge.objects.create(
            Shipping_type_name="Std", charge_amount=Decimal("10"), active=True
        )
        cls.status = OrderStatus.objects.create(status="confirmed")
        addr = ShippingAddress.objects.create(
            user=cls.user,
            first_name="Amina",
            last_name="Rahman",
            email="acct@demo.com",
            phone="+8801711111111",
            country="Bangladesh",
            division="Dhaka",
            district="Gulshan",
            zip_code="1212",
            address1="Road 1",
            is_default=True,
            address_type="shipping",
        )
        order = Order.objects.create(
            user=cls.user,
            shipping_method=cls.ship,
            shipping_address=addr,
            subtotal=Decimal("40"),
            discount=Decimal("0"),
            shipping_charge=Decimal("10"),
            total_amount=Decimal("50"),
            status=Order.STATUS_PLACED,
            order_status=cls.status,
        )
        item = OrderItem.objects.create(
            order=order,
            user=cls.user,
            product=cls.product,
            quantity=1,
            price=Decimal("40"),
            item_total=Decimal("40"),
            size="PDF",
            color="N/A",
        )
        Payment.objects.create(
            order=order, method="COD", status="authorized", amount=Decimal("50")
        )
        Invoice.objects.create(
            invoice_number="INV-TEST-001",
            order=order,
            subtotal=order.subtotal,
            discount=0,
            shipping_charge=order.shipping_charge,
            total_amount=order.total_amount,
        )
        cls.completed = CompletedOrder.objects.create(
            tracking_id="TRACKTEST01",
            shipping_address=addr,
            order=order,
            total_amount=order.total_amount,
        )
        cls.completed.order_items.add(item)
        DigitalDownload.objects.create(
            user=cls.user,
            order=order,
            order_item=item,
            product=cls.product,
            download_limit=3,
            expires_at=timezone.now() + timedelta(days=30),
        )
        Wishlist.objects.create(user=cls.user, product=cls.product)
        Cart.objects.create(user=cls.user, product=cls.product, quantity=2)
        AccountNotification.objects.create(
            user=cls.user, title="Welcome", message="Hello"
        )
        RecentlyViewed.objects.create(user=cls.user, product=cls.product)

    def setUp(self):
        self.client = Client()
        assert self.client.login(email="acct@demo.com", password="Password@123")

    def test_dashboard_requires_login(self):
        c = Client()
        r = c.get(reverse("account-dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r.url)

    def test_dashboard_dynamic(self):
        r = self.client.get(reverse("account-dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Amina")
        self.assertContains(r, "Welcome back")
        self.assertContains(r, "Recent orders")
        self.assertContains(r, f"#{self.completed.order.id}")

    def test_orders_list_and_idor(self):
        r = self.client.get(reverse("account-orders"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Demo Ebook")
        # Other user cannot see
        self.client.logout()
        self.client.login(email="other@demo.com", password="Password@123")
        r = self.client.get(reverse("account-order-detail", args=[self.completed.id]))
        self.assertEqual(r.status_code, 404)

    def test_cancel_and_reorder(self):
        r = self.client.post(reverse("account-cancel-order", args=[self.completed.id]))
        self.assertEqual(r.status_code, 302)
        self.completed.order.refresh_from_db()
        self.assertEqual(self.completed.order.order_status.status, "cancelled")

        r = self.client.post(reverse("account-reorder", args=[self.completed.id]))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Cart.objects.filter(user=self.user, product=self.product).exists())

    def test_downloads(self):
        r = self.client.get(reverse("account-downloads"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Demo Ebook")
        r = self.client.get(reverse("account-download-file", args=[
            DigitalDownload.objects.get(user=self.user).id
        ]))
        self.assertEqual(r.status_code, 200)

    def test_address_crud(self):
        r = self.client.post(
            reverse("account-addresses"),
            {
                "action": "save",
                "label": "Office",
                "address_type": "shipping",
                "first_name": "Amina",
                "last_name": "Rahman",
                "email": "acct@demo.com",
                "phone": "+8801722222222",
                "country": "Bangladesh",
                "division": "Dhaka",
                "district": "Banani",
                "zip_code": "1213",
                "address1": "Office Rd",
                "is_default": "on",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            ShippingAddress.objects.filter(user=self.user, district="Banani").exists()
        )

    def test_payment_method_masked(self):
        r = self.client.post(
            reverse("account-payment-methods"),
            {
                "action": "save",
                "method_type": "card",
                "card_brand": "Visa",
                "card_number": "4111111111114567",
                "exp_month": "12",
                "exp_year": "30",
                "is_default": "on",
            },
        )
        self.assertEqual(r.status_code, 302)
        pm = SavedPaymentMethod.objects.get(user=self.user)
        self.assertEqual(pm.last4, "4567")
        self.assertIn("4567", pm.display_masked)
        self.assertNotIn("4111111111114567", pm.display_masked)
        page = self.client.get(reverse("account-payment-methods"))
        self.assertContains(page, "**** **** **** 4567")
        self.assertNotContains(page, "4111111111114567")

    def test_account_details_update(self):
        r = self.client.post(
            reverse("account-user-details"),
            {
                "first_name": "Amina",
                "last_name": "Updated",
                "username": "amina2",
                "email": "acct@demo.com",
                "phone": "+8801733333333",
                "gender": "female",
                "date_of_birth": "1995-05-05",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, "Updated")
        self.assertEqual(self.user.username, "amina2")

    def test_logout(self):
        r = self.client.get(reverse("user_logout"))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(reverse("account-dashboard"))
        self.assertEqual(r.status_code, 302)
