# Hangar — fork maintenance guide

Hangar is a fork of [makeplane/plane](https://github.com/makeplane/plane) (AGPL-3.0) being
developed to add features on top of the open-source core: SSO (OIDC + SAML 2.0), Epics,
custom issue types with custom properties, and time tracking (worklogs).

The official fork logo is stored at [`hangar-logo.png`](hangar-logo.png). Keep its
name and appearance consistent in project documentation and release materials.

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

## Core-touch ledger

Every fork edit to an upstream-owned file is listed here. Target: fewer than 25 entries.
New-file-only additions (routes, admin pages) are listed for completeness but carry no
merge-conflict risk.

| #   | File                                                           | Phase | Nature                                                                                             |
| --- | -------------------------------------------------------------- | ----- | -------------------------------------------------------------------------------------------------- |
| 1   | `apps/api/plane/settings/common.py`                            | 0     | +1 line: `plane.ext` in `INSTALLED_APPS`                                                           |
| 2   | `apps/api/plane/urls.py`                                       | 0     | +2 lines: `include("plane.ext.urls")`, `include("plane.ext.auth_urls")`                            |
| 3   | `docker-compose-test.yml`                                      | 0     | +1 env var: raise `AUTHENTICATION_RATE_LIMIT` so the full suite passes from one IP (upstreamable)  |
| 4   | `apps/api/plane/utils/instance_config_variables/extended.py`   | 1     | designated empty hook — filled with OIDC config vars (incl. env-derived `IS_OIDC_ENABLED` default) |
| 5   | `apps/api/plane/license/api/views/instance.py`                 | 1     | append-only: `is_oidc_enabled` / `oidc_provider_name` in the public config payload                 |
| 6   | `packages/types/src/instance/auth.ts`, `base.ts`, `auth-ee.ts` | 1     | append OIDC authentication mode, configuration, and public instance types                          |
| 7   | `packages/constants/src/auth/extended.ts`                      | 1     | designated empty hook — add the OIDC login-medium label                                            |
| 8   | `apps/web/core/hooks/oauth/extended.tsx`                       | 1     | designated empty hook — return the OIDC sign-in option                                             |
| 9   | `apps/admin/hooks/oauth/index.ts`, `apps/admin/app/routes.ts`  | 1     | append the OIDC authentication mode and admin configuration route                                  |

Planned (added when the phase lands):

| File                                                                       | Phase | Nature                                                        |
| -------------------------------------------------------------------------- | ----- | ------------------------------------------------------------- |
| `apps/api/Dockerfile.api`, `apps/api/requirements.txt`                     | 1     | xmlsec build deps; include `requirements/ext.txt` (SAML only) |
| `apps/api/plane/license/api/views/instance.py`                             | 1     | append `is_saml_enabled` flag (SAML PR)                       |
| `apps/api/plane/bgtasks/issue_activities_task.py`                          | 3, 4  | append mapper entries (`track_type`, worklog activities)      |
| `apps/api/plane/utils/grouper.py`, `apps/api/plane/utils/issue_filters.py` | 3     | append `type_id` group-by / filter keys                       |
| `apps/web/app/.../epics/`, settings `issue-types/` route folders           | 2, 3  | new files only                                                |
| `packages/i18n/src/locales/*`                                              | all   | append-only strings                                           |
