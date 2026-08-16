
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve
from django.conf.urls.static import static

from shopingo.error_views import product_search

urlpatterns = [
    path('admin/', admin.site.urls),
    path('search/', product_search, name='product-search'),
    path('', include('shopingo.urls')),
    path('', include('accounts.urls')),
    path('oauth/', include('social_django.urls', namespace='social')),
    path('chaining/', include('smart_selects.urls')),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]

# Media serving for local / small deploys when SERVE_MEDIA=True (WhiteNoise does not serve media)
if settings.DEBUG or getattr(settings, 'SERVE_MEDIA', False):
    urlpatterns += [
        re_path(
            r'^media/(?P<path>.*)$',
            serve,
            {'document_root': settings.MEDIA_ROOT},
        ),
    ]

# Custom error handlers (used when DEBUG=False; also available via /errors/<code>/)
handler400 = 'shopingo.error_views.bad_request'
handler403 = 'shopingo.error_views.permission_denied'
handler404 = 'shopingo.error_views.page_not_found'
handler500 = 'shopingo.error_views.server_error'
