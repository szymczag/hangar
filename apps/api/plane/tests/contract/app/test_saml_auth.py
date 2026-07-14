# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import base64
import datetime
import time
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from onelogin.saml2.utils import OneLogin_Saml2_Utils

from plane.db.models import User
from plane.license.models import Instance, InstanceConfiguration

from plane.ext.auth.error import EXT_AUTHENTICATION_ERROR_CODES
from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES

IDP_ENTITY_ID = "https://idp.test/metadata"
IDP_SSO_URL = "https://idp.test/sso"
# Served via SERVER_NAME=hangar.test — python3-saml rejects dotless hostnames
SP_ENTITY_ID = "http://hangar.test/auth/saml/metadata/"
ACS_URL = "http://hangar.test/auth/saml/callback/"

_IDP_KEYPAIR = None


def idp_keypair():
    """Self-signed IdP signing certificate (module-cached, keygen is slow)."""
    global _IDP_KEYPAIR
    if _IDP_KEYPAIR is None:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "idp.test")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
            .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
            .sign(key, hashes.SHA256())
        )
        key_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ).decode()
        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
        _IDP_KEYPAIR = (key_pem, cert_pem)
    return _IDP_KEYPAIR


@pytest.fixture
def setup_instance(db):
    instance_id = uuid.uuid4() if not Instance.objects.exists() else Instance.objects.first().id
    instance, _ = Instance.objects.update_or_create(
        id=instance_id,
        defaults={
            "instance_name": "Test Instance",
            "instance_id": str(uuid.uuid4()),
            "current_version": "1.0.0",
            "domain": "http://localhost:8000",
            "last_checked_at": timezone.now(),
            "is_setup_done": True,
        },
    )
    return instance


@pytest.fixture
def saml_config(db):
    _, cert_pem = idp_keypair()
    for key, value in (
        ("IS_SAML_ENABLED", "1"),
        ("SAML_IDP_ENTITY_ID", IDP_ENTITY_ID),
        ("SAML_IDP_SSO_URL", IDP_SSO_URL),
        ("SAML_IDP_CERTIFICATE", cert_pem),
        ("ENABLE_SIGNUP", "1"),
    ):
        InstanceConfiguration.objects.update_or_create(
            key=key, defaults={"value": value, "category": "SAML", "is_encrypted": False}
        )


@pytest.fixture
def django_client():
    return Client(HTTP_USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) test-client", SERVER_NAME="hangar.test")


def saml_time(offset_seconds=0):
    return OneLogin_Saml2_Utils.parse_time_to_SAML(int(time.time()) + offset_seconds)


def build_response(
    request_id,
    email="saml-user@hangar.test",
    name_id=None,
    name_id_format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
    sign_assertion=True,
    audience=SP_ENTITY_ID,
    destination=ACS_URL,
    not_on_or_after=300,
    issuer=IDP_ENTITY_ID,
    tamper=False,
):
    """Build (and optionally sign) a SAMLResponse document."""
    key_pem, cert_pem = idp_keypair()
    assertion_id = "_a" + uuid.uuid4().hex
    now = saml_time()
    expiry = saml_time(not_on_or_after)

    assertion = f"""<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" ID="{assertion_id}" Version="2.0" IssueInstant="{now}"><saml:Issuer>{issuer}</saml:Issuer><saml:Subject><saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{email}</saml:NameID><saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer"><saml:SubjectConfirmationData InResponseTo="{request_id}" NotOnOrAfter="{expiry}" Recipient="{destination}"/></saml:SubjectConfirmation></saml:Subject><saml:Conditions NotBefore="{saml_time(-60)}" NotOnOrAfter="{expiry}"><saml:AudienceRestriction><saml:Audience>{audience}</saml:Audience></saml:AudienceRestriction></saml:Conditions><saml:AuthnStatement AuthnInstant="{now}" SessionIndex="_s{uuid.uuid4().hex}"><saml:AuthnContext><saml:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:Password</saml:AuthnContextClassRef></saml:AuthnContext></saml:AuthnStatement><saml:AttributeStatement><saml:Attribute Name="email"><saml:AttributeValue xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="xs:string">{email}</saml:AttributeValue></saml:Attribute><saml:Attribute Name="first_name"><saml:AttributeValue xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="xs:string">Sally</saml:AttributeValue></saml:Attribute><saml:Attribute Name="last_name"><saml:AttributeValue xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="xs:string">Assertion</saml:AttributeValue></saml:Attribute></saml:AttributeStatement></saml:Assertion>"""  # noqa: E501

    if name_id is not None or name_id_format != "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress":
        assertion = assertion.replace(
            f'Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{email}</saml:NameID>',
            f'Format="{name_id_format}">{name_id or email}</saml:NameID>',
        )

    if sign_assertion:
        signed = OneLogin_Saml2_Utils.add_sign(assertion, key_pem, cert_pem)
        assertion = signed.decode() if isinstance(signed, bytes) else signed
        # Strip the XML declaration add_sign may prepend
        if assertion.startswith("<?xml"):
            assertion = assertion.split("?>", 1)[1]

    if tamper:
        assertion = assertion.replace(email, "attacker@hangar.test")

    response = f"""<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" ID="_r{uuid.uuid4().hex}" Version="2.0" IssueInstant="{now}" Destination="{destination}" InResponseTo="{request_id}"><saml:Issuer xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">{issuer}</saml:Issuer><samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>{assertion}</samlp:Response>"""  # noqa: E501
    return base64.b64encode(response.encode()).decode()


def initiate(django_client):
    """Run the initiate step; return (relay_token, request_id, response)."""
    response = django_client.get(reverse("saml-initiate"))
    assert response.status_code == 302
    location = urlparse(response["Location"])
    assert location.netloc == "idp.test"
    query = parse_qs(location.query)
    assert "SAMLRequest" in query
    relay_token = query["RelayState"][0]
    flow = cache.get(f"ext:saml:relay:{relay_token}")
    assert flow and flow["request_id"]
    return relay_token, flow["request_id"], response


def post_acs(django_client, saml_response, relay_token):
    return django_client.post(reverse("saml-callback"), {"SAMLResponse": saml_response, "RelayState": relay_token})


def error_code_of(response):
    query = parse_qs(urlparse(response["Location"]).query)
    return int(query["error_code"][0]) if "error_code" in query else None


@pytest.mark.contract
class TestSAMLMetadata:
    @pytest.mark.django_db
    def test_metadata_served(self, django_client, setup_instance, saml_config):
        response = django_client.get(reverse("saml-metadata"))
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/xml")
        body = response.content.decode()
        assert SP_ENTITY_ID in body
        assert ACS_URL in body

    @pytest.mark.django_db
    def test_metadata_not_configured(self, django_client, setup_instance):
        response = django_client.get(reverse("saml-metadata"))
        assert response.status_code == 404


@pytest.mark.contract
class TestSAMLInitiate:
    @pytest.mark.django_db
    def test_not_configured(self, django_client, setup_instance):
        response = django_client.get(reverse("saml-initiate"))
        assert response.status_code == 302
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["SAML_NOT_CONFIGURED"]

    @pytest.mark.django_db
    def test_disabled_provider_is_rejected(self, django_client, setup_instance, saml_config):
        InstanceConfiguration.objects.update_or_create(
            key="IS_SAML_ENABLED",
            defaults={"value": "0", "category": "SAML", "is_encrypted": False},
        )
        response = django_client.get(reverse("saml-initiate"))
        assert response.status_code == 302
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["SAML_NOT_CONFIGURED"]

    @pytest.mark.django_db
    def test_http_idp_sso_url_is_rejected(self, django_client, setup_instance, saml_config):
        InstanceConfiguration.objects.update_or_create(
            key="SAML_IDP_SSO_URL",
            defaults={"value": "http://idp.test/sso", "category": "SAML", "is_encrypted": False},
        )
        response = django_client.get(reverse("saml-initiate"))
        assert response.status_code == 302
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["SAML_NOT_CONFIGURED"]

    @pytest.mark.django_db
    def test_rate_limit_is_enforced(self, django_client, setup_instance, saml_config):
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                "plane.ext.auth.views.saml.authentication_throttle_allows",
                lambda _request: False,
            )
            response = django_client.get(reverse("saml-initiate"))
        assert response.status_code == 302
        assert error_code_of(response) == AUTHENTICATION_ERROR_CODES["RATE_LIMIT_EXCEEDED"]

    @pytest.mark.django_db
    def test_redirects_to_idp_with_relay_state(self, django_client, setup_instance, saml_config):
        initiate(django_client)


@pytest.mark.contract
class TestSAMLCallback:
    @pytest.mark.django_db
    def test_happy_path_signs_up_user(self, django_client, setup_instance, saml_config):
        relay_token, request_id, _ = initiate(django_client)
        response = post_acs(django_client, build_response(request_id), relay_token)
        assert response.status_code == 302
        assert error_code_of(response) is None
        user = User.objects.get(email="saml-user@hangar.test")
        assert user.first_name == "Sally"
        assert user.last_login_medium == "saml"
        assert django_client.session.get("_auth_user_id") == str(user.id)

    @pytest.mark.django_db
    def test_unsigned_assertion_rejected(self, django_client, setup_instance, saml_config):
        relay_token, request_id, _ = initiate(django_client)
        response = post_acs(django_client, build_response(request_id, sign_assertion=False), relay_token)
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["INVALID_SAML_RESPONSE"]
        assert not User.objects.filter(email="saml-user@hangar.test").exists()

    @pytest.mark.django_db
    def test_tampered_assertion_rejected(self, django_client, setup_instance, saml_config):
        relay_token, request_id, _ = initiate(django_client)
        response = post_acs(django_client, build_response(request_id, tamper=True), relay_token)
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["INVALID_SAML_RESPONSE"]
        assert not User.objects.filter(email="attacker@hangar.test").exists()

    @pytest.mark.django_db
    def test_expired_assertion_rejected(self, django_client, setup_instance, saml_config):
        relay_token, request_id, _ = initiate(django_client)
        response = post_acs(django_client, build_response(request_id, not_on_or_after=-120), relay_token)
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["INVALID_SAML_RESPONSE"]

    @pytest.mark.django_db
    def test_wrong_audience_rejected(self, django_client, setup_instance, saml_config):
        relay_token, request_id, _ = initiate(django_client)
        response = post_acs(django_client, build_response(request_id, audience="https://other-sp.test/"), relay_token)
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["INVALID_SAML_RESPONSE"]

    @pytest.mark.django_db
    def test_wrong_in_response_to_rejected(self, django_client, setup_instance, saml_config):
        relay_token, _, _ = initiate(django_client)
        response = post_acs(django_client, build_response("_forged" + uuid.uuid4().hex), relay_token)
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["INVALID_SAML_RESPONSE"]

    @pytest.mark.django_db
    def test_unknown_relay_state_rejected(self, django_client, setup_instance, saml_config):
        _, request_id, _ = initiate(django_client)
        response = post_acs(django_client, build_response(request_id), "not-a-real-token")
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["INVALID_SAML_RESPONSE"]

    @pytest.mark.django_db
    def test_relay_state_single_use(self, django_client, setup_instance, saml_config):
        relay_token, request_id, _ = initiate(django_client)
        saml_response = build_response(request_id)
        first = post_acs(django_client, saml_response, relay_token)
        assert error_code_of(first) is None
        # Same RelayState again: the cache entry was consumed.
        second = post_acs(django_client, saml_response, relay_token)
        assert error_code_of(second) == EXT_AUTHENTICATION_ERROR_CODES["INVALID_SAML_RESPONSE"]

    @pytest.mark.django_db
    def test_assertion_replay_rejected(self, django_client, setup_instance, saml_config):
        """Same assertion via a *fresh* RelayState must still be rejected."""
        relay_token, request_id, _ = initiate(django_client)
        saml_response = build_response(request_id)
        assert error_code_of(post_acs(django_client, saml_response, relay_token)) is None

        # Attacker initiates their own flow and replays the captured response.
        fresh_client = Client(HTTP_USER_AGENT="Mozilla/5.0 replay", SERVER_NAME="hangar.test")
        fresh_relay, _, _ = initiate(fresh_client)
        # Reuse of the old response now fails InResponseTo (different request
        # id) AND the assertion-id replay cache; either way it must not log in.
        response = post_acs(fresh_client, saml_response, fresh_relay)
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["INVALID_SAML_RESPONSE"]

    @pytest.mark.django_db
    def test_acs_rejects_get(self, django_client, setup_instance, saml_config):
        response = django_client.get(reverse("saml-callback"))
        assert response.status_code == 405

    @pytest.mark.django_db
    def test_signup_disabled_without_invite_rejected(self, django_client, setup_instance, saml_config):
        InstanceConfiguration.objects.update_or_create(
            key="ENABLE_SIGNUP", defaults={"value": "0", "category": "AUTHENTICATION", "is_encrypted": False}
        )
        relay_token, request_id, _ = initiate(django_client)
        response = post_acs(django_client, build_response(request_id), relay_token)
        assert response.status_code == 302
        assert error_code_of(response) is not None
        assert not User.objects.filter(email="saml-user@hangar.test").exists()

    @pytest.mark.django_db
    def test_relay_state_is_bound_to_initiating_browser(self, django_client, setup_instance, saml_config):
        relay_token, request_id, _ = initiate(django_client)
        saml_response = build_response(request_id)
        other_browser = Client(HTTP_USER_AGENT="Mozilla/5.0 victim", SERVER_NAME="hangar.test")

        rejected = post_acs(other_browser, saml_response, relay_token)
        assert error_code_of(rejected) == EXT_AUTHENTICATION_ERROR_CODES["INVALID_SAML_RESPONSE"]
        assert cache.get(f"ext:saml:relay:{relay_token}") is not None
        assert "_auth_user_id" not in other_browser.session

        accepted = post_acs(django_client, saml_response, relay_token)
        assert error_code_of(accepted) is None
        assert django_client.session.get("_auth_user_id") is not None

    @pytest.mark.django_db
    def test_stable_subject_cannot_switch_to_another_users_email(self, django_client, setup_instance, saml_config):
        subject = "stable-directory-object-123"
        persistent = "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"
        relay_token, request_id, _ = initiate(django_client)
        first = post_acs(
            django_client,
            build_response(
                request_id,
                email="original@hangar.test",
                name_id=subject,
                name_id_format=persistent,
            ),
            relay_token,
        )
        assert error_code_of(first) is None
        bound = User.objects.get(email="original@hangar.test")
        victim = User.objects.create(email="victim@hangar.test", username="victim")

        second_relay, second_request_id, _ = initiate(django_client)
        second = post_acs(
            django_client,
            build_response(
                second_request_id,
                email=victim.email,
                name_id=subject,
                name_id_format=persistent,
            ),
            second_relay,
        )

        assert error_code_of(second) is None
        assert django_client.session.get("_auth_user_id") == str(bound.id)

    @pytest.mark.django_db
    def test_transient_name_id_is_rejected(self, django_client, setup_instance, saml_config):
        relay_token, request_id, _ = initiate(django_client)
        response = post_acs(
            django_client,
            build_response(
                request_id,
                name_id="transient-123",
                name_id_format="urn:oasis:names:tc:SAML:2.0:nameid-format:transient",
            ),
            relay_token,
        )
        assert error_code_of(response) == EXT_AUTHENTICATION_ERROR_CODES["INVALID_SAML_RESPONSE"]
        assert not User.objects.filter(email="saml-user@hangar.test").exists()
