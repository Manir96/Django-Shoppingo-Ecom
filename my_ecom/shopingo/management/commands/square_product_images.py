"""Square-crop all product images to 1:1 (center crop) for uniform grids."""
from __future__ import annotations

import io
from pathlib import Path

from django.core.management.base import BaseCommand
from PIL import Image

from shopingo.models import ProductImage


class Command(BaseCommand):
    help = "Center-crop every ProductImage to a square and save as JPEG."

    def add_arguments(self, parser):
        parser.add_argument(
            "--size",
            type=int,
            default=800,
            help="Output square size in pixels (default: 800).",
        )

    def handle(self, *args, **options):
        size = options["size"]
        updated = 0
        skipped = 0

        for pi in ProductImage.objects.exclude(image="").iterator():
            try:
                path = pi.image.path
            except (ValueError, FileNotFoundError):
                skipped += 1
                continue

            if not Path(path).exists():
                skipped += 1
                continue

            try:
                with Image.open(path) as im:
                    im = im.convert("RGB")
                    w, h = im.size
                    side = min(w, h)
                    left = (w - side) // 2
                    top = (h - side) // 2
                    im = im.crop((left, top, left + side, top + side))
                    im = im.resize((size, size), Image.Resampling.LANCZOS)
                    buf = io.BytesIO()
                    im.save(buf, format="JPEG", quality=88, optimize=True)
                    data = buf.getvalue()

                # Overwrite same file path
                with open(path, "wb") as f:
                    f.write(data)
                updated += 1
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Skip {path}: {exc}"))
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"Squared {updated} images ({size}x{size}). Skipped {skipped}."
        ))
