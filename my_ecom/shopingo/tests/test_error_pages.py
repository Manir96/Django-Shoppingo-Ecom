"""QA suite for branded error pages."""
import html

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from shopingo.error_views import ERROR_CATALOG, HANDLERS


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"])
class ErrorPagesTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="testserver")

    def _assert_error_page(self, response, code: int):
        self.assertEqual(response.status_code, code)
        raw = response.content.decode("utf-8", "replace")
        content = html.unescape(raw)
        meta = ERROR_CATALOG[code]
        self.assertIn('data-error-shell="1"', raw)
        self.assertIn(str(code), content)
        self.assertIn(meta["headline"], content)
        self.assertIn('name="robots" content="noindex, nofollow"', raw)
        self.assertIn("Go Home", content)
        self.assertNotIn("Traceback", content)
        self.assertNotIn("SECRET_KEY", content)
        self.assertNotIn("django.db.utils", content)
        self.assertEqual(response.get("X-Robots-Tag"), "noindex, nofollow")
        self.assertIn("logo-icon.png", raw)
        self.assertIn("<footer", raw.lower())

    def test_all_preview_routes(self):
        for code in sorted(ERROR_CATALOG):
            with self.subTest(code=code):
                url = reverse("error-preview", kwargs={"code": code})
                response = self.client.get(url)
                self._assert_error_page(response, code)

    def test_real_404_handler(self):
        response = self.client.get("/this-page-definitely-does-not-exist-xyz/")
        self._assert_error_page(response, 404)
        content = html.unescape(response.content.decode("utf-8", "replace"))
        self.assertIn("Browse categories", content)
        self.assertIn('action="/search/"', response.content.decode("utf-8", "replace"))

    def test_401_actions(self):
        response = self.client.get(reverse("error-preview", kwargs={"code": 401}))
        content = html.unescape(response.content.decode("utf-8", "replace"))
        self.assertIn("Login", content)
        self.assertIn("Register", content)

    def test_403_actions(self):
        response = self.client.get(reverse("error-preview", kwargs={"code": 403}))
        content = html.unescape(response.content.decode("utf-8", "replace"))
        self.assertIn("Dashboard", content)

    def test_500_actions(self):
        response = self.client.get(reverse("error-preview", kwargs={"code": 500}))
        content = html.unescape(response.content.decode("utf-8", "replace"))
        self.assertIn("Retry", content)
        self.assertIn("Contact Support", content)

    def test_429_wait_hint(self):
        response = self.client.get(reverse("error-preview", kwargs={"code": 429}))
        content = html.unescape(response.content.decode("utf-8", "replace")).lower()
        self.assertIn("wait", content)

    def test_503_maintenance(self):
        response = self.client.get(reverse("error-preview", kwargs={"code": 503}))
        content = html.unescape(response.content.decode("utf-8", "replace")).lower()
        self.assertIn("maintenance", content)

    def test_handlers_registered(self):
        self.assertEqual(set(HANDLERS), set(ERROR_CATALOG))

    def test_search_page(self):
        response = self.client.get(reverse("product-search"), {"q": "phone"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Search", response.content.decode("utf-8", "replace"))

    def test_middleware_wraps_plain_forbidden(self):
        from django.http import HttpResponseForbidden
        from django.test import RequestFactory
        from shopingo.middleware import FriendlyErrorPagesMiddleware

        factory = RequestFactory()
        request = factory.get("/secret-area/")
        request.user = type("U", (), {"is_authenticated": False})()

        def get_response(_req):
            return HttpResponseForbidden("Authentication required", content_type="text/plain")

        middleware = FriendlyErrorPagesMiddleware(get_response)
        response = middleware(request)
        self.assertEqual(response.status_code, 403)
        self.assertIn(b'data-error-shell="1"', response.content)
