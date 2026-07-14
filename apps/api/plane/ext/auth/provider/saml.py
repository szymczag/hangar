# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os
import time
import hashlib
from urllib.parse import urlparse

# Django imports
from django.core.cache import cache

# Third party imports
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.settings import OneLogin_Saml2_Settings

# Module imports
from plane.authentication.adapter.base import Adapter
from plane.authentication.adapter.error import AuthenticationException
from plane.authentication.services import ExternalIdentity
from plane.license.utils.instance_value import get_configuration_value

from plane.ext.auth.error import EXT_AUTHENTICATION_ERROR_CODES

# Fallback TTL for the assertion replay cache when the assertion carries no
# NotOnOrAfter (python3-saml strict mode rejects those anyway).
REPLAY_CACHE_FALLBACK_TTL = 60 * 10

# Common attribute names tried in order when the deployment does not map them
# explicitly.
DEFAULT_EMAIL_ATTRIBUTES = [
    "email",
    "urn:oid:0.9.2342.19200300.100.1.3",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
]
DEFAULT_FIRST_NAME_ATTRIBUTES = [
    "first_name",
    "givenName",
    "urn:oid:2.5.4.42",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
]
DEFAULT_LAST_NAME_ATTRIBUTES = [
    "last_name",
    "sn",
    "urn:oid:2.5.4.4",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",
]


class SAMLProvider(Adapter):
    provider = "saml"

    def __init__(self, request, callback=None, require_enabled=True):
        (
            IS_SAML_ENABLED,
            SAML_IDP_ENTITY_ID,
            SAML_IDP_SSO_URL,
            SAML_IDP_CERTIFICATE,
            SAML_ATTR_EMAIL,
            SAML_ATTR_FIRST_NAME,
            SAML_ATTR_LAST_NAME,
            SAML_ATTR_SUBJECT,
        ) = get_configuration_value(
            [
                {
                    "key": "IS_SAML_ENABLED",
                    "default": os.environ.get("IS_SAML_ENABLED", "0"),
                },
                {
                    "key": "SAML_IDP_ENTITY_ID",
                    "default": os.environ.get("SAML_IDP_ENTITY_ID"),
                },
                {
                    "key": "SAML_IDP_SSO_URL",
                    "default": os.environ.get("SAML_IDP_SSO_URL"),
                },
                {
                    "key": "SAML_IDP_CERTIFICATE",
                    "default": os.environ.get("SAML_IDP_CERTIFICATE"),
                },
                {
                    "key": "SAML_ATTR_EMAIL",
                    "default": os.environ.get("SAML_ATTR_EMAIL"),
                },
                {
                    "key": "SAML_ATTR_FIRST_NAME",
                    "default": os.environ.get("SAML_ATTR_FIRST_NAME"),
                },
                {
                    "key": "SAML_ATTR_LAST_NAME",
                    "default": os.environ.get("SAML_ATTR_LAST_NAME"),
                },
                {
                    "key": "SAML_ATTR_SUBJECT",
                    "default": os.environ.get("SAML_ATTR_SUBJECT"),
                },
            ]
        )

        if (require_enabled and IS_SAML_ENABLED != "1") or not (
            SAML_IDP_ENTITY_ID and SAML_IDP_SSO_URL and SAML_IDP_CERTIFICATE
        ):
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["SAML_NOT_CONFIGURED"],
                error_message="SAML_NOT_CONFIGURED",
            )

        sso_url = urlparse(SAML_IDP_SSO_URL)
        if sso_url.scheme != "https" or not sso_url.netloc or sso_url.username or sso_url.password or sso_url.fragment:
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["SAML_NOT_CONFIGURED"],
                error_message="SAML_NOT_CONFIGURED",
            )

        super().__init__(request=request, provider=self.provider, callback=callback)
        self.idp_entity_id = SAML_IDP_ENTITY_ID
        self.idp_sso_url = SAML_IDP_SSO_URL
        self.idp_certificate = SAML_IDP_CERTIFICATE
        self.attr_email = SAML_ATTR_EMAIL
        self.attr_first_name = SAML_ATTR_FIRST_NAME
        self.attr_last_name = SAML_ATTR_LAST_NAME
        self.attr_subject = SAML_ATTR_SUBJECT

        scheme = "https" if request.is_secure() else "http"
        self.sp_base = f"{scheme}://{request.get_host()}"

    def get_settings_dict(self):
        return {
            "strict": True,
            "sp": {
                "entityId": f"{self.sp_base}/auth/saml/metadata/",
                "assertionConsumerService": {
                    "url": f"{self.sp_base}/auth/saml/callback/",
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                },
                "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            },
            "idp": {
                "entityId": self.idp_entity_id,
                "singleSignOnService": {
                    "url": self.idp_sso_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                },
                "x509cert": self.idp_certificate,
            },
            "security": {
                # Assertions must be signed by the configured IdP certificate;
                # strict mode also enforces audience, destination, and the
                # NotBefore/NotOnOrAfter window.
                "wantAssertionsSigned": True,
                "rejectUnsolicitedResponsesWithInResponseTo": True,
                "requestedAuthnContext": False,
            },
        }

    def get_saml_auth(self):
        request = self.request
        request_data = {
            "https": "on" if request.is_secure() else "off",
            "http_host": request.get_host(),
            "script_name": request.path,
            "get_data": request.GET.copy(),
            "post_data": request.POST.copy(),
        }
        return OneLogin_Saml2_Auth(request_data, self.get_settings_dict())

    def get_sp_metadata(self):
        settings = OneLogin_Saml2_Settings(self.get_settings_dict(), sp_validation_only=True)
        metadata = settings.get_sp_metadata()
        errors = settings.validate_metadata(metadata)
        if errors:
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["SAML_NOT_CONFIGURED"],
                error_message="SAML_NOT_CONFIGURED",
            )
        return metadata

    def __first_attribute(self, attributes, configured_name, fallbacks):
        names = [configured_name] if configured_name else fallbacks
        for name in names:
            values = attributes.get(name) or []
            if values and values[0]:
                return values[0]
        return None

    def authenticate(self, request_id=None):
        auth = self.get_saml_auth()
        auth.process_response(request_id=request_id)

        if auth.get_errors() or not auth.is_authenticated():
            self.logger.warning(
                "SAML response rejected",
                extra={"errors": auth.get_errors(), "reason": auth.get_last_error_reason()},
            )
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["INVALID_SAML_RESPONSE"],
                error_message="INVALID_SAML_RESPONSE",
            )

        # Replay protection: every assertion ID may authenticate exactly once
        # within its validity window. cache.add is atomic — False means the ID
        # was already used.
        assertion_id = auth.get_last_assertion_id()
        not_on_or_after = auth.get_last_assertion_not_on_or_after()
        ttl = max(int(not_on_or_after - time.time()), 1) if not_on_or_after else REPLAY_CACHE_FALLBACK_TTL
        if not assertion_id or not cache.add(f"ext:saml:assertion:{assertion_id}", "1", ttl):
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["INVALID_SAML_RESPONSE"],
                error_message="INVALID_SAML_RESPONSE",
            )

        attributes = auth.get_attributes() or {}
        email = self.__first_attribute(attributes, self.attr_email, DEFAULT_EMAIL_ATTRIBUTES) or auth.get_nameid()
        first_name = self.__first_attribute(attributes, self.attr_first_name, DEFAULT_FIRST_NAME_ATTRIBUTES)
        last_name = self.__first_attribute(attributes, self.attr_last_name, DEFAULT_LAST_NAME_ATTRIBUTES)

        if not first_name:
            first_name = (email or "").split("@")[0]

        if self.attr_subject:
            subject = self.__first_attribute(attributes, self.attr_subject, [])
            subject_format = f"attribute:{self.attr_subject}"
        else:
            subject = auth.get_nameid()
            subject_format = auth.get_nameid_format() or ""
        if not subject or subject_format == "urn:oasis:names:tc:SAML:2.0:nameid-format:transient":
            raise AuthenticationException(
                error_code=EXT_AUTHENTICATION_ERROR_CODES["INVALID_SAML_RESPONSE"],
                error_message="INVALID_SAML_RESPONSE",
            )

        legacy_provider_id = hashlib.sha256(f"{self.idp_entity_id}\0{subject}".encode()).hexdigest()

        self.set_user_data(
            {
                "email": email,
                "user": {
                    # NameID is scoped to the IdP. Hash the IdP/NameID pair so
                    # switching IdPs cannot collide with an existing account.
                    "provider_id": legacy_provider_id,
                    "email": email,
                    "avatar": None,
                    "first_name": first_name,
                    "last_name": last_name or "",
                    "is_password_autoset": True,
                },
            }
        )
        self.set_external_identity(
            ExternalIdentity(
                provider=self.provider,
                issuer=self.idp_entity_id,
                subject=str(subject),
                subject_format=subject_format,
                email=email,
                email_verified=True,
                first_name=first_name,
                last_name=last_name or "",
            )
        )
        return self.complete_login_or_signup()
