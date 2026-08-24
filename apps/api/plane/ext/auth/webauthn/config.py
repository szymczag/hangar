# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Relying-party identity for the instance-admin console.

Getting this wrong does not produce a subtle bug. The relying-party id is
checked by the *browser* against the origin of the page calling
``navigator.credentials``, so an id that is neither equal to nor a
registrable-domain suffix of the panel's host makes the call fail with a
``SecurityError`` before any request reaches the API. With a mandatory second
factor that is not "2FA is broken" — it is every administrator locked out of
the console, recoverable only from a shell.

So the checks here run *before* options are issued and refuse to produce
something the browser will reject, turning an opaque failure in the console
into a named error an operator can act on.
"""

# Python imports
import ipaddress
from urllib.parse import urlsplit

# Django imports
from django.conf import settings

# Module imports
from plane.authentication.utils.host import base_host

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}


def _origin_of(url):
    """Reduce a URL to scheme://host[:port], or "" when it has no host."""
    parts = urlsplit(url or "")
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}"


def _host_of(origin):
    host = urlsplit(origin).hostname or ""
    return host.rstrip(".").lower()


def admin_origin(request):
    """The origin the console is served from, per base_host()."""
    return _origin_of(base_host(request=request, is_admin=True))


def allowed_origins(request):
    """Exact origins an assertion may be signed for.

    Configured explicitly, or derived. The derivation adds the app origin only
    when ADMIN_BASE_URL is unset — in that topology the console lives under the
    app origin anyway, whereas adding it unconditionally would widen the
    allowlist to a host the console does not use.
    """
    configured = (settings.WEBAUTHN_ALLOWED_ORIGINS or "").strip()
    if configured:
        return {origin for origin in (_origin_of(o.strip()) for o in configured.split(",")) if origin}

    origins = set()
    console = admin_origin(request)
    if console:
        origins.add(console)
    if not getattr(settings, "ADMIN_BASE_URL", None):
        app = _origin_of(settings.WEB_URL or settings.APP_BASE_URL or "")
        if app:
            origins.add(app)
    return origins


def rp_id(request):
    """The relying-party id, configured or derived from the console's host."""
    configured = (settings.WEBAUTHN_RP_ID or "").strip().rstrip(".").lower()
    if configured:
        return configured

    source = getattr(settings, "ADMIN_BASE_URL", None) or settings.WEB_URL or settings.APP_BASE_URL or ""
    return _host_of(_origin_of(source))


def validate_config(request):
    """Return a human-readable reason the configuration cannot work, or None.

    Every check here corresponds to a browser-side rejection we would otherwise
    hit with no diagnostic.
    """
    identifier = rp_id(request)
    if not identifier:
        return "No relying-party ID could be derived. Set WEBAUTHN_RP_ID, ADMIN_BASE_URL or WEB_URL."

    try:
        ipaddress.ip_address(identifier)
    except ValueError:
        pass
    else:
        return f"The relying-party ID '{identifier}' is an IP address; WebAuthn requires a domain name."

    origins = allowed_origins(request)
    if not origins:
        return "No allowed origin could be derived. Set WEBAUTHN_ALLOWED_ORIGINS or ADMIN_BASE_URL."

    for origin in sorted(origins):
        host = _host_of(origin)
        # The browser accepts an RP ID equal to the page's host or a
        # registrable-domain suffix of it, and nothing else.
        if not (host == identifier or host.endswith(f".{identifier}")):
            return (
                f"The relying-party ID '{identifier}' is neither '{host}' nor a parent of it. "
                f"Set WEBAUTHN_RP_ID to a domain both share."
            )
        scheme = urlsplit(origin).scheme
        if scheme != "https" and host not in LOOPBACK_HOSTS:
            return (
                f"'{origin}' is not a secure context. WebAuthn requires HTTPS outside localhost, "
                f"so the console must be served over TLS before a security key can be used."
            )
    return None


__all__ = ["admin_origin", "allowed_origins", "rp_id", "validate_config"]
