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

| #   | File                                                                                                                                              | Phase | Nature                                                                                              |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | --------------------------------------------------------------------------------------------------- |
| 1   | `apps/api/plane/settings/common.py`                                                                                                               | 0     | +1 line: `plane.ext` in `INSTALLED_APPS`                                                            |
| 2   | `apps/api/plane/urls.py`                                                                                                                          | 0     | +2 lines: `include("plane.ext.urls")`, `include("plane.ext.auth_urls")`                             |
| 3   | `docker-compose-test.yml`                                                                                                                         | 0     | +1 env var: raise `AUTHENTICATION_RATE_LIMIT` so the full suite passes from one IP (upstreamable)   |
| 4   | `apps/api/plane/utils/instance_config_variables/extended.py`                                                                                      | 1     | designated empty hook — filled with OIDC + SAML config vars (including env-derived enable defaults) |
| 5   | `apps/api/plane/license/api/views/instance.py`                                                                                                    | 1     | append-only: OIDC and SAML enable flags and provider names in the public config payload             |
| 6   | `packages/types/src/instance/auth.ts`, `base.ts`, `auth-ee.ts`                                                                                    | 1     | append OIDC and SAML authentication modes, configuration, and public instance types                 |
| 7   | `packages/constants/src/auth/extended.ts`                                                                                                         | 1     | designated empty hook — add OIDC and SAML login-medium labels                                       |
| 8   | `apps/web/core/hooks/oauth/extended.tsx`                                                                                                          | 1     | designated empty hook — return OIDC and SAML sign-in options                                        |
| 9   | `apps/admin/hooks/oauth/index.ts`, `apps/admin/app/routes.ts`                                                                                     | 1     | append OIDC and SAML authentication modes and admin configuration routes                            |
| 10  | `apps/api/Dockerfile.api`, `Dockerfile.dev`                                                                                                       | 1     | add the build packages required by the xmlsec binding                                               |
| 11  | `apps/api/requirements/base.txt`                                                                                                                  | 1     | include `requirements/ext.txt`, which isolates fork-only Python dependencies                        |
| 12  | `apps/api/plane/db/models/issue.py`                                                                                                               | 2     | exclude epics from the upstream work-item manager so they remain on dedicated Epic surfaces         |
| 13  | `apps/web/core/store/issue/project/`, `issue/helpers/base-issues.store.ts`                                                                        | 2     | parameterize shared issue/filter stores so the Epic overlay uses isolated services and state        |
| 14  | `packages/types/src/settings.ts`, `packages/constants/src/settings/project.ts`, `apps/web/core/components/settings/project/sidebar/item-icon.tsx` | 3     | append the `work_item_types` project-settings tab, group entry, and icon                            |
| 15  | `packages/i18n/src/locales/*/common.json`                                                                                                         | 3     | append the localized `common.work_item_types` label                                                 |
| 16  | `apps/api/plane/utils/issue_filters.py`                                                                                                           | 3     | append the UUID-validated `issue_type` filter mapped to `type_id__in`                               |
| 17  | `apps/api/plane/bgtasks/issue_activities_task.py`                                                                                                 | 3, 4  | append the `track_type` field tracker plus worklog create/update/delete activity handlers           |
| 18  | `packages/constants/src/issue/filter.ts`                                                                                                          | 4     | append the `WORKLOG` activity filter type and option; retain the lint-safe callback parameter rename |
| 19  | `packages/types/src/project/projects.ts`                                                                                                          | 4     | append `is_time_tracking_enabled` to `IProject`; the flag already exists on the server model         |

Planned (added when the phase lands):

| File                          | Phase | Nature              |
| ----------------------------- | ----- | ------------------- |
| `packages/i18n/src/locales/*` | all   | append-only strings |
