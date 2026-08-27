# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Whether this instance allows anything to be visible beyond its members.

`Page.access` is 0 for public and 1 for private. `IssueView.access` is the other
way round. Any code that takes a single "make it private" value and applies it to
both sets the opposite of what it intended for one of them.

So the private value for each is named here, once, and nowhere else. A test
compares each against its model's own choices, because a renumbering upstream
would otherwise turn this file into a way of publishing things quietly.

`Project.network` is deliberately not governed. It decides whether members of a
workspace can discover a project they have not been added to — not whether
outsiders can read it — so forcing it would change how a team navigates without
closing anything that was open.

Publishing to the internet is a separate question with no per-object setting to
force: a deploy board either exists and serves or it does not. It is refused at
the one place every public request passes through.
"""

import os

from plane.license.utils.instance_value import get_configuration_value

# Off by default. Turning it on is an operator's decision, and on an existing
# instance it changes what people can already see.
FORCE_PRIVATE_VISIBILITY_KEY = "FORCE_PRIVATE_VISIBILITY"

# Page.access choices = ((0, "Public"), (1, "Private"))
PAGE_PRIVATE_ACCESS = 1
# IssueView.access choices = ((0, "Private"), (1, "Public")) — the reverse of Page.
VIEW_PRIVATE_ACCESS = 0


def force_private_visibility() -> bool:
    (configured,) = get_configuration_value(
        [
            {
                "key": FORCE_PRIVATE_VISIBILITY_KEY,
                "default": os.environ.get(FORCE_PRIVATE_VISIBILITY_KEY, "0"),
            }
        ]
    )
    return str(configured) == "1"


def apply_private_visibility(*, apps=None) -> dict[str, int]:
    """Bring objects that already exist into line with the policy.

    Enforcing at write time only governs what happens next; anything created
    before the policy was turned on stays as visible as it was. So this exists,
    and it runs when the policy is switched on rather than waiting to be
    remembered.

    One-way on purpose. The previous visibility of each object is not recorded,
    because a table of "what this used to be readable by" is a description of
    what to expose to undo the decision, and an operator turning this on is
    saying they do not want that lying around. Turning the policy back off leaves
    everything private until someone opens it again deliberately.

    Deploy boards are disabled rather than deleted: the row carries the anchor
    that was handed out, and keeping it means the same address cannot later be
    reissued for something else.

    `apps` is the historical registry when called from a migration, and None when
    called from a request or a command.
    """
    registry = apps
    if registry is None:
        from django.apps import apps as django_apps

        registry = django_apps

    Page = registry.get_model("db", "Page")
    IssueView = registry.get_model("db", "IssueView")
    DeployBoard = registry.get_model("db", "DeployBoard")

    return {
        "pages": Page.objects.exclude(access=PAGE_PRIVATE_ACCESS).update(access=PAGE_PRIVATE_ACCESS),
        "views": IssueView.objects.exclude(access=VIEW_PRIVATE_ACCESS).update(access=VIEW_PRIVATE_ACCESS),
        "deploy_boards": DeployBoard.objects.filter(is_disabled=False).update(is_disabled=True),
    }
