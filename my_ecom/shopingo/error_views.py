"""Production-ready error pages for Shopingo."""
from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token
from django.views.decorators.http import require_GET

ERROR_CATALOG = {
    400: {
        "slug": "bad-request",
        "title": "Bad Request",
        "headline": "The request could not be processed.",
        "description": "Something about this request looks invalid or incomplete. Please go back and try again, or continue shopping.",
        "illustration": "bad-request",
        "show_search": True,
        "actions": ("home", "shop", "back", "support"),
    },
    401: {
        "slug": "unauthorized",
        "title": "Unauthorized",
        "headline": "Please login to continue.",
        "description": "You need an account session to view this page. Sign in or create a free account to continue.",
        "illustration": "unauthorized",
        "show_search": False,
        "actions": ("login", "register", "home"),
    },
    403: {
        "slug": "forbidden",
        "title": "Forbidden",
        "headline": "You don't have permission to access this page.",
        "description": "This area is restricted for your account. Head back to your dashboard or the storefront.",
        "illustration": "forbidden",
        "show_search": False,
        "actions": ("dashboard", "home", "support"),
    },
    404: {
        "slug": "not-found",
        "title": "Page Not Found",
        "headline": "Oops! The page you're looking for doesn't exist.",
        "description": "The link may be broken, or the page may have moved. Try searching, browse categories, or continue shopping.",
        "illustration": "not-found",
        "show_search": True,
        "show_suggestions": True,
        "actions": ("home", "shop", "back", "support"),
    },
    405: {
        "slug": "method-not-allowed",
        "title": "Method Not Allowed",
        "headline": "That action isn't supported here.",
        "description": "The browser used an HTTP method this page doesn't accept. Go back or continue shopping from the homepage.",
        "illustration": "method",
        "show_search": True,
        "actions": ("home", "shop", "back", "support"),
    },
    408: {
        "slug": "request-timeout",
        "title": "Request Timeout",
        "headline": "The request took too long.",
        "description": "Your connection timed out before we could finish. Please try again in a moment.",
        "illustration": "timeout",
        "show_search": False,
        "actions": ("retry", "home", "shop", "support"),
    },
    429: {
        "slug": "too-many-requests",
        "title": "Too Many Requests",
        "headline": "Too many requests.",
        "description": "You've made requests a little too quickly. Please wait a moment, then try again.",
        "illustration": "rate-limit",
        "show_search": False,
        "actions": ("retry", "home", "support"),
        "wait_hint": "Wait about 30–60 seconds before retrying.",
    },
    500: {
        "slug": "server-error",
        "title": "Internal Server Error",
        "headline": "Something went wrong on our side.",
        "description": "We've logged the issue and our team will look into it. Please retry, or contact support if it continues.",
        "illustration": "server",
        "show_search": False,
        "actions": ("retry", "home", "support"),
    },
    502: {
        "slug": "bad-gateway",
        "title": "Bad Gateway",
        "headline": "We hit a temporary gateway issue.",
        "description": "An upstream service didn't respond correctly. Please retry shortly — this is usually temporary.",
        "illustration": "gateway",
        "show_search": False,
        "actions": ("retry", "home", "support"),
    },
    503: {
        "slug": "service-unavailable",
        "title": "Service Unavailable",
        "headline": "We're performing maintenance.",
        "description": "Shopingo is temporarily unavailable while we improve the store. Thanks for your patience.",
        "illustration": "maintenance",
        "show_search": False,
        "actions": ("retry", "home", "support"),
        "show_downtime": True,
    },
}


def _safe_extra_context(request, code: int) -> dict:
    """Optional enrichment for 404 — never raise into the error page."""
    ctx: dict = {
        "popular_products": [],
        "browse_categories": [],
        "recent_views": [],
        "maintenance_eta": getattr(settings, "MAINTENANCE_ETA", "") or "",
    }
    if code != 404:
        return ctx
    try:
        from shopingo.models import Category, Product, RecentlyViewed

        ctx["popular_products"] = list(
            Product.objects.filter(is_popular=True)
            .prefetch_related("images")
            .order_by("-id")[:8]
        )
        if not ctx["popular_products"]:
            ctx["popular_products"] = list(
                Product.objects.prefetch_related("images").order_by("-id")[:8]
            )
        ctx["browse_categories"] = list(Category.objects.order_by("name")[:8])
        if getattr(request, "user", None) and request.user.is_authenticated:
            ctx["recent_views"] = list(
                RecentlyViewed.objects.filter(user=request.user)
                .select_related("product")
                .prefetch_related("product__images")
                .order_by("-viewed_at")[:6]
            )
    except Exception:
        pass
    return ctx


def render_error(request, status_code: int, exception=None) -> HttpResponse:
    """Render a branded error page with the correct HTTP status."""
    code = int(status_code)
    meta = ERROR_CATALOG.get(code) or ERROR_CATALOG[500]
    context = {
        "error_code": code,
        "error": meta,
        "exception": None,  # never expose exception details to clients
        "page_title": f"{code} {meta['title']} | Shopingo",
        "meta_description": meta["headline"],
        "is_error_page": True,
    }
    context.update(_safe_extra_context(request, code))

    try:
        response = render(request, "errors/error.html", context, status=code)
    except Exception:
        # Absolute fallback if template/DB/context processors fail (esp. 500)
        response = HttpResponse(_minimal_error_html(code, meta), status=code, content_type="text/html")

    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response._error_page = True  # type: ignore[attr-defined]
    return response


def _minimal_error_html(code: int, meta: dict) -> str:
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{code} {meta['title']} | Shopingo</title>
<style>
body{{margin:0;font-family:system-ui,sans-serif;background:#f1f5f9;color:#0f172a;display:flex;min-height:100vh;align-items:center;justify-content:center}}
.card{{background:#fff;border-radius:18px;padding:2rem;max-width:420px;box-shadow:0 10px 40px rgba(15,23,42,.08);text-align:center}}
.code{{font-size:3.5rem;font-weight:800;letter-spacing:-.04em;margin:0}}
a{{display:inline-block;margin:.35rem;padding:.65rem 1.1rem;border-radius:12px;background:#0f172a;color:#fff;text-decoration:none;font-weight:600}}
</style></head><body>
<div class="card">
<p class="code">{code}</p>
<h1 style="font-size:1.25rem">{meta['headline']}</h1>
<p style="color:#64748b">{meta['description']}</p>
<a href="/">Go Home</a>
</div></body></html>"""


@requires_csrf_token
def bad_request(request, exception=None):
    return render_error(request, 400, exception)


def unauthorized(request, exception=None):
    return render_error(request, 401, exception)


@requires_csrf_token
def permission_denied(request, exception=None):
    return render_error(request, 403, exception)


@requires_csrf_token
def page_not_found(request, exception=None):
    return render_error(request, 404, exception)


def method_not_allowed(request, exception=None):
    return render_error(request, 405, exception)


def request_timeout(request, exception=None):
    return render_error(request, 408, exception)


def too_many_requests(request, exception=None):
    return render_error(request, 429, exception)


@requires_csrf_token
def server_error(request):
    return render_error(request, 500)


def bad_gateway(request, exception=None):
    return render_error(request, 502, exception)


def service_unavailable(request, exception=None):
    return render_error(request, 503, exception)


HANDLERS = {
    400: bad_request,
    401: unauthorized,
    403: permission_denied,
    404: page_not_found,
    405: method_not_allowed,
    408: request_timeout,
    429: too_many_requests,
    500: server_error,
    502: bad_gateway,
    503: service_unavailable,
}


@require_GET
def preview_error(request, code: int):
    """Preview / QA route for every branded error page."""
    if code not in HANDLERS:
        return render_error(request, 404)
    return HANDLERS[code](request)


def product_search(request):
    """Simple storefront search used by header + 404 search form."""
    from django.db.models import Q
    from shopingo.models import Product

    q = (request.GET.get("q") or "").strip()[:120]
    products = Product.objects.none()
    if q:
        products = (
            Product.objects.filter(
                Q(title__icontains=q)
                | Q(brand_name__icontains=q)
                | Q(sku__icontains=q)
            )
            .prefetch_related("images")
            .distinct()[:48]
        )
    return render(
        request,
        "errors/search_results.html",
        {
            "q": q,
            "products": products,
            "page_title": f"Search: {q}" if q else "Search | Shopingo",
        },
    )
