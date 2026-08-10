"""Seed matched catalog: categories, products, unique type-correct images."""
from __future__ import annotations

import hashlib
import io
import random
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from PIL import Image, ImageDraw

from shopingo.catalog_data import (
    CATALOG,
    CATEGORY_IMAGE_TAGS,
    LEGACY_CATEGORY_NAMES,
    long_description,
)
from shopingo.models import Brand, Category, Product, ProductImage, ProductTag, SubCategory, Tag

User = get_user_model()

DEMO_CATEGORY_NAMES = [c["name"] for c in CATALOG] + LEGACY_CATEGORY_NAMES


class Command(BaseCommand):
    help = "Rebuild catalog with matched titles, brands, descriptions and unique images."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Clear demo catalog first.")
        parser.add_argument("--skip-images", action="store_true", help="Labeled cards only.")

    def handle(self, *args, **options):
        if options["clear"]:
            self._clear_demo_catalog()

        seller = self._get_seller()
        image_cache: dict[str, bytes] = {}
        used_image_hashes: set[str] = set()
        total_products = 0
        skip_images = options["skip_images"]

        Category.objects.exclude(name__in=DEMO_CATEGORY_NAMES).update(is_active=False)
        Category.objects.filter(name__in=LEGACY_CATEGORY_NAMES).update(is_active=False)

        for cat_order, cat_data in enumerate(CATALOG, start=1):
            category, _ = Category.objects.update_or_create(
                name=cat_data["name"],
                defaults={
                    "description": cat_data["description"],
                    "icon": cat_data["icon"],
                    "promo_title": cat_data["promo_title"],
                    "promo_text": cat_data["promo_text"],
                    "menu_order": cat_order,
                    "is_active": True,
                    "meta_title": f"Shop {cat_data['name']} Online | Shopingo",
                    "meta_description": cat_data["description"][:160],
                    "meta_keywords": f"{cat_data['name']}, buy online, shopingo",
                },
            )
            self.stdout.write(self.style.SUCCESS(f"Category: {category.name}"))
            folder = cat_data["folder"]

            if not skip_images:
                tags = CATEGORY_IMAGE_TAGS.get(category.name, "shopping,store")
                self._attach_category_media(category, folder, tags, image_cache)

            for sub_order, sub_data in enumerate(cat_data["subs"], start=1):
                subcategory, _ = SubCategory.objects.update_or_create(
                    name=sub_data["name"],
                    category=category,
                    defaults={
                        "description": f"Browse {sub_data['name']} in {category.name}.",
                        "menu_order": sub_order,
                        "is_active": True,
                        "meta_title": f"{sub_data['name']} | {category.name} | Shopingo",
                        "meta_description": f"Shop the best {sub_data['name']} products at Shopingo.",
                        "meta_keywords": f"{sub_data['name']}, {category.name}",
                    },
                )

                for idx, product_data in enumerate(sub_data["products"]):
                    product_data = dict(product_data)  # copy
                    self._ensure_matched_copy(product_data)
                    self._validate_product(product_data)

                    brand_slug = slugify(product_data["brand"]) or f"brand-{idx}"
                    brand_obj = Brand.objects.filter(name=product_data["brand"]).first()
                    if not brand_obj:
                        brand_obj = Brand.objects.filter(slug=brand_slug).first()
                    if not brand_obj:
                        brand_obj = Brand.objects.create(name=product_data["brand"], slug=brand_slug)
                    sku = (
                        f"{slugify(category.name)[:3].upper()}-"
                        f"{slugify(sub_data['name']).replace('-', '')[:6].upper()}-"
                        f"{idx + 1:03d}"
                    )
                    product, created = Product.objects.update_or_create(
                        sku=sku,
                        defaults=self._product_defaults(
                            product_data=product_data,
                            category=category,
                            subcategory=subcategory,
                            seller=seller,
                            idx=idx,
                        ),
                    )
                    self._attach_tags(product, category, subcategory, product_data["brand"])

                    lock = int(hashlib.md5(sku.encode()).hexdigest()[:8], 16) % 100000
                    if skip_images:
                        data = self._make_labeled_card(product_data, folder)
                    else:
                        data = self._fetch_matched_image(
                            product_data, folder, lock, image_cache, used_image_hashes
                        )
                    self._save_product_images(product, folder, product_data["title"], data)

                    if idx == 0 and not subcategory.featured_image:
                        subcategory.featured_image.save(
                            f"{slugify(sub_data['name'])}-featured.jpg",
                            ContentFile(data),
                            save=True,
                        )

                    total_products += 1
                    action = "Created" if created else "Updated"
                    self.stdout.write(f"  {action}: {product.title} [{product_data['brand']}]")

        self.stdout.write(self.style.SUCCESS(
            f"Done. Seeded {len(CATALOG)} categories, "
            f"{sum(len(c['subs']) for c in CATALOG)} subcategories, "
            f"{total_products} matched products."
        ))
        # Ensure size/color options exist for product detail pages
        from django.core.management import call_command
        call_command("seed_variations", clear=True)

    def _ensure_matched_copy(self, product_data: dict):
        """Guarantee brand appears in title/description text before save."""
        title = product_data["title"]
        brand = product_data["brand"]
        short = product_data["short"]
        blob = f"{title} {short}".lower()
        brand_parts = [p for p in brand.replace("&", " ").replace("-", " ").split() if len(p) > 2]
        if brand.lower() not in blob and not any(p.lower() in blob for p in brand_parts):
            product_data["title"] = f"{brand} {title}"
        short_l = product_data["short"].lower()
        if brand.lower() not in short_l and not any(p.lower() in short_l for p in brand_parts):
            product_data["short"] = f"{brand} — {product_data['short']}"

    def _validate_product(self, product_data: dict):
        title = product_data["title"]
        brand = product_data["brand"]
        short = product_data["short"]
        tags = product_data["tags"]
        blob = f"{title} {short}".lower()

        brand_parts = [p for p in brand.replace("&", " ").replace("-", " ").split() if len(p) > 2]
        brand_ok = brand.lower() in blob or any(p.lower() in blob for p in brand_parts)
        if not brand_ok:
            raise ValueError(f"Brand mismatch: {brand!r} not referenced in {title!r}")

        short_l = short.lower()
        desc_ok = (
            brand.lower() in short_l
            or any(p.lower() in short_l for p in brand_parts)
            or any(w.lower() in short_l for w in title.replace("-", " ").split() if len(w) > 3)
        )
        if not desc_ok:
            raise ValueError(f"Description mismatch for {title!r}")

        if not tags or "," not in tags:
            raise ValueError(f"Missing image tags for {title!r}")

    def _clear_demo_catalog(self):
        cats = Category.objects.filter(name__in=DEMO_CATEGORY_NAMES)
        count = cats.count()
        cats.delete()
        self.stdout.write(self.style.WARNING(f"Cleared {count} demo categories (cascade products)."))

    def _get_seller(self):
        user = (
            User.objects.filter(email="seller1@demo.com").first()
            or User.objects.filter(is_staff=True).first()
            or User.objects.first()
        )
        if not user:
            user = User.objects.create_user(
                email="catalogseller@demo.com",
                password="Password@123",
                username="catalogseller",
            )
        return user

    def _product_defaults(self, *, product_data, category, subcategory, seller, idx):
        regular_d = Decimal(str(product_data["regular"]))
        sale_d = Decimal(str(product_data["sale"]))
        title = product_data["title"]
        brand = product_data["brand"]
        short = product_data["short"]
        long_html = long_description(product_data, category.name, subcategory.name)
        flags = {
            "is_featured": idx % 4 == 0,
            "is_new_arrival": idx % 3 == 0,
            "is_bestseller": idx % 5 == 0,
            "is_trending": idx % 4 == 1,
            "is_popular": idx % 3 == 1,
            "is_recommended": idx % 5 == 1,
            "is_flash_sale": idx % 6 == 0,
        }
        return {
            "title": title,
            "brand_name": brand,
            "short_description": short[:300],
            "description": long_html,
            "description_details": long_html,
            "more_information": f"<p>{brand} authentic product. SKU-managed stock from Shopingo warehouse.</p>",
            "price": regular_d,
            "orginal_price": sale_d,
            "discount_price": regular_d - sale_d,
            "stock": random.randint(8, 120),
            "rating": Decimal(str(round(random.uniform(3.8, 4.9), 2))),
            "review_count": random.randint(12, 860),
            "category": category,
            "subcategory": subcategory,
            "seller": seller,
            "meta_title": f"Buy {title} | {brand} | Shopingo",
            "meta_description": short[:160],
            "meta_keywords": f"{title}, {brand}, {subcategory.name}, {category.name}",
            **flags,
        }

    def _attach_tags(self, product, category, subcategory, brand_name):
        for name in (category.name, subcategory.name, brand_name):
            name = name[:50]
            tag = Tag.objects.filter(name=name).first()
            if not tag:
                base_slug = slugify(name)[:100] or "tag"
                slug = base_slug
                n = 1
                while Tag.objects.filter(slug=slug).exclude(name=name).exists():
                    slug = f"{base_slug}-{n}"
                    n += 1
                tag = Tag.objects.filter(slug=slug).first()
                if not tag:
                    tag = Tag.objects.create(name=name, slug=slug)
            ProductTag.objects.get_or_create(product=product, tag=tag)

    def _download(self, url: str, cache: dict[str, bytes]) -> bytes | None:
        if url in cache:
            return cache[url]
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ShopingoSeedBot/1.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = resp.read()
            if data and len(data) > 2000:
                cache[url] = data
                return data
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            self.stdout.write(self.style.WARNING(f"Image download failed: {url} ({exc})"))
        return None

    def _fetch_matched_image(self, product_data, folder, lock, cache, used_hashes):
        """Type-matched photo when available; otherwise a labeled product card (always matches)."""
        primary = product_data["tags"].split(",")[0].strip()
        encoded = urllib.parse.quote(primary)
        url = f"https://loremflickr.com/800/800/{encoded}?lock={lock}"
        data = self._download(url, cache)
        if data:
            digest = hashlib.md5(data).hexdigest()
            if digest not in used_hashes:
                used_hashes.add(digest)
                return self._stamp_product_label(data, product_data, folder)

        used_hashes.add(hashlib.md5(f"{product_data['title']}-{lock}".encode()).hexdigest())
        return self._make_labeled_card(product_data, folder)

    def _stamp_product_label(self, image_bytes: bytes, product_data: dict, folder: str) -> bytes:
        try:
            im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            im = self._center_square(im, 800)
            draw = ImageDraw.Draw(im)
            draw.rectangle((0, 680, 800, 800), fill=(20, 20, 20))
            draw.text((24, 700), product_data["brand"].upper()[:28], fill=(255, 214, 10))
            draw.text((24, 740), product_data["title"][:42], fill=(255, 255, 255))
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=88, optimize=True)
            return buf.getvalue()
        except Exception:
            return self._make_labeled_card(product_data, folder)

    def _center_square(self, im: Image.Image, size: int) -> Image.Image:
        w, h = im.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        im = im.crop((left, top, left + side, top + side))
        return im.resize((size, size), Image.Resampling.LANCZOS)

    def _make_labeled_card(self, product_data: dict, folder: str) -> bytes:
        colors = {
            "electronics": (24, 48, 96),
            "fashion": (96, 36, 56),
            "home": (36, 88, 64),
            "beauty": (96, 48, 88),
        }
        bg = colors.get(folder, (40, 40, 40))
        img = Image.new("RGB", (800, 800), (245, 245, 245))
        draw = ImageDraw.Draw(img)
        # header band
        draw.rectangle((0, 0, 800, 160), fill=bg)
        draw.rectangle((40, 200, 760, 760), fill=(255, 255, 255), outline=bg, width=4)
        brand = product_data["brand"][:32]
        title = product_data["title"][:40]
        short = product_data.get("short", "")[:70]
        price = product_data.get("sale", 0)
        draw.text((40, 50), brand.upper(), fill=(255, 214, 10))
        draw.text((40, 100), "SHOPINGO AUTHENTIC", fill=(255, 255, 255))
        draw.text((70, 280), title, fill=bg)
        draw.text((70, 360), short[:52], fill=(70, 70, 70))
        if len(short) > 52:
            draw.text((70, 400), short[52:104], fill=(70, 70, 70))
        draw.text((70, 500), f"${price}", fill=bg)
        draw.text((70, 560), "Matched product listing", fill=(120, 120, 120))
        # unique pattern so images are not identical
        seed = sum(ord(c) for c in title) % 200
        for i in range(8):
            x = 80 + ((seed + i * 37) % 600)
            y = 620 + ((seed + i * 19) % 100)
            draw.ellipse((x, y, x + 18, y + 18), fill=bg)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        return buf.getvalue()

    def _to_square(self, image_bytes: bytes, size: int) -> bytes:
        try:
            im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            im = self._center_square(im, size)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=88, optimize=True)
            return buf.getvalue()
        except Exception:
            return image_bytes

    def _save_product_images(self, product, folder, title, image_bytes: bytes):
        product.images.all().delete()
        base = slugify(title)[:40] or "product"
        square_bytes = self._to_square(image_bytes, 800)

        primary = ProductImage(product=product, is_primary=True, is_thumbnail=False, alt_text=title)
        primary.image.save(f"{base}-primary.jpg", ContentFile(square_bytes), save=True)

        thumb_bytes = self._to_square(image_bytes, 400)
        thumb = ProductImage(product=product, is_primary=False, is_thumbnail=True, alt_text=f"{title} thumbnail")
        thumb.image.save(f"{base}-thumb.jpg", ContentFile(thumb_bytes), save=True)

        if not product.og_image:
            product.og_image.save(f"{base}-og.jpg", ContentFile(square_bytes), save=True)

    def _attach_category_media(self, category, folder, tags, cache):
        encoded = urllib.parse.quote(tags)
        data = self._download(f"https://loremflickr.com/800/800/{encoded}?lock=1", cache)
        if not data:
            data = self._make_labeled_card(
                {"title": category.name, "brand": "Shopingo", "short": (category.description or "")[:60], "sale": 0},
                folder,
            )
        slug = slugify(category.name)
        if not category.banner:
            category.banner.save(f"{slug}-banner.jpg", ContentFile(data), save=False)
        if not category.featured_image:
            category.featured_image.save(f"{slug}-featured.jpg", ContentFile(data), save=False)
        if not category.og_image:
            category.og_image.save(f"{slug}-og.jpg", ContentFile(data), save=False)
        category.save()
