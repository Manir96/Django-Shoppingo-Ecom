"""Replace bare HTTP error responses with branded Shopingo error pages."""
from __future__ import annotations

FRIENDLY_STATUSES = frozenset({400, 401, 403, 404, 405, 408, 429, 500, 502, 503})


class FriendlyErrorPagesMiddleware:
    """
    When a view/middleware returns a plain error status (e.g. HttpResponseForbidden
    text, HttpResponseNotAllowed), swap in the branded error template — unless the
    response is already our error page, JSON/AJAX, or admin/static/media.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            return self._maybe_replace(request, response)
        except Exception:
            return response

    def _maybe_replace(self, request, response):
        code = getattr(response, "status_code", None)
        if code not in FRIENDLY_STATUSES:
            return response
        if getattr(response, "_error_page", False):
            return response

        path = request.path or ""
        if path.startswith(("/admin/", "/static/", "/media/", "/oauth/", "/chaining/")):
            return response

        content_type = (response.get("Content-Type") or "").lower()
        if "application/json" in content_type or "application/javascript" in content_type:
            return response
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return response
        if "text/html" not in content_type and content_type and content_type != "text/plain":
            # Keep non-HTML API-ish responses
            if content_type not in ("", "text/plain"):
                return response

        # Don't replace large custom HTML pages that already handle the error
        content = getattr(response, "content", b"") or b""
        if b'data-error-shell="1"' in content[:4000]:
            return response
        if len(content) > 8000 and b"<html" in content[:500].lower():
            return response

        from shopingo.error_views import render_error

        return render_error(request, code)
