# Hangar — fork maintenance guide

Hangar is a fork of [makeplane/plane](https://github.com/makeplane/plane) (AGPL-3.0) that
implements additional features on top of the open-source core: SSO (OIDC + SAML 2.0),
Epics, custom issue types with custom properties, and time tracking (worklogs).

All fork code is isolated so upstream syncs stay cheap:

- **Backend** lives in the dedicated Django app `apps/api/plane/ext/` (own models,
  migrations, serializers, views, URLs). Upstream never touches this path.
- **Frontend** lives in the `apps/web/ce/` overlay, resolved via the `@/plane-web/*`
  alias (`apps/web/tsconfig.json`). Filling existing CE stubs requires no core edits.
- Everything else is an **append-only** edit to a core file, tracked in the ledger below.

## Syncing with upstream

```sh
git remote add upstream https://github.com/makeplane/plane.git   # once
git fetch upstream
git merge upstream/preview       # merge, never rebase — fork history is published
```

After every sync, walk the ledger below and re-verify each touchpoint still applies.

## Commit conventions

Conventional commits (`type(scope): message`). No attribution trailers.

## Licensing & copyright headers

The whole work is AGPL-3.0-only. Two header rules:

- **Upstream files (including ones we modify):** keep the original
  `Copyright (c) 2023-present Plane Software, Inc. and contributors` notice
  intact — AGPL requires preserving upstream notices, and removing them would
  violate the license.
- **Fork-authored files (new files under `plane/ext/`, new admin pages, new
  tests, etc.):** use
  `Copyright (c) 2026-present Maciej Szymczak and contributors` with the same
  `SPDX-License-Identifier: AGPL-3.0-only` tag.

"Plane" appearing in retained copyright notices and in module paths is factual
attribution / internal naming, not trademark use; product branding is what must
avoid the Plane name (see the README notice).

## Core-touch ledger

Every fork edit to an upstream-owned file is listed here. Target: fewer than 25 entries.
New-file-only additions (routes, admin pages) are listed for completeness but carry no
merge-conflict risk.

| # | File | Phase | Nature |
|---|------|-------|--------|
| 1 | `apps/api/plane/settings/common.py` | 0 | +1 line: `plane.ext` in `INSTALLED_APPS` |
| 2 | `apps/api/plane/urls.py` | 0 | +2 lines: `include("plane.ext.urls")`, `include("plane.ext.auth_urls")` |
| 3 | `docker-compose-test.yml` | 0 | +1 env var: raise `AUTHENTICATION_RATE_LIMIT` so the full suite passes from one IP (upstreamable) |
| 4 | `apps/api/plane/utils/instance_config_variables/extended.py` | 1 | designated empty hook — filled with OIDC + SAML config vars (incl. env-derived enable defaults) |
| 5 | `apps/api/plane/license/api/views/instance.py` | 1 | append-only: `is_oidc_enabled` / `oidc_provider_name` / `is_saml_enabled` / `saml_provider_name` in the public config payload |
| 6 | `packages/types/src/instance/auth.ts`, `base.ts`, `auth-ee.ts` | 1 | `auth-ee.ts` is the designated `never` hook — filled; config-key unions and instance flags appended |
| 7 | `apps/web/core/hooks/oauth/extended.tsx` | 1 | designated empty hook — filled with extended sign-in options |
| 8 | `apps/admin/hooks/oauth/index.ts`, `apps/admin/app/routes.ts` | 1 | append extended authentication modes + admin route |
| 9 | `apps/api/Dockerfile.api`, `Dockerfile.dev` | 1 | +3 build packages (`xmlsec-dev`, `libxml2-dev`, `libxslt-dev`) for the xmlsec binding |
| 10 | `apps/api/requirements/base.txt` | 1 | +1 include: `-r ext.txt` (fork requirements live in `requirements/ext.txt`) |
| 11 | `apps/api/plane/db/models/issue.py` | 2 | +1 exclude in `IssueManager`: epics (`type__is_epic=True`) stay out of work-item querysets |

Planned (added when the phase lands):

| File | Phase | Nature |
|------|-------|--------|
| `apps/api/plane/bgtasks/issue_activities_task.py` | 3, 4 | append mapper entries (`track_type`, worklog activities) |
| `apps/api/plane/utils/grouper.py`, `apps/api/plane/utils/issue_filters.py` | 3 | append `type_id` group-by / filter keys |
| `apps/web/app/.../epics/`, settings `issue-types/` route folders | 2, 3 | new files only |
| `packages/i18n/src/locales/*` | all | append-only strings |
