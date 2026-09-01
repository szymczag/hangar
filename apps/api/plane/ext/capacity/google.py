from __future__ import annotations

import logging
from urllib.parse import urlencode

import requests
from django.core.cache import cache
from django.utils import timezone

from plane.authentication.utils.outbound import TLSPolicy, fetch_validated
from plane.ext.capacity.crypto import decrypt_value
from plane.ext.models import GoogleCalendarCredential

logger = logging.getLogger(__name__)
GOOGLE_API_ORIGIN = ("https", "www.googleapis.com", 443)
GOOGLE_TOKEN_ORIGIN = ("https", "oauth2.googleapis.com", 443)


class GoogleCalendarError(RuntimeError):
    def __init__(self, code: str, *, reauthorization_required: bool = False):
        self.code = code
        self.reauthorization_required = reauthorization_required
        super().__init__(code)


def _request(method, url, *, origin, data=None, json_body=None, headers=None, max_bytes=1024 * 1024):
    return fetch_validated(
        method,
        url,
        required_origin=origin,
        data=data,
        json_body=json_body,
        headers=headers,
        timeout=10,
        max_response_bytes=max_bytes,
        tls_policy=TLSPolicy.MIN_TLS12,
    )


class GoogleCalendarClient:
    def __init__(self, *, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    def exchange_code(self, *, code: str, redirect_uri: str, code_verifier: str) -> dict:
        return self._token_request(
            {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            }
        )

    def _token_request(self, data: dict) -> dict:
        try:
            payload = _request(
                "POST",
                "https://oauth2.googleapis.com/token",
                origin=GOOGLE_TOKEN_ORIGIN,
                data=data,
            ).json()
        except (requests.RequestException, ValueError, UnicodeDecodeError) as exc:
            reauth = "invalid_grant" in str(exc)
            raise GoogleCalendarError("token_exchange_failed", reauthorization_required=reauth) from exc
        if not isinstance(payload, dict) or not payload.get("access_token"):
            raise GoogleCalendarError("token_exchange_failed")
        return payload

    def access_token(self, credential: GoogleCalendarCredential, *, force=False) -> str:
        cache_key = f"gcal:access:{credential.id}"
        if not force:
            cached = cache.get(cache_key)
            if isinstance(cached, str) and cached:
                return cached
        refresh_token = decrypt_value(credential.encrypted_refresh_token, credential.encryption_key_id)
        try:
            payload = self._token_request(
                {
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                }
            )
        except GoogleCalendarError as exc:
            if exc.reauthorization_required:
                GoogleCalendarCredential.objects.filter(pk=credential.pk).update(
                    status=GoogleCalendarCredential.Status.REAUTHORIZATION_REQUIRED,
                    last_error_code="invalid_grant",
                )
            raise
        token = payload["access_token"]
        ttl = max(60, min(int(payload.get("expires_in", 3600)) - 60, 3540))
        cache.set(cache_key, token, ttl)
        return token

    def _authorized_json(self, credential, method, url, *, json_body=None, max_bytes=1024 * 1024):
        for attempt in range(2):
            token = self.access_token(credential, force=attempt == 1)
            try:
                payload = _request(
                    method,
                    url,
                    origin=GOOGLE_API_ORIGIN,
                    json_body=json_body,
                    headers={"Authorization": f"Bearer {token}"},
                    max_bytes=max_bytes,
                ).json()
                GoogleCalendarCredential.objects.filter(pk=credential.pk).update(
                    status=GoogleCalendarCredential.Status.CONNECTED,
                    last_successful_at=timezone.now(),
                    last_error_code="",
                )
                return payload
            except requests.HTTPError as exc:
                if "HTTP 401" in str(exc) and attempt == 0:
                    cache.delete(f"gcal:access:{credential.id}")
                    continue
                code = "rate_limited" if "HTTP 429" in str(exc) else "provider_error"
                raise GoogleCalendarError(code) from exc
            except (requests.RequestException, ValueError, UnicodeDecodeError) as exc:
                raise GoogleCalendarError("provider_unavailable") from exc
        raise GoogleCalendarError("reauthorization_required", reauthorization_required=True)

    def userinfo(self, access_token: str) -> dict:
        try:
            payload = _request(
                "GET",
                "https://www.googleapis.com/oauth2/v2/userinfo",
                origin=GOOGLE_API_ORIGIN,
                headers={"Authorization": f"Bearer {access_token}"},
            ).json()
        except (requests.RequestException, ValueError, UnicodeDecodeError) as exc:
            raise GoogleCalendarError("userinfo_failed") from exc
        if not isinstance(payload, dict) or not payload.get("id") or not payload.get("verified_email"):
            raise GoogleCalendarError("userinfo_failed")
        return payload

    def list_calendars(self, credential: GoogleCalendarCredential) -> list[dict]:
        calendars, page_token = [], None
        while True:
            query = {"maxResults": 250, "minAccessRole": "freeBusyReader"}
            if page_token:
                query["pageToken"] = page_token
            payload = self._authorized_json(
                credential,
                "GET",
                f"https://www.googleapis.com/calendar/v3/users/me/calendarList?{urlencode(query)}",
            )
            items = payload.get("items", []) if isinstance(payload, dict) else []
            if not isinstance(items, list) or len(calendars) + len(items) > 500:
                raise GoogleCalendarError("calendar_list_too_large")
            calendars.extend(
                {
                    "id": item.get("id"),
                    "summary": str(item.get("summary") or "Calendar")[:255],
                    "primary": bool(item.get("primary")),
                    "access_role": item.get("accessRole"),
                }
                for item in items
                if isinstance(item, dict) and item.get("id")
            )
            page_token = payload.get("nextPageToken")
            if not page_token:
                return calendars

    def freebusy(self, credential, calendar_ids: list[str], *, time_min: str, time_max: str) -> list[dict]:
        busy = []
        for offset in range(0, len(calendar_ids), 50):
            batch = calendar_ids[offset : offset + 50]
            payload = self._authorized_json(
                credential,
                "POST",
                "https://www.googleapis.com/calendar/v3/freeBusy",
                json_body={
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "timeZone": "UTC",
                    "items": [{"id": i} for i in batch],
                },
            )
            calendars = payload.get("calendars", {}) if isinstance(payload, dict) else {}
            for calendar_id in batch:
                result = calendars.get(calendar_id, {})
                if result.get("errors"):
                    raise GoogleCalendarError("calendar_unavailable")
                busy.extend(result.get("busy", []))
        return busy
