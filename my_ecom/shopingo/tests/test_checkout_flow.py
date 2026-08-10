"""End-to-end checkout audit tests."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CountryName, Role
from shopingo.models import (
    Cart,
    Category,
    CompletedOrder,
    Coupon,
    Invoice,
    Order,
    Payment,
    Product,
    ShippingCharge,
    SubCategory,
)

User = get_user_model()


class CheckoutFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        role, _ = Role.objects.get_or_create(
            name="customer", defaults={"display_name": "Customer", "is_active": True}
        )
        cls.user = User.objects.create_user(
            email="checkout@demo.com",
            password="Password@123",
            role=role,
            first_name="Test",
            last_name="Buyer",
            username="checkout_user",
        )
        cls.country = CountryName.objects.create(nameName="Bangladesh")
        cls.cat = Category.objects.create(name="Electronics")
        cls.sub = SubCategory.objects.create(name="Smartphones", category=cls.cat)
        cls.product = Product.objects.create(
            title="Test Phone",
            slug="test-phone-checkout",
            price=Decimal("1200.00"),
            orginal_price=Decimal("1000.00"),
            discount_price=Decimal("200.00"),
            stock=20,
            category=cls.cat,
            subcategory=cls.sub,
            seller=cls.user,
            brand_name="TestBrand",
        )
        cls.ship_std = ShippingCharge.objects.create(
            Shipping_type_name="Standard Shipping",
            charge_amount=Decimal("50.00"),
            delivery_time="3-5 days",
            estimated_days=5,
            active=True,
        )
        cls.ship_exp = ShippingCharge.objects.create(
            Shipping_type_name="Express Shipping",
            charge_amount=Decimal("100.00"),
            delivery_time="1-2 days",
            estimated_days=2,
            active=True,
        )
        now = timezone.now()
        cls.coupon = Coupon.objects.create(
            code="SAVE10",
            discount_percent=10,
            valid_from=now - timedelta(days=1),
            valid_to=now + timedelta(days=30),
            active=True,
        )

    def setUp(self):
        self.client = Client()
        assert self.client.login(email="checkout@demo.com", password="Password@123")
        Cart.objects.filter(user=self.user).delete()
        Cart.objects.create(
            user=self.user,
            product=self.product,
            quantity=2,
            size="256GB",
            color="Phantom Black",
        )

    def _post_details(self, **overrides):
        data = {
            "first_name": "Test",
            "last_name": "Buyer",
            "email": "checkout@demo.com",
            "phone": "+8801712345678",
            "country_id": str(self.country.id),
            "division_id": "Dhaka",
            "district_id": "Gulshan",
            "zip_code": "1212",
            "address1": "House 1, Road 2",
            "address2": "House 1, Road 2",
        }
        data.update(overrides)
        return self.client.post(reverse("checkout-details"), data)

    def test_cart_shows_variant_and_proceed(self):
        r = self.client.get(reverse("shopping-cart"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Test Phone")
        self.assertContains(r, "256GB")
        self.assertContains(r, "Phantom Black")
        r2 = self.client.post(reverse("shopping-cart"))
        self.assertEqual(r2.status_code, 302)
        self.assertEqual(r2.url, reverse("checkout-details"))

    def test_empty_cart_blocks_checkout(self):
        Cart.objects.filter(user=self.user).delete()
        r = self.client.get(reverse("checkout-details"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("shopping-cart"))

    def test_details_validation_required(self):
        r = self._post_details(first_name="", email="bad", phone="12")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "required", status_code=200)

    def test_cannot_skip_to_shipping(self):
        r = self.client.get(reverse("checkout-shipping"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("checkout-details"))

    def test_cannot_skip_to_payment(self):
        r = self.client.get(reverse("checkout-payment"))
        self.assertEqual(r.status_code, 302)

    def test_cannot_skip_to_review(self):
        r = self.client.get(reverse("checkout-review"))
        self.assertEqual(r.status_code, 302)

    def test_full_cod_checkout(self):
        stock_before = self.product.stock
        self.assertEqual(self._post_details().status_code, 302)

        r = self.client.post(
            reverse("checkout-shipping"),
            {"shipping_method": str(self.ship_std.id)},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("checkout-payment"))
        order_id = self.client.session["order_id"]
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.shipping_charge, Decimal("50.00"))

        r = self.client.post(reverse("checkout-payment"), {"payment_method": "COD"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("checkout-review"))
        order.refresh_from_db()
        self.assertTrue(order.items.exists())
        self.assertEqual(order.items.first().size, "256GB")
        self.assertEqual(order.items.first().color, "Phantom Black")
        self.assertEqual(order.payment.method, Payment.METHOD_COD)

        r = self.client.get(reverse("checkout-review"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Cash on Delivery")
        self.assertContains(r, "256GB")

        r = self.client.post(reverse("checkout-complete", args=[order.id]))
        self.assertEqual(r.status_code, 200)
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PLACED)
        self.assertTrue(CompletedOrder.objects.filter(order=order).exists())
        self.assertTrue(Invoice.objects.filter(order=order).exists())
        self.assertEqual(self.product.stock, stock_before - 2)
        self.assertFalse(Cart.objects.filter(user=self.user).exists())
        self.assertNotIn("order_id", self.client.session)

    def test_card_validation_and_success(self):
        self._post_details()
        self.client.post(
            reverse("checkout-shipping"),
            {"shipping_method": str(self.ship_exp.id)},
        )
        # Decline card
        r = self.client.post(
            reverse("checkout-payment"),
            {
                "payment_method": "CARD",
                "card_owner": "Test Buyer",
                "card_number": "4000000000000002",
                "card_exp_mm": "12",
                "card_exp_yy": "30",
                "card_cvv": "123",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("checkout-payment"))

        r = self.client.post(
            reverse("checkout-payment"),
            {
                "payment_method": "CARD",
                "card_owner": "Test Buyer",
                "card_number": "4111111111111111",
                "card_exp_mm": "12",
                "card_exp_yy": "30",
                "card_cvv": "123",
            },
        )
        self.assertEqual(r.url, reverse("checkout-review"))
        order = Order.objects.get(id=self.client.session["order_id"])
        self.assertEqual(order.payment.method, "CARD")
        self.assertEqual(order.payment.status, Payment.STATUS_COMPLETED)

    def test_paypal_and_netbanking(self):
        self._post_details()
        self.client.post(
            reverse("checkout-shipping"),
            {"shipping_method": str(self.ship_std.id)},
        )
        r = self.client.post(
            reverse("checkout-payment"),
            {"payment_method": "PAYPAL", "paypal_account_type": "domestic"},
        )
        self.assertEqual(r.url, reverse("checkout-review"))

        # Reset payment via another method
        r = self.client.post(
            reverse("checkout-payment"),
            {"payment_method": "NETBANKING", "bank_name": "BRAC Bank"},
        )
        self.assertEqual(r.url, reverse("checkout-review"))
        order = Order.objects.get(id=self.client.session["order_id"])
        self.assertEqual(order.payment.method, "NETBANKING")
        self.assertIn("BRAC", order.payment.notes)

    def test_coupon_apply(self):
        r = self.client.post(reverse("apply_coupon"), {"coupon_code": "SAVE10"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.session.get("coupon_code"), "SAVE10")

        r = self.client.post(reverse("apply_coupon"), {"coupon_code": "FAKE"})
        self.assertEqual(r.status_code, 302)

    def test_duplicate_place_order_idempotent(self):
        self._post_details()
        self.client.post(
            reverse("checkout-shipping"),
            {"shipping_method": str(self.ship_std.id)},
        )
        self.client.post(reverse("checkout-payment"), {"payment_method": "COD"})
        order_id = self.client.session["order_id"]
        self.client.post(reverse("checkout-complete", args=[order_id]))
        # Session cleared — place again via direct URL should still show success
        r = self.client.post(reverse("checkout-complete", args=[order_id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(CompletedOrder.objects.filter(order_id=order_id).count(), 1)

    def test_quantity_update(self):
        item = Cart.objects.get(user=self.user)
        r = self.client.post(
            reverse("update_cart_quantity"),
            {"item_id": item.id, "quantity": 3},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["success"])
        item.refresh_from_db()
        self.assertEqual(item.quantity, 3)

    def test_session_preserves_details(self):
        self._post_details()
        info = self.client.session.get("shipping_info")
        self.assertEqual(info["phone"], "+8801712345678")
        r = self.client.get(reverse("checkout-details"))
        self.assertContains(r, "+8801712345678")
        self.assertContains(r, "House 1, Road 2")
