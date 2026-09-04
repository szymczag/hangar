# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Global Settings"""

# Python imports
import ipaddress
import logging
import os
import re
from urllib.parse import urlparse
from urllib.parse import urljoin

# Third party imports
import dj_database_url

# Django imports
from django.core.management.utils import get_random_secret_key
from django.core.exceptions import ImproperlyConfigured
from corsheaders.defaults import default_headers


# Module imports
from plane.utils.url import is_valid_url


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_logger = logging.getLogger("plane")


def _bounded_integer_setting(name: str, default: int, minimum: int, maximum: int) -> int:
    raw_value = os.environ.get(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ImproperlyConfigured(f"{name} must be an integer") from error
    if value < minimum or value > maximum:
        raise ImproperlyConfigured(f"{name} must be between {minimum} and {maximum}")
    return value


def _rate_setting(name: str, default: str) -> str:
    value = os.environ.get(name, default)
    if re.fullmatch(r"[1-9][0-9]*/(second|minute|hour|day)", value) is None:
        raise ImproperlyConfigured(f"{name} must use DRF rate syntax such as '10/minute'")
    return value


# Secret Key — use `or` so an explicitly empty env var is treated the same as unset,
# falling back to a random key rather than passing "" to Django (GHSA-cmwv-pjmw-8483).
SECRET_KEY = os.environ.get("SECRET_KEY") or get_random_secret_key()
# Refuse to run silently with a publicly-known or placeholder SECRET_KEY
# (GHSA-cmwv-pjmw-8483). Emit a critical log so operators notice immediately.
# The `or get_random_secret_key()` above means the only way to reach this branch
# is if the environment explicitly passes one of the flagged values.
_INSECURE_SECRET_KEYS = {
    "60gp0byfz2dvffa45cxl20p1scy9xbpf6d8c5y0geejgkyp1b5",  # old publicly-known default
    "change-this-key-on-deployment",  # placeholder shipped in community templates
}
if SECRET_KEY in _INSECURE_SECRET_KEYS:
    _logger.critical(
        "SECURITY: SECRET_KEY is set to a known insecure or placeholder value. "
        "This makes your installation vulnerable to session forgery, CSRF bypass, and "
        "password-reset token forging. Set a unique SECRET_KEY before deploying to production. "
        "Generate one with: "
        'python3 -c "from django.utils.crypto import get_random_secret_key; print(get_random_secret_key())"'
    )

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = int(os.environ.get("DEBUG", "0"))

# Self-hosted mode
IS_SELF_MANAGED = True

# Hangar Runner is deny-by-default until an instance operator opts in. Workspace
# administrators still need to activate it separately and accept current consent.
RUNNER_ENABLED = os.environ.get("RUNNER_ENABLED", "0") == "1"
TODOIST_IMPORTS_ENABLED = os.environ.get("TODOIST_IMPORTS_ENABLED", "0") == "1"
GOOGLE_CALENDAR_CAPACITY_ENABLED = os.environ.get("ENABLE_GOOGLE_CALENDAR_CAPACITY", "0") == "1"
CALENDAR_CAPACITY_USER_RATE = _rate_setting("CALENDAR_CAPACITY_USER_RATE", "10/minute")
CALENDAR_CAPACITY_WORKSPACE_RATE = _rate_setting("CALENDAR_CAPACITY_WORKSPACE_RATE", "30/minute")
CALENDAR_TOKEN_ENCRYPTION_KEYS = tuple(
    key.strip() for key in os.environ.get("CALENDAR_TOKEN_ENCRYPTION_KEYS", "").split(",") if key.strip()
)
if GOOGLE_CALENDAR_CAPACITY_ENABLED and not CALENDAR_TOKEN_ENCRYPTION_KEYS:
    raise ImproperlyConfigured("CALENDAR_TOKEN_ENCRYPTION_KEYS is required when Google Calendar capacity is enabled")
TODOIST_IMPORT_LEASE_SECONDS = _bounded_integer_setting("TODOIST_IMPORT_LEASE_SECONDS", 120, 30, 900)
TODOIST_IMPORT_RECOVERY_GRACE_SECONDS = _bounded_integer_setting("TODOIST_IMPORT_RECOVERY_GRACE_SECONDS", 30, 0, 300)
TODOIST_IMPORT_SOURCE_RETENTION_HOURS = _bounded_integer_setting("TODOIST_IMPORT_SOURCE_RETENTION_HOURS", 24, 1, 168)
TODOIST_IMPORT_PREVIEW_TTL_SECONDS = _bounded_integer_setting("TODOIST_IMPORT_PREVIEW_TTL_SECONDS", 900, 60, 3600)
TODOIST_IMPORT_MAX_ACTIVE_PER_USER = _bounded_integer_setting("TODOIST_IMPORT_MAX_ACTIVE_PER_USER", 1, 1, 100)
TODOIST_IMPORT_MAX_ACTIVE_PER_WORKSPACE = _bounded_integer_setting(
    "TODOIST_IMPORT_MAX_ACTIVE_PER_WORKSPACE", 2, 1, 1000
)
TODOIST_IMPORT_MAX_ROWS_PER_WORKSPACE_24H = _bounded_integer_setting(
    "TODOIST_IMPORT_MAX_ROWS_PER_WORKSPACE_24H", 50_000, 1, 10_000_000
)
TODOIST_IMPORT_MAX_ACTIVE_SOURCE_BYTES_PER_WORKSPACE = _bounded_integer_setting(
    "TODOIST_IMPORT_MAX_ACTIVE_SOURCE_BYTES_PER_WORKSPACE", 10 * 1024 * 1024, 1, 10 * 1024 * 1024 * 1024
)
TODOIST_IMPORT_PREVIEW_USER_RATE = _rate_setting("TODOIST_IMPORT_PREVIEW_USER_RATE", "10/minute")
TODOIST_IMPORT_PREVIEW_WORKSPACE_RATE = _rate_setting("TODOIST_IMPORT_PREVIEW_WORKSPACE_RATE", "30/minute")
TODOIST_IMPORT_EXECUTE_USER_RATE = _rate_setting("TODOIST_IMPORT_EXECUTE_USER_RATE", "3/hour")
TODOIST_IMPORT_EXECUTE_WORKSPACE_RATE = _rate_setting("TODOIST_IMPORT_EXECUTE_WORKSPACE_RATE", "10/hour")

# Duplicating a project writes up to MAX_TOTAL_ROWS rows while holding a lock on
# the workspace row, so an unthrottled caller can stall project creation for
# everyone in that workspace. The DRF default is AnonRateThrottle, which by
# construction does not throttle an authenticated caller.
PROJECT_DUPLICATE_USER_RATE = _rate_setting("PROJECT_DUPLICATE_USER_RATE", "10/hour")
PROJECT_DUPLICATE_WORKSPACE_RATE = _rate_setting("PROJECT_DUPLICATE_WORKSPACE_RATE", "30/hour")
TODOIST_IMPORT_WORKER_CONCURRENCY = _bounded_integer_setting("TODOIST_IMPORT_WORKER_CONCURRENCY", 2, 1, 32)
TODOIST_IMPORT_WORKER_PREFETCH_MULTIPLIER = _bounded_integer_setting(
    "TODOIST_IMPORT_WORKER_PREFETCH_MULTIPLIER", 1, 1, 4
)

# Webhook IP allowlist — comma-separated IPs or CIDR ranges that are allowed as
# webhook targets even if they resolve to private networks.
# Example: "10.0.0.0/8,192.168.1.0/24,172.16.0.5"
_webhook_allowed_ips_raw = os.environ.get("WEBHOOK_ALLOWED_IPS", "")
WEBHOOK_ALLOWED_IPS = []
for _cidr in _webhook_allowed_ips_raw.split(","):
    _cidr = _cidr.strip()
    if not _cidr:
        continue
    try:
        WEBHOOK_ALLOWED_IPS.append(ipaddress.ip_network(_cidr, strict=False))
    except ValueError:
        _logger.warning("WEBHOOK_ALLOWED_IPS: skipping invalid entry %r", _cidr)

# Webhook hostname allowlist — comma-separated hostnames that bypass the
# private-IP SSRF check. Useful for trusted internal services whose IPs are
# dynamic in containerised deployments (e.g. docker-compose service DNS,
# kubernetes service hostnames).
# Example: "silo,silo.namespace.svc.cluster.local,internal-api.lan"
_webhook_allowed_hosts_raw = os.environ.get("WEBHOOK_ALLOWED_HOSTS", "")
WEBHOOK_ALLOWED_HOSTS = [
    _host.strip().rstrip(".").lower() for _host in _webhook_allowed_hosts_raw.split(",") if _host.strip()
]

# Gitea OAuth carries a client secret and bearer token. Private destinations
# are denied by default and may only be enabled by the deployment operator,
# never through the mutable instance configuration alone.
_gitea_allowed_ips_raw = os.environ.get("GITEA_ALLOWED_IPS", "")
GITEA_ALLOWED_IPS = []
for _cidr in _gitea_allowed_ips_raw.split(","):
    _cidr = _cidr.strip()
    if not _cidr:
        continue
    try:
        GITEA_ALLOWED_IPS.append(ipaddress.ip_network(_cidr, strict=False))
    except ValueError:
        _logger.warning("GITEA_ALLOWED_IPS: skipping invalid entry %r", _cidr)

_gitea_allowed_hosts_raw = os.environ.get("GITEA_ALLOWED_HOSTS", "")
GITEA_ALLOWED_HOSTS = [
    _host.strip().rstrip(".").lower() for _host in _gitea_allowed_hosts_raw.split(",") if _host.strip()
]

# GITLAB_HOST is operator-supplied and self-managed GitLab is commonly internal.
# Same rule as Gitea: private destinations only when the deployment operator
# names them, never through the mutable instance configuration alone.
_gitlab_allowed_ips_raw = os.environ.get("GITLAB_ALLOWED_IPS", "")
GITLAB_ALLOWED_IPS = []
for _cidr in _gitlab_allowed_ips_raw.split(","):
    _cidr = _cidr.strip()
    if not _cidr:
        continue
    try:
        GITLAB_ALLOWED_IPS.append(ipaddress.ip_network(_cidr, strict=False))
    except ValueError:
        _logger.warning("GITLAB_ALLOWED_IPS: skipping invalid entry %r", _cidr)

_gitlab_allowed_hosts_raw = os.environ.get("GITLAB_ALLOWED_HOSTS", "")
GITLAB_ALLOWED_HOSTS = [
    _host.strip().rstrip(".").lower() for _host in _gitlab_allowed_hosts_raw.split(",") if _host.strip()
]

_smtp_allowed_ips_raw = os.environ.get("SMTP_ALLOWED_IPS", "")
SMTP_ALLOWED_IPS = []
for _cidr in _smtp_allowed_ips_raw.split(","):
    _cidr = _cidr.strip()
    if not _cidr:
        continue
    try:
        SMTP_ALLOWED_IPS.append(ipaddress.ip_network(_cidr, strict=False))
    except ValueError:
        _logger.warning("SMTP_ALLOWED_IPS: skipping invalid entry %r", _cidr)

_smtp_allowed_hosts_raw = os.environ.get("SMTP_ALLOWED_HOSTS", "")
SMTP_ALLOWED_HOSTS = [
    _host.strip().rstrip(".").lower() for _host in _smtp_allowed_hosts_raw.split(",") if _host.strip()
]

_smtp_allowed_ports_raw = os.environ.get("SMTP_ALLOWED_PORTS", "25,465,587,2525")
SMTP_ALLOWED_PORTS = set()
for _port in _smtp_allowed_ports_raw.split(","):
    try:
        _port_number = int(_port.strip())
        if not 1 <= _port_number <= 65535:
            raise ValueError
        SMTP_ALLOWED_PORTS.add(_port_number)
    except ValueError:
        _logger.warning("SMTP_ALLOWED_PORTS: skipping invalid entry %r", _port)

# Webhook disallowed domains — comma-separated hostnames. Webhooks targeting
# these domains or any of their subdomains are rejected (the request host is
# always appended at validation time as a loop-back guard). Empty by default
# for self-hosted deployments; set to e.g. "example.com" to block specific domains.
_webhook_disallowed_domains_raw = os.environ.get("WEBHOOK_DISALLOWED_DOMAINS", "")
WEBHOOK_DISALLOWED_DOMAINS = [
    _d.strip().rstrip(".").lower() for _d in _webhook_disallowed_domains_raw.split(",") if _d.strip()
]

# Allowed Hosts
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

# Application definition
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    # Inhouse apps
    "plane.analytics",
    "plane.app",
    "plane.space",
    "plane.bgtasks",
    "plane.db",
    "plane.utils",
    "plane.web",
    "plane.middleware",
    "plane.license",
    "plane.api",
    "plane.authentication",
    # Fork extensions (see FORK.md)
    "plane.ext",
    # Third-party things
    "rest_framework",
    "corsheaders",
    "django_celery_beat",
]

# Middlewares
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "plane.authentication.middleware.session.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "crum.CurrentRequestUserMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "plane.middleware.request_body_size.RequestBodySizeLimitMiddleware",
    "plane.middleware.logger.APITokenLogMiddleware",
    "plane.middleware.logger.RequestLoggerMiddleware",
]

# Rest Framework settings
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework.authentication.SessionAuthentication",),
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.AnonRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        # Fork (see FORK.md): configurable like every other rate beside it. The
        # unauthenticated rate is per client address, so anything that puts many
        # browsers behind one address -- the visual regression stack, a corporate
        # NAT -- exhausts thirty requests a minute and gets 429s that the web app
        # reports as "Hangar didn't start correctly".
        "anon": os.environ.get("ANON_RATE_LIMIT", "30/minute"),
        "asset_id": "5/minute",
        "runner_user_read": os.environ.get("RUNNER_API_USER_READ_RATE", "240/minute"),
        "runner_user_mutation": os.environ.get("RUNNER_API_USER_MUTATION_RATE", "60/minute"),
        "runner_read": os.environ.get("RUNNER_API_READ_RATE", "120/minute"),
        "runner_mutation": os.environ.get("RUNNER_API_MUTATION_RATE", "30/minute"),
        "todoist_preview_user": TODOIST_IMPORT_PREVIEW_USER_RATE,
        "todoist_preview_workspace": TODOIST_IMPORT_PREVIEW_WORKSPACE_RATE,
        "todoist_execute_user": TODOIST_IMPORT_EXECUTE_USER_RATE,
        "todoist_execute_workspace": TODOIST_IMPORT_EXECUTE_WORKSPACE_RATE,
        "project_duplicate_user": PROJECT_DUPLICATE_USER_RATE,
        "project_duplicate_workspace": PROJECT_DUPLICATE_WORKSPACE_RATE,
        "calendar_capacity_user": CALENDAR_CAPACITY_USER_RATE,
        "calendar_capacity_workspace": CALENDAR_CAPACITY_WORKSPACE_RATE,
    },
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "EXCEPTION_HANDLER": "plane.authentication.adapter.exception.auth_exception_handler",
    # Preserve original Django URL parameter names (pk) instead of converting to 'id'
    "SCHEMA_COERCE_PATH_PK": False,
}

# API key throttle rate (DRF SimpleRateThrottle format, e.g. "60/minute")
API_KEY_RATE_LIMIT = os.environ.get("API_KEY_RATE_LIMIT", "60/minute")

# Django Auth Backend
AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend",)  # default

# Root Urls
ROOT_URLCONF = "plane.urls"

# Templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": ["templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]


# CORS Settings
CORS_ALLOW_CREDENTIALS = True
cors_origins_raw = os.environ.get("CORS_ALLOWED_ORIGINS", "")
# filter out empty strings
cors_allowed_origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]
if cors_allowed_origins:
    CORS_ALLOWED_ORIGINS = cors_allowed_origins
    secure_origins = False if [origin for origin in cors_allowed_origins if "http:" in origin] else True
else:
    CORS_ALLOW_ALL_ORIGINS = True
    secure_origins = False

CORS_ALLOW_HEADERS = [*default_headers, "X-API-Key"]

# Application Settings
WSGI_APPLICATION = "plane.wsgi.application"
ASGI_APPLICATION = "plane.asgi.application"

# Django Sites
SITE_ID = 1

# User Model
AUTH_USER_MODEL = "db.User"

# Database
if bool(os.environ.get("DATABASE_URL")):
    # Parse database configuration from $DATABASE_URL
    DATABASES = {"default": dj_database_url.config()}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB"),
            "USER": os.environ.get("POSTGRES_USER"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
            "HOST": os.environ.get("POSTGRES_HOST"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }


if os.environ.get("ENABLE_READ_REPLICA", "0") == "1":
    if bool(os.environ.get("DATABASE_READ_REPLICA_URL")):
        # Parse database configuration from $DATABASE_URL
        DATABASES["replica"] = dj_database_url.parse(os.environ.get("DATABASE_READ_REPLICA_URL"))
    else:
        DATABASES["replica"] = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_READ_REPLICA_DB"),
            "USER": os.environ.get("POSTGRES_READ_REPLICA_USER"),
            "PASSWORD": os.environ.get("POSTGRES_READ_REPLICA_PASSWORD"),
            "HOST": os.environ.get("POSTGRES_READ_REPLICA_HOST"),
            "PORT": os.environ.get("POSTGRES_READ_REPLICA_PORT", "5432"),
        }

    # Database Routers
    DATABASE_ROUTERS = ["plane.utils.core.dbrouters.ReadReplicaRouter"]
    # Add middleware at the end for read replica routing
    MIDDLEWARE.append("plane.middleware.db_routing.ReadReplicaRoutingMiddleware")


# Redis Config
REDIS_URL = os.environ.get("REDIS_URL")
REDIS_SSL = REDIS_URL and "rediss" in REDIS_URL

if REDIS_SSL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "CONNECTION_POOL_KWARGS": {"ssl_cert_reqs": False},
            },
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }

# Password validations
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Password reset time the number of seconds the uniquely generated uid will be valid
PASSWORD_RESET_TIMEOUT = 3600

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static-assets", "collected-static")
STATICFILES_DIRS = (os.path.join(BASE_DIR, "static"),)

# Media Settings
MEDIA_ROOT = "mediafiles"
MEDIA_URL = "/media/"

# Internationalization
LANGUAGE_CODE = "en-us"
USE_I18N = True

# Timezones
USE_TZ = True
TIME_ZONE = "UTC"

# Default Auto Field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email settings
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Storage Settings
# Use Minio settings
USE_MINIO = int(os.environ.get("USE_MINIO", 0)) == 1

STORAGES = {"staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}
STORAGES["default"] = {"BACKEND": "plane.settings.storage.S3Storage"}
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "access-key")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "secret-key")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_S3_BUCKET_NAME", "uploads")
AWS_REGION = os.environ.get("AWS_REGION", "")
AWS_DEFAULT_ACL = "public-read"
AWS_QUERYSTRING_AUTH = False
AWS_S3_FILE_OVERWRITE = False
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", None) or os.environ.get("MINIO_ENDPOINT_URL", None)
AWS_S3_PUBLIC_ENDPOINT_URL = os.environ.get("AWS_S3_PUBLIC_ENDPOINT_URL", None)
if AWS_S3_ENDPOINT_URL and USE_MINIO:
    parsed_url = urlparse(os.environ.get("WEB_URL", "http://localhost"))
    AWS_S3_CUSTOM_DOMAIN = f"{parsed_url.netloc}/{AWS_STORAGE_BUCKET_NAME}"
    AWS_S3_URL_PROTOCOL = f"{parsed_url.scheme}:"

# RabbitMQ connection settings
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = os.environ.get("RABBITMQ_PORT", "5672")
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "guest")
RABBITMQ_VHOST = os.environ.get("RABBITMQ_VHOST", "/")
AMQP_URL = os.environ.get("AMQP_URL")

# Celery Configuration
if AMQP_URL:
    CELERY_BROKER_URL = AMQP_URL
else:
    CELERY_BROKER_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{RABBITMQ_VHOST}"

CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["application/json"]


CELERY_IMPORTS = (
    # scheduled tasks
    "plane.bgtasks.issue_automation_task",
    "plane.bgtasks.exporter_expired_task",
    "plane.bgtasks.file_asset_task",
    "plane.bgtasks.email_notification_task",
    "plane.bgtasks.email_delivery_task",
    "plane.bgtasks.cleanup_task",
    "plane.license.bgtasks.telemetry_metrics",
    # management tasks
    "plane.bgtasks.dummy_data_task",
    # issue version tasks
    "plane.bgtasks.issue_version_sync",
    "plane.bgtasks.issue_description_version_sync",
)

FILE_SIZE_LIMIT = int(os.environ.get("FILE_SIZE_LIMIT", 5242880))

# Unsplash Access key
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
# Github Access Token
GITHUB_ACCESS_TOKEN = os.environ.get("GITHUB_ACCESS_TOKEN", False)

# Analytics
ANALYTICS_SECRET_KEY = os.environ.get("ANALYTICS_SECRET_KEY", False)
ANALYTICS_BASE_API = os.environ.get("ANALYTICS_BASE_API", False)

# Posthog settings
POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY", False)
POSTHOG_HOST = os.environ.get("POSTHOG_HOST", False)

# Skip environment variable configuration
SKIP_ENV_VAR = os.environ.get("SKIP_ENV_VAR", "1") == "1"

DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("FILE_SIZE_LIMIT", 5242880))

# Cookie Settings
SESSION_COOKIE_SECURE = secure_origins
SESSION_COOKIE_HTTPONLY = True
SESSION_ENGINE = "plane.db.models.session"
SESSION_COOKIE_AGE = int(os.environ.get("SESSION_COOKIE_AGE", 604800))
SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "session-id")
SESSION_COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", None)
SESSION_SAVE_EVERY_REQUEST = os.environ.get("SESSION_SAVE_EVERY_REQUEST", "0") == "1"

# Admin Cookie
ADMIN_SESSION_COOKIE_NAME = "admin-session-id"
ADMIN_SESSION_COOKIE_AGE = int(os.environ.get("ADMIN_SESSION_COOKIE_AGE", 3600))

# Fork (see FORK.md): WebAuthn second factor for the instance-admin console.
# The relying-party id is validated by the *browser* against the origin of the
# page calling navigator.credentials, which is the admin panel — not the API.
# Left unset it is derived from ADMIN_BASE_URL, falling back to WEB_URL. Set it
# explicitly when the panel lives on a different subdomain from the app: the
# correct value is then their shared parent, because an id that is neither equal
# to nor a registrable-domain suffix of the panel's host makes every sign-in
# fail in the browser before the request is sent.
WEBAUTHN_RP_ID = os.environ.get("WEBAUTHN_RP_ID", None)
WEBAUTHN_RP_NAME = os.environ.get("WEBAUTHN_RP_NAME", "Hangar")
# Comma-separated exact origins an assertion may come from. Derived from the
# admin origin when unset. This is the server-side check, and it is what keeps a
# broad RP ID from being exploitable by a sibling subdomain.
WEBAUTHN_ALLOWED_ORIGINS = os.environ.get("WEBAUTHN_ALLOWED_ORIGINS", "")

# How long a password-verified sign-in may wait for its second factor, and how
# long a challenge stays valid. Enrollment gets longer because the person has to
# find and register a key.
ADMIN_2FA_PENDING_ASSERT_WINDOW = int(os.environ.get("ADMIN_2FA_PENDING_ASSERT_WINDOW", 300))
ADMIN_2FA_PENDING_ENROLL_WINDOW = int(os.environ.get("ADMIN_2FA_PENDING_ENROLL_WINDOW", 900))
ADMIN_2FA_CHALLENGE_TTL = int(os.environ.get("ADMIN_2FA_CHALLENGE_TTL", 300))
ADMIN_2FA_MAX_ATTEMPTS = int(os.environ.get("ADMIN_2FA_MAX_ATTEMPTS", 5))

# Operator escape hatch, not a way to soften the requirement. It exists so an
# instance locked out by a misconfigured relying-party id can be recovered
# without a code change; it is logged loudly at startup when disabled.
ADMIN_WEBAUTHN_REQUIRED = os.environ.get("ADMIN_WEBAUTHN_REQUIRED", "1") == "1"
if not ADMIN_WEBAUTHN_REQUIRED:
    _logger.warning("ADMIN_WEBAUTHN_REQUIRED=0: the instance-admin console is protected by a password alone.")

# CSRF cookies
CSRF_COOKIE_SECURE = secure_origins
CSRF_COOKIE_HTTPONLY = True
CSRF_TRUSTED_ORIGINS = cors_allowed_origins
CSRF_COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", None)
CSRF_FAILURE_VIEW = "plane.authentication.views.common.csrf_failure"

######  Base URLs ######

# Admin Base URL
ADMIN_BASE_URL = os.environ.get("ADMIN_BASE_URL", None)
if ADMIN_BASE_URL and not is_valid_url(ADMIN_BASE_URL):
    ADMIN_BASE_URL = None
ADMIN_BASE_PATH = os.environ.get("ADMIN_BASE_PATH", "/god-mode/")

# Space Base URL
SPACE_BASE_URL = os.environ.get("SPACE_BASE_URL", None)
if SPACE_BASE_URL and not is_valid_url(SPACE_BASE_URL):
    SPACE_BASE_URL = None
SPACE_BASE_PATH = os.environ.get("SPACE_BASE_PATH", "/spaces/")

# App Base URL
APP_BASE_URL = os.environ.get("APP_BASE_URL", None)
if APP_BASE_URL and not is_valid_url(APP_BASE_URL):
    APP_BASE_URL = None
APP_BASE_PATH = os.environ.get("APP_BASE_PATH", "/")

# Live Base URL
LIVE_BASE_URL = os.environ.get("LIVE_BASE_URL", None)
if LIVE_BASE_URL and not is_valid_url(LIVE_BASE_URL):
    LIVE_BASE_URL = None
LIVE_BASE_PATH = os.environ.get("LIVE_BASE_PATH", "/live/")

LIVE_URL = urljoin(LIVE_BASE_URL, LIVE_BASE_PATH) if LIVE_BASE_URL else None
LIVE_SERVER_SECRET_KEY = os.environ.get("LIVE_SERVER_SECRET_KEY")

# WEB URL
WEB_URL = os.environ.get("WEB_URL")

HARD_DELETE_AFTER_DAYS = int(os.environ.get("HARD_DELETE_AFTER_DAYS", 60))


def _retention_days(env_var, default):
    """
    Read a retention window (in days) from the environment, falling back to the
    default when the variable is unset, unparseable, or negative — a negative
    window would otherwise select rows with a future cutoff and delete everything.
    """
    raw = os.environ.get(env_var)
    if raw is None:
        return default
    try:
        days = int(raw)
    except ValueError:
        return default
    return days if days >= 0 else default


# API activity logs hold request/response payloads, so they are retained for a
# shorter window than other logs.
API_ACTIVITY_LOG_RETENTION_DAYS = _retention_days("API_ACTIVITY_LOG_RETENTION_DAYS", 14)

# Webhook delivery logs are retained on their own window, independent of the
# generic HARD_DELETE_AFTER_DAYS.
WEBHOOK_LOG_RETENTION_DAYS = _retention_days("WEBHOOK_LOG_RETENTION_DAYS", 14)

# Email notification logs are retained on their own window.
EMAIL_LOG_RETENTION_DAYS = _retention_days("EMAIL_LOG_RETENTION_DAYS", 7)

# Policy-aware outbound email. These flags stage the migration; requiring
# OpenPGP always suppresses confidential email when no verified key exists.
EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "smtp").strip().lower()
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO", "").strip()
EMAIL_SES_REGION = os.environ.get("EMAIL_SES_REGION", "eu-central-1").strip()
EMAIL_SES_CONFIGURATION_SET_AUTH = os.environ.get("EMAIL_SES_CONFIGURATION_SET_AUTH", "hangar-auth").strip()
EMAIL_SES_CONFIGURATION_SET_NOTIFICATIONS = os.environ.get(
    "EMAIL_SES_CONFIGURATION_SET_NOTIFICATIONS", "hangar-notifications"
).strip()
EMAIL_SES_EVENTS_QUEUE_URL = os.environ.get("EMAIL_SES_EVENTS_QUEUE_URL", "").strip()
EMAIL_SES_EVENTS_TOPIC_ARN = os.environ.get("EMAIL_SES_EVENTS_TOPIC_ARN", "").strip()
EMAIL_SES_ACCOUNT_ID = os.environ.get("EMAIL_SES_ACCOUNT_ID", "").strip()
EMAIL_SES_AWS_ACCESS_KEY_ID = os.environ.get("EMAIL_SES_AWS_ACCESS_KEY_ID", "").strip()
EMAIL_SES_AWS_SECRET_ACCESS_KEY = os.environ.get("EMAIL_SES_AWS_SECRET_ACCESS_KEY", "").strip()
EMAIL_SES_AWS_SESSION_TOKEN = os.environ.get("EMAIL_SES_AWS_SESSION_TOKEN", "").strip()
EMAIL_EVENTS_AWS_ACCESS_KEY_ID = os.environ.get("EMAIL_EVENTS_AWS_ACCESS_KEY_ID", "").strip()
EMAIL_EVENTS_AWS_SECRET_ACCESS_KEY = os.environ.get("EMAIL_EVENTS_AWS_SECRET_ACCESS_KEY", "").strip()
EMAIL_EVENTS_AWS_SESSION_TOKEN = os.environ.get("EMAIL_EVENTS_AWS_SESSION_TOKEN", "").strip()
EMAIL_MESSAGE_ID_DOMAIN = os.environ.get("EMAIL_MESSAGE_ID_DOMAIN", "hangar.invalid").strip().lower()
EMAIL_MAX_STORED_PAYLOAD_BYTES = int(os.environ.get("EMAIL_MAX_STORED_PAYLOAD_BYTES", 8388608))
EMAIL_MAX_ATTACHMENT_BYTES = int(os.environ.get("EMAIL_MAX_ATTACHMENT_BYTES", 5242880))
EMAIL_SMTP_TIMEOUT_SECONDS = int(os.environ.get("EMAIL_SMTP_TIMEOUT_SECONDS", 30))
EMAIL_GPG_BINARY = os.environ.get("EMAIL_GPG_BINARY", "gpg")
EMAIL_OUTBOX_RETENTION_DAYS = _retention_days("EMAIL_OUTBOX_RETENTION_DAYS", 7)
EMAIL_EVENT_RETENTION_DAYS = _retention_days("EMAIL_EVENT_RETENTION_DAYS", 4)
EMAIL_AUDIT_RETENTION_DAYS = _retention_days("EMAIL_AUDIT_RETENTION_DAYS", 90)
EMAIL_DELIVERY_V2_ENABLED = os.environ.get("EMAIL_DELIVERY_V2_ENABLED", "0") == "1"
EMAIL_OPENPGP_ENABLED = os.environ.get("EMAIL_OPENPGP_ENABLED", "0") == "1"

if EMAIL_PROVIDER == "ses":
    EMAIL_PROVIDER = "ses_smtp"
if EMAIL_PROVIDER not in {"smtp", "ses_smtp", "ses_api"}:
    raise ImproperlyConfigured("EMAIL_PROVIDER must be 'smtp', 'ses_smtp', or 'ses_api'")
if not re.fullmatch(r"[A-Za-z0-9.-]+", EMAIL_MESSAGE_ID_DOMAIN):
    raise ImproperlyConfigured("EMAIL_MESSAGE_ID_DOMAIN must be a valid header-safe domain")
if min(EMAIL_MAX_STORED_PAYLOAD_BYTES, EMAIL_MAX_ATTACHMENT_BYTES, EMAIL_SMTP_TIMEOUT_SECONDS) <= 0:
    raise ImproperlyConfigured("Email payload limits and SMTP timeout must be positive")
if EMAIL_OPENPGP_ENABLED and not EMAIL_DELIVERY_V2_ENABLED:
    raise ImproperlyConfigured("EMAIL_OPENPGP_ENABLED requires durable email delivery")
if bool(EMAIL_EVENTS_AWS_ACCESS_KEY_ID) != bool(EMAIL_EVENTS_AWS_SECRET_ACCESS_KEY):
    raise ImproperlyConfigured("SES event-consumer access key ID and secret must be configured together")
if bool(EMAIL_SES_AWS_ACCESS_KEY_ID) != bool(EMAIL_SES_AWS_SECRET_ACCESS_KEY):
    raise ImproperlyConfigured("SES API access key ID and secret must be configured together")
if EMAIL_DELIVERY_V2_ENABLED and EMAIL_PROVIDER in {"ses_smtp", "ses_api"}:
    if not all(
        (
            EMAIL_SES_CONFIGURATION_SET_AUTH,
            EMAIL_SES_CONFIGURATION_SET_NOTIFICATIONS,
            EMAIL_SES_EVENTS_QUEUE_URL,
            EMAIL_SES_EVENTS_TOPIC_ARN,
            EMAIL_SES_ACCOUNT_ID,
        )
    ):
        raise ImproperlyConfigured("SES delivery requires configuration sets, SQS, SNS, and an AWS account ID")
    if not re.fullmatch(r"\d{12}", EMAIL_SES_ACCOUNT_ID):
        raise ImproperlyConfigured("EMAIL_SES_ACCOUNT_ID must contain exactly 12 digits")
    expected_topic_prefix = f"arn:aws:sns:{EMAIL_SES_REGION}:{EMAIL_SES_ACCOUNT_ID}:"
    expected_queue_prefix = f"https://sqs.{EMAIL_SES_REGION}.amazonaws.com/{EMAIL_SES_ACCOUNT_ID}/"
    if not EMAIL_SES_EVENTS_TOPIC_ARN.startswith(expected_topic_prefix):
        raise ImproperlyConfigured("The SES event topic must match the configured region and account")
    if not EMAIL_SES_EVENTS_QUEUE_URL.startswith(expected_queue_prefix):
        raise ImproperlyConfigured("The SES event queue must match the configured region and account")

# Instance Changelog URL
INSTANCE_CHANGELOG_URL = os.environ.get("INSTANCE_CHANGELOG_URL", "")

ATTACHMENT_MIME_TYPES = [
    # Images
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/svg+xml",
    "image/webp",
    "image/tiff",
    "image/bmp",
    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/markdown",
    "application/rtf",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.presentation",
    "application/vnd.oasis.opendocument.graphics",
    # Microsoft Visio
    "application/vnd.visio",
    # Netpbm format
    "image/x-portable-graymap",
    "image/x-portable-bitmap",
    "image/x-portable-pixmap",
    # Open Office Bae
    "application/vnd.oasis.opendocument.database",
    # Audio
    "audio/mpeg",
    "audio/wav",
    "audio/ogg",
    "audio/midi",
    "audio/x-midi",
    "audio/aac",
    "audio/flac",
    "audio/x-m4a",
    # Video
    "video/mp4",
    "video/mpeg",
    "video/ogg",
    "video/webm",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-ms-wmv",
    # Archives
    "application/zip",
    "application/x-rar",
    "application/x-rar-compressed",
    "application/x-tar",
    "application/gzip",
    "application/x-zip",
    "application/x-zip-compressed",
    "application/x-7z-compressed",
    "application/x-compressed",
    "application/x-compressed-tar",
    "application/x-compressed-tar-gz",
    "application/x-compressed-tar-bz2",
    "application/x-compressed-tar-zip",
    "application/x-compressed-tar-7z",
    "application/x-compressed-tar-rar",
    "application/x-compressed-tar-zip",
    # 3D Models
    "model/gltf-binary",
    "model/gltf+json",
    "model/obj",
    # Fonts
    "font/ttf",
    "font/otf",
    "font/woff",
    "font/woff2",
    # Other
    "text/css",
    "text/javascript",
    "application/json",
    "text/xml",
    "text/csv",
    "application/xml",
    # SQL
    "application/x-sql",
    # Gzip
    "application/x-gzip",
    # Markdown
    "text/markdown",
]

# MIME types that browsers can execute as scripts when served inline.
# These must always be served with Content-Disposition: attachment, even if they
# somehow end up stored (e.g. uploaded before this restriction was added).
SCRIPT_CAPABLE_MIME_TYPES: frozenset[str] = frozenset(
    [
        "image/svg+xml",  # SVG with onload / embedded <script> tags
        "text/javascript",
        "application/javascript",
        "text/html",
        "application/xhtml+xml",
        "text/xml",
        "application/xml",
    ]
)

# Seed directory path
SEED_DIR = os.path.join(BASE_DIR, "seeds")

ENABLE_DRF_SPECTACULAR = os.environ.get("ENABLE_DRF_SPECTACULAR", "0") == "1"

if ENABLE_DRF_SPECTACULAR:
    REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"
    INSTALLED_APPS.append("drf_spectacular")
    from .openapi import SPECTACULAR_SETTINGS  # noqa: F401
