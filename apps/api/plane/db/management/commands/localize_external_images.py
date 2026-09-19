# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Take images on other hosts out of stored profile, cover and logo fields.

Images are only ever this instance's own, and the frontends'
Content-Security-Policy allows no other image host
(docs/content-security-policy.md). Rows written before that can still point
at one: a profile picture left on the identity provider because it was never
copied, an Unsplash cover, a workspace logo linked from elsewhere. The browser
refuses to load them, so they show as broken.

    python manage.py localize_external_images            # report only, writes nothing
    python manage.py localize_external_images --apply    # fix the affected rows

A profile picture is copied into object storage the way sign-in copies one
(same size and type limits, same guarded fetch), and cleared if that fails; a
cleared picture falls back to the initials. Covers and logos are cleared, and
fall back to the default cover or the initials.

An image is *external* when its URL is absolute and its origin is not this
instance's (WEB_URL, APP_BASE_URL, ADMIN_BASE_URL, SPACE_BASE_URL) nor its
object storage's (AWS_S3_ENDPOINT_URL, AWS_S3_PUBLIC_ENDPOINT_URL). Add other
origins that are yours with --local-origin.
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand

from plane.db.models import Account, Project, User, Workspace

# (model, url field, asset field) whose external URL is cleared.
CLEARED = [
    (User, "cover_image", "cover_image_asset"),
    (Project, "cover_image", "cover_image_asset"),
    (Workspace, "logo", "logo_asset"),
]


def _origin(url):
    parts = urlsplit(url or "")
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}".lower()


def configured_local_origins():
    origins = set()
    for name in (
        "WEB_URL",
        "APP_BASE_URL",
        "ADMIN_BASE_URL",
        "SPACE_BASE_URL",
        "AWS_S3_ENDPOINT_URL",
        "AWS_S3_PUBLIC_ENDPOINT_URL",
    ):
        origin = _origin(getattr(settings, name, None))
        if origin:
            origins.add(origin)
    return origins


def is_external(url, local_origins):
    """An absolute http(s) URL on an origin that is not this instance's."""
    origin = _origin(url)
    return origin is not None and origin not in local_origins


class Command(BaseCommand):
    help = "Copy or clear profile pictures, covers and logos stored as URLs on other hosts."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the changes; without it nothing is written.")
        parser.add_argument(
            "--local-origin",
            action="append",
            default=[],
            metavar="ORIGIN",
            help="Another origin whose images are this instance's own (repeatable), e.g. https://files.example.com.",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        local_origins = configured_local_origins()
        for extra in options["local_origin"]:
            origin = _origin(extra)
            if origin is None:
                self.stderr.write(f"Ignoring --local-origin {extra!r}: not an http(s) origin.")
                continue
            local_origins.add(origin)
        self.stdout.write(f"Local origins: {', '.join(sorted(local_origins)) or '(none configured)'}")

        self._avatars(apply, local_origins)
        for model, field, asset_field in CLEARED:
            self._clear(model, field, asset_field, apply, local_origins)

        if not apply:
            self.stdout.write("Report only. Run again with --apply to write the changes.")

    def _avatars(self, apply, local_origins):
        users = [
            user
            for user in User.objects.filter(avatar_asset__isnull=True).exclude(avatar__isnull=True).exclude(avatar="")
            if is_external(user.avatar, local_origins)
        ]
        copied = cleared = 0
        for user in users:
            if not apply:
                continue
            if self._copy_avatar(user):
                copied += 1
            else:
                User.objects.filter(pk=user.pk, avatar=user.avatar, avatar_asset__isnull=True).update(avatar="")
                cleared += 1
        if apply:
            self.stdout.write(f"User.avatar: {len(users)} external, {copied} copied to storage, {cleared} cleared")
        else:
            self.stdout.write(f"User.avatar: {len(users)} external, would be copied to storage (or cleared)")

    @staticmethod
    def _copy_avatar(user):
        # The sign-in path's own copy, run in-process: it fetches through the
        # SSRF-guarded client and sets avatar_asset only if the avatar is
        # still the one it fetched.
        from plane.bgtasks.file_asset_task import download_oauth_avatar

        account = Account.objects.filter(user=user).order_by("created_at").first()
        try:
            download_oauth_avatar(
                avatar_url=user.avatar,
                user_id=str(user.pk),
                provider=account.provider if account else "unknown",
            )
        except Exception:  # noqa: BLE001 -- one failed download must not stop the rest
            return False
        return User.objects.filter(pk=user.pk, avatar_asset__isnull=False).exists()

    def _clear(self, model, field, asset_field, apply, local_origins):
        ids = [
            pk
            for pk, url in model.objects.filter(**{f"{asset_field}__isnull": True})
            .exclude(**{f"{field}__isnull": True})
            .exclude(**{field: ""})
            .values_list("pk", field)
            if is_external(url, local_origins)
        ]
        if apply and ids:
            model.objects.filter(pk__in=ids).update(**{field: None})
        verb = "cleared" if apply else "would be cleared"
        self.stdout.write(f"{model.__name__}.{field}: {len(ids)} external, {verb}")
