# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Enumerate routes and the authorization mechanism each one relies on.

Authorization in this codebase is enforced four different ways: DRF
``permission_classes``, the ``@allow_permission`` decorator, filtering inside
``get_queryset``, and checks made by a service the view delegates to. No single
grep can prove coverage across all four, and the queryset-filtering variety is
indistinguishable from an unprotected view by inspection — a missing
``.filter()`` looks exactly like correct code.

This module resolves what is actually wired into the URL conf, so the tests
built on it reason about the deployed surface rather than about what a search
happened to match.
"""

import inspect
from dataclasses import dataclass, field

from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver
from rest_framework.permissions import AllowAny, IsAuthenticated

HANDLER_NAMES = ("get", "post", "put", "patch", "delete", "head", "options")

# How a route establishes that the caller may act on the target.
MECHANISM_PERMISSION_CLASS = "permission_class"
MECHANISM_DECORATOR = "allow_permission"
MECHANISM_QUERYSET = "queryset_filter"
MECHANISM_SERVICE = "service_layer"
MECHANISM_PUBLIC = "public"
MECHANISM_NONE = "none"

# Membership-bearing lookups a get_queryset must go through for a view to
# count as enforcing authorization in its queryset.
MEMBERSHIP_MARKERS = (
    "workspace_member__member",
    "project_projectmember__member",
    "workspace__workspace_member__member",
    "project__project_projectmember__member",
    "member=self.request.user",
    "member=request.user",
)

# Calls that hand the authorization decision to a service layer.
SERVICE_MARKERS = ("resolve_for_admin", "actor=request.user", "actor=self.request.user")


@dataclass
class RouteRecord:
    pattern: str
    name: str
    view_class: type | None
    view_module: str
    handlers: tuple[str, ...]
    permission_classes: tuple[str, ...]
    mechanisms: set = field(default_factory=set)
    kwargs_required: tuple[str, ...] = ()

    @property
    def is_public(self):
        return MECHANISM_PUBLIC in self.mechanisms

    @property
    def is_unclassified(self):
        return self.mechanisms == {MECHANISM_NONE} or not self.mechanisms

    def describe(self):
        return f"{self.pattern} [{self.view_module}.{getattr(self.view_class, '__name__', '?')}]"


def _view_class(callback):
    return getattr(callback, "view_class", None) or getattr(callback, "cls", None)


def _source_of(view_class):
    try:
        return inspect.getsource(view_class)
    except (OSError, TypeError):
        return ""


def _classify(view_class, permission_names, source):
    mechanisms = set()

    if "AllowAny" in permission_names:
        mechanisms.add(MECHANISM_PUBLIC)

    # Anything narrower than bare IsAuthenticated is a real gate.
    if any(name not in {"IsAuthenticated", "AllowAny"} for name in permission_names):
        mechanisms.add(MECHANISM_PERMISSION_CLASS)

    if "allow_permission" in source:
        mechanisms.add(MECHANISM_DECORATOR)

    if "get_queryset" in source and any(marker in source for marker in MEMBERSHIP_MARKERS):
        mechanisms.add(MECHANISM_QUERYSET)

    if any(marker in source for marker in SERVICE_MARKERS):
        mechanisms.add(MECHANISM_SERVICE)

    return mechanisms or {MECHANISM_NONE}


def _walk(resolver, prefix=""):
    for entry in resolver.url_patterns:
        route = prefix + str(entry.pattern)
        if isinstance(entry, URLResolver):
            yield from _walk(entry, route)
        elif isinstance(entry, URLPattern):
            yield route, entry


def collect_routes(urlconf=None):
    """Return a RouteRecord for every route in the URL conf."""
    records = []
    for route, entry in _walk(get_resolver(urlconf)):
        view_class = _view_class(entry.callback)
        if view_class is None:
            continue

        permission_classes = tuple(
            getattr(permission, "__name__", str(permission))
            for permission in (getattr(view_class, "permission_classes", None) or [])
        )
        source = _source_of(view_class)
        handlers = tuple(name for name in HANDLER_NAMES if hasattr(view_class, name))

        records.append(
            RouteRecord(
                pattern=route,
                name=entry.name or "",
                view_class=view_class,
                view_module=view_class.__module__,
                handlers=handlers,
                permission_classes=permission_classes,
                mechanisms=_classify(view_class, permission_classes, source),
                kwargs_required=tuple(entry.pattern.regex.groupindex.keys()),
            )
        )
    return records


def workspace_scoped(records):
    """Routes addressing a specific workspace, which a non-member must not reach."""
    return [record for record in records if "slug" in record.kwargs_required and not record.is_public]


__all__ = [
    "AllowAny",
    "IsAuthenticated",
    "MECHANISM_DECORATOR",
    "MECHANISM_NONE",
    "MECHANISM_PERMISSION_CLASS",
    "MECHANISM_PUBLIC",
    "MECHANISM_QUERYSET",
    "MECHANISM_SERVICE",
    "RouteRecord",
    "collect_routes",
    "workspace_scoped",
]
