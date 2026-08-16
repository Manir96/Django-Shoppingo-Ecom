from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from my_ecom/.env
load_dotenv(BASE_DIR / '.env')

temp_dir = os.path.join(BASE_DIR, 'templates')
static_dir = os.path.join(BASE_DIR, 'static')


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_list(name: str, default=None):
    raw = os.getenv(name, '')
    if not raw.strip():
        return default or []
    return [item.strip() for item in raw.split(',') if item.strip()]


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

SECRET_KEY = (os.getenv('SECRET_KEY') or '').strip().strip('"').strip("'")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        'SECRET_KEY is not set. Create my_ecom/.env from .env.example and set '
        'SECRET_KEY in double quotes if it contains # or $ characters.'
    )

DEBUG = _env_bool('DEBUG', default=False)

ALLOWED_HOSTS = _env_list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

CSRF_TRUSTED_ORIGINS = _env_list('CSRF_TRUSTED_ORIGINS')

AUTH_USER_MODEL = 'accounts.CustomUser'

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'smart_selects',
    'shopingo',
    'accounts',
    'social_django',
    'ckeditor',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Last: swap plain error responses for branded pages
    'shopingo.middleware.FriendlyErrorPagesMiddleware',
]

ROOT_URLCONF = 'my_ecom.urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [temp_dir],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'shopingo.context_processors.global_categories',
                'shopingo.context_processors.cart_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'my_ecom.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'data.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [static_dir]
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_DIRS  = [static_dir,]
STATIC_ROOT = 'staticfiles'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

# WhiteNoise serves files collected into STATIC_ROOT (run collectstatic on deploy).
WHITENOISE_USE_FINDERS = DEBUG

# Serve uploaded media via Django when Nginx/S3 is not configured (local / small deploys)
SERVE_MEDIA = _env_bool('SERVE_MEDIA', default=True)

# Optional message shown on the 503 maintenance error page
MAINTENANCE_ETA = os.getenv('MAINTENANCE_ETA', '').strip()

LOGIN_URL = 'customer_login'
# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Social Auth Settings
LOGIN_REDIRECT_URL = 'account-dashboard'

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.getenv('SOCIAL_AUTH_GOOGLE_OAUTH2_KEY', '').strip()
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.getenv('SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET', '').strip()

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]
if SOCIAL_AUTH_GOOGLE_OAUTH2_KEY and SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET:
    AUTHENTICATION_BACKENDS.insert(0, 'social_core.backends.google.GoogleOAuth2')

SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.user.create_user',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
)

SOCIAL_AUTH_GOOGLE_OAUTH2_AUTH_EXTRA_ARGUMENTS = {
    'prompt': 'select_account'
}


# Email Settings
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = _env_bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '').strip()
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '').strip()
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'noreply@localhost')

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    # Safe fallback so the app stays usable until SMTP credentials are configured
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# Security hardening (tunable via .env for local HTTP vs HTTPS production)
SECURE_SSL_REDIRECT = _env_bool('SECURE_SSL_REDIRECT', default=False)
SESSION_COOKIE_SECURE = _env_bool('SESSION_COOKIE_SECURE', default=False)
CSRF_COOKIE_SECURE = _env_bool('CSRF_COOKIE_SECURE', default=False)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Django forms need readable CSRF cookie in many setups
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
