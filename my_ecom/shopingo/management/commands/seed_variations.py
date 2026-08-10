"""Create Color/Size options and Variation rows for catalog products."""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from shopingo.models import Brand, Color, Product, Size, Variation

# Subcategory → (sizes, colors[(name, hex)])
VARIATION_PRESETS: dict[str, tuple[list[str], list[tuple[str, str]]]] = {
    "Smartphones": (
        ["128GB", "256GB", "512GB"],
        [
            ("Phantom Black", "#1A1A1A"),
            ("Storm White", "#F2F2F2"),
            ("Aura Red", "#C41E3A"),
            ("Electric Blue", "#1565C0"),
        ],
    ),
    "Laptops": (
        ["8GB/256GB", "16GB/512GB", "32GB/1TB"],
        [
            ("Space Gray", "#6E6E73"),
            ("Silver", "#C0C0C0"),
            ("Midnight", "#1C1C1E"),
        ],
    ),
    "Headphones": (
        ["Standard", "Pro"],
        [
            ("Matte Black", "#111111"),
            ("Pearl White", "#FAFAFA"),
            ("Navy", "#001F3F"),
        ],
    ),
    "Smart Watches": (
        ["40mm", "44mm", "46mm"],
        [
            ("Black", "#000000"),
            ("Silver", "#C0C0C0"),
            ("Rose Gold", "#B76E79"),
        ],
    ),
    "Cameras": (
        ["Body Only", "Kit Lens"],
        [
            ("Black", "#1A1A1A"),
            ("Silver", "#B8B8B8"),
        ],
    ),
    "Men's Clothing": (
        ["S", "M", "L", "XL", "XXL"],
        [
            ("Navy", "#001F3F"),
            ("Black", "#111111"),
            ("White", "#FFFFFF"),
            ("Olive", "#556B2F"),
        ],
    ),
    "Women's Clothing": (
        ["XS", "S", "M", "L", "XL"],
        [
            ("Black", "#111111"),
            ("White", "#FFFFFF"),
            ("Blush", "#DE5D83"),
            ("Sky Blue", "#87CEEB"),
        ],
    ),
    "Shoes": (
        ["40", "41", "42", "43", "44"],
        [
            ("Black", "#111111"),
            ("White", "#FFFFFF"),
            ("Brown", "#8B4513"),
        ],
    ),
    "Bags": (
        ["One Size",],
        [
            ("Black", "#111111"),
            ("Tan", "#D2B48C"),
            ("Navy", "#001F3F"),
        ],
    ),
    "Watches": (
        ["38mm", "42mm", "44mm"],
        [
            ("Silver", "#C0C0C0"),
            ("Gold", "#D4AF37"),
            ("Black", "#111111"),
        ],
    ),
    "Furniture": (
        ["Small", "Medium", "Large"],
        [
            ("Walnut", "#5C4033"),
            ("Oak", "#C4A484"),
            ("White", "#F5F5F5"),
        ],
    ),
    "Kitchen": (
        ["Standard", "Large"],
        [
            ("Stainless", "#B0B0B0"),
            ("Black", "#1A1A1A"),
            ("White", "#FFFFFF"),
        ],
    ),
    "Home Decor": (
        ["Small", "Medium", "Large"],
        [
            ("Ivory", "#FFFFF0"),
            ("Gray", "#808080"),
            ("Terracotta", "#E2725B"),
        ],
    ),
    "Lighting": (
        ["Warm White", "Cool White"],
        [
            ("Black", "#111111"),
            ("Brass", "#B5A642"),
            ("White", "#FFFFFF"),
        ],
    ),
    "Storage": (
        ["Small", "Medium", "Large"],
        [
            ("White", "#FFFFFF"),
            ("Gray", "#808080"),
            ("Natural", "#E8DCC4"),
        ],
    ),
    "Skincare": (
        ["30ml", "50ml", "100ml"],
        [
            ("Clear", "#E8F4F8"),
            ("White", "#FFFFFF"),
            ("Rose", "#FFC0CB"),
        ],
    ),
    "Hair Care": (
        ["250ml", "500ml"],
        [
            ("Black", "#1A1A1A"),
            ("Gold", "#D4AF37"),
            ("White", "#FFFFFF"),
        ],
    ),
    "Perfume": (
        ["30ml", "50ml", "100ml"],
        [
            ("Gold", "#D4AF37"),
            ("Silver", "#C0C0C0"),
            ("Black", "#111111"),
        ],
    ),
    "Makeup": (
        ["Fair", "Medium", "Deep"],
        [
            ("Nude", "#E3BC9A"),
            ("Rose", "#FF007F"),
            ("Berry", "#8A2BE2"),
        ],
    ),
    "Men Grooming": (
        ["50ml", "100ml", "150ml"],
        [
            ("Black", "#111111"),
            ("Blue", "#1E90FF"),
            ("Silver", "#C0C0C0"),
        ],
    ),
}

DEFAULT_PRESET = (
    ["S", "M", "L", "XL"],
    [
        ("Black", "#111111"),
        ("White", "#FFFFFF"),
        ("Blue", "#1565C0"),
        ("Red", "#C41E3A"),
    ],
)


class Command(BaseCommand):
    help = "Seed size/color variations for all active catalog products."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing variations before seeding.",
        )
        parser.add_argument(
            "--product",
            type=str,
            default="",
            help="Only seed one product by slug (e.g. asus-rog-phone-10).",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = Variation.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted} variations."))

        qs = Product.objects.all().select_related("subcategory", "category")
        slug = (options["product"] or "").strip()
        if slug:
            qs = qs.filter(slug=slug)
            if not qs.exists():
                self.stderr.write(self.style.ERROR(f"Product not found: {slug}"))
                return

        created_total = 0
        updated_total = 0
        for product in qs.iterator():
            c, u = self._seed_product(product)
            created_total += c
            updated_total += u

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created_total}, updated {updated_total} variations "
                f"for {qs.count()} product(s)."
            )
        )

    @transaction.atomic
    def _seed_product(self, product: Product) -> tuple[int, int]:
        sub_name = product.subcategory.name if product.subcategory_id else ""
        sizes_list, colors_list = VARIATION_PRESETS.get(sub_name, DEFAULT_PRESET)

        size_objs = [self._get_or_create_size(name) for name in sizes_list]
        color_objs = [self._get_or_create_color(name, code) for name, code in colors_list]
        brand = self._resolve_brand(product)

        sale = product.orginal_price or product.price or Decimal("0")
        mrp = product.price or sale
        discount = product.discount_price
        if discount is None:
            discount = (mrp - sale) if mrp and sale and mrp > sale else Decimal("0")

        combo_count = max(1, len(size_objs) * len(color_objs))
        base_stock = max(0, int(product.stock or 0))
        per = max(1, base_stock // combo_count) if base_stock else 5
        remainder = base_stock - (per * combo_count) if base_stock else 0

        created = 0
        updated = 0
        idx = 0
        for color in color_objs:
            for size in size_objs:
                stock = per + (1 if idx < remainder else 0)
                if not base_stock:
                    stock = 5
                obj, was_created = Variation.objects.update_or_create(
                    product=product,
                    color=color,
                    size=size,
                    brand=brand,
                    defaults={
                        "price": mrp,
                        "discount_price": discount,
                        "stock": stock,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
                idx += 1
        return created, updated

    def _get_or_create_size(self, name: str) -> Size:
        obj, _ = Size.objects.get_or_create(name=name)
        return obj

    def _get_or_create_color(self, name: str, code: str) -> Color:
        obj = Color.objects.filter(name__iexact=name).first()
        if obj:
            if code and obj.code != code:
                obj.code = code
                obj.save(update_fields=["code"])
            return obj
        return Color.objects.create(name=name, code=code)

    def _resolve_brand(self, product: Product) -> Brand:
        from django.utils.text import slugify

        name = (product.brand_name or "").strip() or "Generic"
        brand = Brand.objects.filter(name__iexact=name).first()
        if brand:
            return brand
        slug = slugify(name) or "generic"
        brand = Brand.objects.filter(slug=slug).first()
        if brand:
            return brand
        # Unique slug if name differs but slug collides
        base = slug
        n = 1
        while Brand.objects.filter(slug=slug).exists():
            slug = f"{base}-{n}"
            n += 1
        return Brand.objects.create(name=name, slug=slug)
