# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import logging
from urllib.parse import urlencode, quote

import requests
from django.core.cache import cache
from django.utils import timezone

from plane.authentication.utils.outbound import TLSPolicy, fetch_validated
from plane.ext.capacity.crypto import decrypt_value
from plane.ext.models import GoogleCalendarCredential

logger = logging.getLogger(__name__)
# Every listing below already caps the items it will accept. That bounds the
# work but not the conversation: a page carrying no items and a next-page
# token would be followed forever, because neither counter moves. The peer is
# the pinned Google origin rather than anything hostile, so this is a
# liveness bound, not a security control -- but a worker wedged in a loop that
# holds a calendar's lease is indistinguishable from one that has crashed.
MAX_PAGES = 64
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

    def revoke(self, credential: GoogleCalendarCredential) -> None:
        refresh_token = decrypt_value(credential.encrypted_refresh_token, credential.encryption_key_id)
        try:
            _request(
                "POST",
                "https://oauth2.googleapis.com/revoke",
                origin=GOOGLE_TOKEN_ORIGIN,
                data={"token": refresh_token},
                max_bytes=64 * 1024,
            )
        except requests.HTTPError as exc:
            # Google returns 400 when a token is already invalid. The desired
            # disconnected state has therefore already been reached.
            if "HTTP 400" not in str(exc):
                raise GoogleCalendarError("revocation_failed") from exc
        except requests.RequestException as exc:
            raise GoogleCalendarError("revocation_failed") from exc

    def _authorized_json(self, credential, method, url, *, json_body=None, max_bytes=1024 * 1024, expect_json=True):
        """A Google API call, with one token refresh on 401.

        `expect_json=False` exists for the calls that succeed with no body at
        all. Deleting an event answers `204 No Content`, and parsing that as
        JSON raises -- which this method would report as `provider_unavailable`,
        so a delete that worked would be retried forever against an event that
        is already gone.
        """
        for attempt in range(2):
            token = self.access_token(credential, force=attempt == 1)
            try:
                response = _request(
                    method,
                    url,
                    origin=GOOGLE_API_ORIGIN,
                    json_body=json_body,
                    headers={"Authorization": f"Bearer {token}"},
                    max_bytes=max_bytes,
                )
                payload = response.json() if expect_json and response.body else {}
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
                # The write paths act on these differently: a conflict means
                # the event we were about to create already exists under our own
                # identifier, and a missing one means a delete has nothing left
                # to do. Collapsing them into `provider_error` would turn both
                # into retries that can never succeed.
                message = str(exc)
                if "HTTP 429" in message:
                    code = "rate_limited"
                elif "HTTP 409" in message:
                    code = "already_exists"
                elif "HTTP 404" in message:
                    code = "not_found"
                elif "HTTP 410" in message:
                    code = "gone"
                else:
                    code = "provider_error"
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
        calendars, page_token, pages = [], None, 0
        while True:
            pages += 1
            if pages > MAX_PAGES:
                raise GoogleCalendarError("calendar_list_too_large")
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
                    "timezone": item.get("timeZone"),
                }
                for item in items
                if isinstance(item, dict) and item.get("id")
            )
            page_token = payload.get("nextPageToken")
            if not page_token:
                from plane.ext.capacity.timezones import remember_primary_timezone

                remember_primary_timezone(credential, calendars)
                return calendars

    # Three reads, three field masks, one loop. The masks are the whole point of
    # this subsystem's privacy story, so they sit next to each other where a
    # reviewer can compare them, rather than in three near-identical methods
    # where one of them quietly grows a field.
    _AVAILABILITY_FIELDS = "nextPageToken,timeZone,items(id,iCalUID,status,start,end,originalStartTime)"
    _RULE_CALENDAR_FIELDS = (
        "nextPageToken,timeZone,items(id,iCalUID,status,summary,updated,start,end,"
        "originalStartTime,extendedProperties/private)"
    )
    _OWN_CALENDAR_FIELDS = (
        "nextPageToken,timeZone,items(id,iCalUID,status,updated,start,end,originalStartTime,"
        "attendees(email,responseStatus),attendeesOmitted)"
    )

    def _paged_events(self, credential, calendar_id, *, fields, time_min, time_max, updated_min=None):
        """Every event page for one calendar and window, under one field mask.

        `updated_min` turns the read incremental, and forces `showDeleted`: a
        cancellation is precisely an event whose only recent change is that it
        stopped existing, and a caller asking for changes has to see it.
        """
        events, page_token, pages = [], None, 0
        while True:
            pages += 1
            if pages > MAX_PAGES:
                raise GoogleCalendarError("events_window_too_large")
            query = {
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "showDeleted": "true" if updated_min else "false",
                "maxResults": 250,
                "fields": fields,
            }
            if updated_min:
                query["updatedMin"] = updated_min
            if page_token:
                query["pageToken"] = page_token
            payload = self._authorized_json(
                credential,
                "GET",
                (
                    f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events"
                    f"?{urlencode(query)}"
                ),
            )
            if not isinstance(payload, dict) or not isinstance(payload.get("items", []), list):
                raise GoogleCalendarError("invalid_events_response")
            items = payload.get("items", [])
            if len(events) + len(items) > 2000:
                raise GoogleCalendarError("events_window_too_large")
            for item in items:
                if not isinstance(item, dict):
                    raise GoogleCalendarError("invalid_events_response")
                events.append({**item, "calendar_timezone": payload.get("timeZone", "UTC")})
            page_token = payload.get("nextPageToken")
            if not page_token:
                return events

    def list_events(self, credential, calendar_id, *, time_min, time_max):
        """Times only. Kept for callers that must never see event content."""
        return self._paged_events(
            credential,
            calendar_id,
            fields=self._AVAILABILITY_FIELDS,
            time_min=time_min,
            time_max=time_max,
        )

    def list_training_events(self, credential, calendar_id, *, time_min, time_max, updated_min=None) -> list[dict]:
        """Read a rule's calendar: what trainings exist, when, and called what.

        Titles are requested here and nowhere else. It is safe precisely because
        of which calendar this is -- a rule names the calendar the organization
        keeps its trainings on, so every title on it is a training title. The
        same mask pointed at somebody's own calendar would be reading their
        private life, which is why `list_own_training_responses` exists and does
        not ask for `summary`.

        Attendees are deliberately absent: a calendar whose owner hides the
        guest list returns none, so building recognition on them means
        recognizing almost nothing. Membership comes from the trainer's own copy
        instead.
        """
        return self._paged_events(
            credential,
            calendar_id,
            fields=self._RULE_CALENDAR_FIELDS,
            time_min=time_min,
            time_max=time_max,
            updated_min=updated_min,
        )

    def insert_event(self, credential, calendar_id, event: dict, *, send_updates="all") -> dict:
        """Create one event on a calendar, with the identifier we chose.

        Supplying our own `id` is what makes this idempotent: a redelivered
        Celery message, or a retry after a response we never saw, lands on the
        same identifier and Google answers `409` instead of creating a second
        event. The caller treats that conflict as success and reconciles.
        """
        query = urlencode({"sendUpdates": send_updates, "conferenceDataVersion": 0})
        return self._authorized_json(
            credential,
            "POST",
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events?{query}",
            json_body=event,
        )

    def update_event(self, credential, calendar_id, event_id: str, event: dict, *, send_updates="all") -> dict:
        query = urlencode({"sendUpdates": send_updates})
        return self._authorized_json(
            credential,
            "PUT",
            (
                f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}"
                f"/events/{quote(event_id, safe='')}?{query}"
            ),
            json_body=event,
        )

    def delete_event(self, credential, calendar_id, event_id: str, *, send_updates="all") -> None:
        """Remove an event. A `404` or `410` means it is already gone, which is the goal."""
        query = urlencode({"sendUpdates": send_updates})
        try:
            self._authorized_json(
                credential,
                "DELETE",
                (
                    f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}"
                    f"/events/{quote(event_id, safe='')}?{query}"
                ),
                expect_json=False,
            )
        except GoogleCalendarError as exc:
            if exc.code in ("not_found", "gone"):
                return
            raise

    def list_own_training_responses(self, credential, *, time_min, time_max, updated_min=None) -> list[dict]:
        """Read a trainer's own calendar for identity and answer, never content.

        This is the half of recognition the rule's calendar cannot supply. An
        organizer who hides the guest list hides it from the API too, so the
        only place a trainer's involvement is legible is their own copy of the
        invitation, where they are always their own attendee.

        The mask asks for no `summary` and no `description`, so the titles of
        this person's private meetings are not merely discarded -- they are
        never sent. That is a stronger statement than filtering, and it is the
        reason this read is acceptable at all.
        """
        return self._paged_events(
            credential,
            "primary",
            fields=self._OWN_CALENDAR_FIELDS,
            time_min=time_min,
            time_max=time_max,
            updated_min=updated_min,
        )

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
