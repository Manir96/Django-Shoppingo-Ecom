"""Ensure checkout shipping methods and a valid demo coupon exist."""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from shopingo.models import Coupon, ShippingCharge


class Command(BaseCommand):
    help = "Seed Standard/Express shipping and a valid SAVE10 coupon."

    def handle(self, *args, **options):
        methods = [
            ("Standard Shipping", Decimal("50.00"), "3-5 business days", 5),
            ("Express Shipping", Decimal("100.00"), "1-2 business days", 2),
            ("Store Pickup", Decimal("0.00"), "Same day pickup", 0),
        ]
        for name, fee, time_label, days in methods:
            obj, created = ShippingCharge.objects.update_or_create(
                Shipping_type_name=name,
                defaults={
                    "charge_amount": fee,
                    "delivery_time": time_label,
                    "estimated_days": days,
                    "active": True,
                    "min_order_amount": Decimal("0.00"),
                },
            )
            self.stdout.write(
                self.style.SUCCESS(f"{'Created' if created else 'Updated'}: {obj.Shipping_type_name}")
            )

        now = timezone.now()
        coupon, created = Coupon.objects.update_or_create(
            code="SAVE10",
            defaults={
                "discount_percent": 10,
                "valid_from": now - timedelta(days=1),
                "valid_to": now + timedelta(days=365),
                "active": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if created else 'Updated'} coupon: {coupon.code} ({coupon.discount_percent}%)"
            )
        )
