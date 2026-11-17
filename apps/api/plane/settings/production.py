# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Production settings"""

import os

from .common import *  # noqa

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = int(os.environ.get("DEBUG", 0)) == 1

# Honor the 'X-Forwarded-Proto' header for request.is_secure()
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# TLS terminates at the trusted ingress or Gateway. Use the canonical external
# host and port supplied by that proxy when Django constructs absolute URLs.
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Fork (see FORK.md): `manage.py check --deploy` runs in CI against these
# settings. Two of its warnings are about work the edge does, not Django:
#
# - security.W008 (SECURE_SSL_REDIRECT): the HTTP-to-HTTPS redirect happens
#   before a request reaches the API. Compose: Caddy's automatic HTTPS
#   (apps/proxy/Caddyfile.ce) redirects whenever SITE_ADDRESS is a host name.
#   Helm: the Gateway (charts/hangar/templates/gateway.yaml) has only an HTTPS
#   listener, and the Ingress always declares TLS for the public host. Turning
#   the redirect on here would also break plain-http installs, which the cookie
#   settings in common.py still support, and in-cluster probes that speak http.
# - security.W004 (SECURE_HSTS_SECONDS): the API shares its host with the web
#   and admin front ends, whose nginx sends Strict-Transport-Security on every
#   response (packages/csp/bin/nginx-headers.mjs), as the space app does
#   (apps/space/app/root.tsx). HSTS applies to the whole host, so /api and
#   /auth are covered by the policy the browser already holds. The all-in-one
#   image is the exception: its Caddy serves the front ends itself
#   (apps/proxy/Caddyfile.aio.ce) and sends no HSTS.
SILENCED_SYSTEM_CHECKS = ["security.W004", "security.W008"]

INSTALLED_APPS += ("scout_apm.django",)  # noqa


# Scout Settings
SCOUT_MONITOR = os.environ.get("SCOUT_MONITOR", False)
SCOUT_KEY = os.environ.get("SCOUT_KEY", "")
SCOUT_NAME = "Hangar"

LOG_DIR = os.path.join(BASE_DIR, "logs")  # noqa

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "verbose": {"format": "%(asctime)s [%(process)d] %(levelname)s %(name)s: %(message)s"},
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(levelname)s %(asctime)s %(module)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "level": "INFO",
        },
        "file": {
            "class": "plane.utils.logging.SizedTimedRotatingFileHandler",
            "filename": (
                os.path.join(BASE_DIR, "logs", "plane-debug.log")  # noqa
                if DEBUG
                else os.path.join(BASE_DIR, "logs", "plane-error.log")  # noqa
            ),
            "when": "s",
            "maxBytes": 1024 * 1024 * 1,
            "interval": 1,
            "backupCount": 5,
            "formatter": "json",
            "level": "DEBUG" if DEBUG else "ERROR",
        },
    },
    "loggers": {
        "plane.api.request": {
            "level": "DEBUG" if DEBUG else "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "plane.api": {
            "level": "DEBUG" if DEBUG else "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "plane.worker": {
            "level": "DEBUG" if DEBUG else "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "plane.exception": {
            "level": "DEBUG" if DEBUG else "ERROR",
            "handlers": ["console", "file"],
            "propagate": False,
        },
        "plane.external": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "plane.authentication": {
            "level": "DEBUG" if DEBUG else "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "plane.migrations": {
            "level": "DEBUG" if DEBUG else "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        # Content-Security-Policy violation reports (plane/web/views.py). Without
        # an entry here they reached only Python's last-resort handler, which
        # prints the message and drops every field of the report.
        "plane.security": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}
