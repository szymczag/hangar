# Operate a Hangar Helm release

This guide covers routine verification, upgrades, credential rotation, backup,
restore, rollback decisions, scaling, and removal. Commands use the default
release name `hangar`; adjust them for your installation.

```bash
export RELEASE_NAME=hangar
export NAMESPACE=hangar
```

## Verify a release

Start with Helm and controller state:

```bash
helm --namespace "$NAMESPACE" status "$RELEASE_NAME"
kubectl --namespace "$NAMESPACE" get \
  deployment,statefulset,pod,job,pvc,service,ingress,networkpolicy
kubectl --namespace "$NAMESPACE" rollout status deployment \
  --selector app.kubernetes.io/instance="$RELEASE_NAME" \
  --timeout=5m
```

The migration is a revision-scoped Job. A completed Job is intentionally not a
Ready Pod, so do not wait for every release Pod to report Ready.

```bash
kubectl --namespace "$NAMESPACE" get jobs \
  --selector app.kubernetes.io/instance="$RELEASE_NAME",app.kubernetes.io/component=migrator
```

Inspect the current revision's migration log by substituting its Job name:

```bash
kubectl --namespace "$NAMESPACE" logs job/HANGAR-MIGRATION-JOB
```

Then verify through the public origin:

- HTTP redirects to HTTPS;
- `/`, `/api`, `/live`, `/god-mode`, and `/spaces` reach the intended backend;
- the Live WebSocket performs an HTTP Upgrade;
- authentication and a representative project operation work;
- an uploaded object can be downloaded; and
- internal Services are not reachable outside the cluster.

When `mail.enabled=true`, also verify the dedicated mail worker, one cleartext
account receipt, one encrypted compatibility test, a simulated bounce, the
SNS/SQS feedback path, and both the user and administrator delivery ledgers.
Use [Amazon SES email operations](../aws-ses-email-operations.md) for rollout,
deliverability monitoring, suppression recovery, and incident procedures.

When `todoistImports.enabled=true`, also verify that the `import-worker`
Deployment is Ready, consumes only the `imports` queue, receives the API
ConfigMap and object-storage Secret references, and can complete a synthetic
preview/import/report cycle without exposing the private bucket publicly. Confirm
that one over-limit request returns `429` without creating a job or source.

## Upgrade a release

### Upgrade from `rc.19` to `rc.20`

This release moves the inherited application baseline from Plane `v1.4.0-rc2`
to the exact final `v1.4.0` commit `917b23a6`. It includes Django 5.2.15 and the
final upstream dependency, filtering, avatar, and application fixes. Hangar's
upload-validation migration remains the migration-history anchor.

The release also tightens server-side authorization for analytics, workspace
search, cycle and module mutation, and project deploy-board routes. OAuth login
now uses a provider- and surface-bound, single-use transaction state. Gitea,
OIDC, and SMTP outbound traffic validates and pins resolved destinations; the
Live PDF exporter accepts only bounded raster assets from credential-free
presigned HTTP(S) URLs and refuses redirects.

`rc.20` adds Django migration
`0129_alter_draftissue_assignees_alter_issue_assignees_and_more`. It records the
final upstream relationship metadata for draft issue assignees, issue assignees,
and module members; it does not rewrite existing issue or membership rows.
Existing `rc.19` Helm values and Secret names remain structurally compatible.
There is no Helm resource, RBAC, NetworkPolicy, or persisted-data contract
change.

Before upgrading:

1. take a PostgreSQL backup, prove that it can be restored in isolation, and
   record the current Helm revision and application image digests;
2. confirm the target chart is `0.1.0-rc.20`, its application version is
   `v0.1.0-rc.20`, and its signatures and digests pass the
   [release verification procedure](security.md#verify-release-010-rc20);
3. if Gitea OAuth or SMTP is enabled, review the destination policy in the
   [federated SSO guide](../federated-sso-security.md) or
   [email security model](../email-delivery-and-openpgp.md); private destinations
   require both an application allowlist and the matching narrow
   `networkPolicy.privateEgress` rule;
4. render the existing values against the target chart and verify that only the
   expected release versions and immutable image digests change; and
5. schedule the API, workers, Live service, and all frontends as one coordinated
   Helm revision. Do not mix `rc.19` and `rc.20` application images.

The chart does not currently expose `GITEA_ALLOWED_HOSTS`,
`GITEA_ALLOWED_IPS`, `SMTP_ALLOWED_HOSTS`, `SMTP_ALLOWED_IPS`, or
`SMTP_ALLOWED_PORTS` as Helm values. Public destinations remain usable when
they resolve exclusively to permitted public addresses. A private Gitea or SMTP
destination is outside the supported chart contract for this release; do not
patch generated Deployments by hand to bypass that boundary.

Wait for the revision-scoped migration Job before admitting traffic. OAuth
transactions started before the rollout cannot be resumed; users should restart
the sign-in flow. After the rollout, verify:

- users outside a workspace or project cannot read analytics, search results,
  deploy-board content, or mutate cycles and modules by supplying identifiers;
- GitHub, GitLab, and Gitea callbacks reject missing, stale, replayed,
  cross-provider, and cross-surface transaction state;
- enabled Gitea, OIDC, and SMTP integrations reach only their intended hosts,
  refuse redirects where applicable, and fail closed on blocked address changes;
- SMTP credentials are never sent over a plaintext connection;
- PDF export embeds a valid bounded PNG or JPEG while rejecting redirects,
  unsupported media types, oversized bodies, malformed asset IDs, and excess
  image counts; and
- upload, download, issue editing, Live updates, and a representative workspace
  workflow remain healthy.

`rc.19` is the immediately previous complete publication, but it predates the
security boundaries introduced here. There is no security-equivalent rollback
target. If an emergency availability rollback is unavoidable, disable affected
OAuth, SMTP, analytics, and export surfaces first. Migration `0129` may remain
applied because it does not rewrite application rows; return every component to
`rc.20` as soon as possible.

### Upgrade from `rc.18` to `rc.19`

This release introduces the server-enforced file-upload boundary described in
[secure file uploads](../secure-file-uploads.md). Direct uploads are staged
under server-generated keys and are published only after bounded content,
canonical MIME, size, and ETag validation. Legacy multipart routes apply the
same content and entity-authorization policy. Only objects carrying the current
server-owned validation marker can render inline; other formats are forced to
download.

Asset mutation authorization is now consistent across current, legacy,
duplicate, bulk, completion, delete, and restore paths. Project guests cannot
change a project cover. Server-side object-storage operations always use the
configured internal endpoint, while browser presigning uses the explicit public
endpoint or trusted `WEB_URL`; request `Host` headers never select an outbound
storage destination.

`rc.19` adds Django migration
`0128_fileasset_upload_validation_version`. The migration adds an integer marker
with default `0` and does not rewrite existing objects. Existing `rc.18` Helm
values remain structurally compatible, and there is no Helm values, Secret,
Kubernetes resource, RBAC, or network-policy contract change. The inherited
Plane source remains `v1.4.0-rc2` (`package.json` version `1.4.0`).

Before upgrading:

1. take a PostgreSQL backup, prove that it can be restored in isolation, and
   record the current Helm revision and application image digests;
2. confirm the target package is `0.1.0-rc.19`, its application version is
   `v0.1.0-rc.19`, and its signatures and digests pass the
   [release verification procedure](security.md#verify-release-010-rc19);
3. verify that the internal object-storage endpoint is reachable only from the
   intended workloads, the public endpoint is the browser-facing origin,
   anonymous bucket access is disabled, and neither value is derived from an
   inbound request;
4. render the existing values against the target chart and verify that only the
   expected release versions and immutable image digests change; and
5. schedule the API, task workers, Beat, Live service, and all frontends as one
   coordinated Helm revision.

Wait for the revision-scoped migration Job before admitting traffic. Then run
the legacy public-raster validator from an API container:

```sh
python manage.py revalidate_legacy_static_assets
```

Use `--limit N` for bounded batches and monitor the validated, quarantined, and
retryable counts. A historical avatar, cover, or logo returns `404` until it is
successfully revalidated; do not bypass this behavior by restoring anonymous
bucket reads.

After the rollout, verify:

- a valid JPEG or PNG upload completes, renders inline only in an allowed public
  raster context, and downloads normally as an attachment elsewhere;
- MIME-spoofed, active-content, oversized, replaced, and cross-project uploads
  fail without publishing or associating an object;
- project members and administrators can manage project covers, while project
  guests receive a not-found response on every mutation route;
- the API can perform HEAD, COPY, and DELETE through the internal storage
  endpoint while generated browser URLs use only the configured public origin;
- legacy raster revalidation succeeds for a known-valid object and quarantines
  a deliberately invalid test object; and
- sign-in, workspace/project navigation, Live updates, import jobs, and a
  representative issue workflow remain healthy.

`rc.18` is the immediately previous complete publication, but it predates the
security boundary introduced here. There is no security-equivalent rollback
target among earlier release candidates. If availability recovery requires an
emergency application rollback, disable uploads and isolate object storage
first. The additive validation column may remain in the database; return every
component to `rc.19` as soon as possible. Restore the pre-upgrade backup only
when unrelated writes, corruption, or the incident requires point-in-time
recovery.

### Upgrade from `rc.17` to `rc.18`

This release fixes the stacking contract for every Popper-positioned Headless
UI panel. `rc.17` moved panels into portals to escape clipping ancestors, but
those portals retained local `z-10` or `z-30` layers. Issue peeks and dialogs
use layers through `z-100`, so a panel could be visible while browser hit
testing delivered pointer events to the dialog above it. Priority, label,
module, date, and other field selectors could therefore open without accepting
a selection.

The shared Tailwind layer now assigns every Popper root marked with
`data-popper-placement` to the floating-overlay layer `110`: above all current
dialog and issue-peek layers, but below the notification layer `1000`. This
central contract covers all 33 Popper targets and overrides stale component-local
stacking classes. A repository test verifies that every JSX Popper ref owns its
attributes and that the shared overlay rule and variable cannot be removed
independently.

There is no Django migration and no Helm values, Secret, permission, Kubernetes
resource, or network-policy contract change. The inherited Plane source remains
`v1.4.0-rc2` (`package.json` version `1.4.0`). Existing `rc.17` values are
compatible with the `rc.18` chart. Upgrade the API, workers, Live service, and
frontends together as one Helm revision; mixed application versions are not a
qualified steady state.

Before upgrading:

1. take a PostgreSQL backup, prove that it can be restored in isolation, and
   record the current Helm revision and application image digests;
2. confirm the target package is `0.1.0-rc.18`, its application version is
   `v0.1.0-rc.18`, and its signatures and digests pass the
   [release verification procedure](security.md#verify-release-010-rc18);
3. render the existing values against the target chart and verify that only the
   expected release versions and immutable image digests change; and
4. schedule all Hangar application components as one coordinated rollout.

After the rollout, use a clean browser profile and verify:

- opening and selecting priority, labels, modules, dates, state, estimate,
  member, project, cycle, intake state, onboarding role, and account or
  workspace menu values;
- pointer selection inside an issue peek and every supported dialog size;
- panel placement beside its trigger after scrolling and near viewport edges;
- keyboard focus, Escape, outside-click, and repeated open/close behavior; and
- sign-in, workspace and project navigation, Live updates, and representative
  API operations.

A local real-pointer browser exercise confirmed that Priority changed from none
to high, Modules from none to alpha, and Labels from none to security inside a
dialog using the shared layer. The production build, lint, types, format, and
repository contract tests also passed.

`rc.17` is the immediately previous complete publication, but it contains the
pointer-interaction failure corrected here. `rc.16`, `rc.15`, `rc.14`,
`rc.13`, and `rc.12` contain earlier frontend migration failures. None is a
recommended rollback target. Because `rc.12` through `rc.18` add no schema or
data migration, a coordinated application rollback from `rc.18` to `rc.11`
does not require a database restore solely because one of those releases was
deployed. Stop or replace all application Pods together, deploy the `rc.11`
chart and images as one revision, and repeat the representative application and
access-control checks. Restore the pre-upgrade backup when unrelated writes,
data corruption, or the incident being handled requires point-in-time recovery.

### Upgrade from `rc.16` to `rc.17`

This release completes the visibility and interaction portion of the Headless UI
2 Popper migration. `rc.16` correctly attached Popper refs, styles, and
attributes to the Headless UI panel root, but most panels remained below
ancestors using `overflow-hidden` or `overflow-y-auto`. A panel could therefore
have correct Popper coordinates while being clipped and appear not to open.
Manually portaled panels could also render below task content because their
stacking layer remained on an unpositioned child.

Every Popper-backed Headless UI panel now either uses Headless UI's native portal
or its existing explicit portal. The positioned panel root owns an explicit
stacking layer and protects portaled pointer events from surrounding
outside-click handlers. The shared single-select commits a selected value before
closing, and three Popper-backed popovers missed by the earlier migration now
follow the same root-ref contract. Repository contract tests reject unportaled,
unprotected, unlayered, or nested-ref panels.

There is no Django migration and no Helm values, Secret, permission, Kubernetes
resource, or network-policy contract change. The inherited Plane source remains
`v1.4.0-rc2` (`package.json` version `1.4.0`). Existing `rc.16` values are
compatible with the `rc.17` chart. Upgrade the API, workers, Live service, and
frontends together as one Helm revision; mixed application versions are not a
qualified steady state.

Before upgrading:

1. take a PostgreSQL backup, prove that it can be restored in isolation, and
   record the current Helm revision and application image digests;
2. confirm the target package is `0.1.0-rc.17`, its application version is
   `v0.1.0-rc.17`, and its signatures and digests pass the
   [release verification procedure](security.md#verify-release-010-rc17);
3. render the existing values against the target chart and verify that only the
   expected release versions and immutable image digests change; and
4. schedule all Hangar application components as one coordinated rollout.

After the rollout, use a clean browser profile and verify:

- sign-in, workspace navigation, project navigation, Live updates, and
  representative API operations;
- opening and selecting values in priority, state, estimate, member, project,
  module, cycle, date, date-range, label, intake-state, onboarding role, and
  account or workspace menus;
- every panel is visible beside its trigger inside task details, including after
  scrolling and near viewport edges;
- keyboard focus, pointer selection, Escape, outside-click, and repeated
  open/close behavior; and
- the browser console contains no Headless UI Fragment, clipping, or
  panel-positioning error.

`rc.16` is the immediately previous complete publication, but it contains the
visibility failure corrected here. `rc.15`, `rc.14`, `rc.13`, and `rc.12`
contain the earlier frontend migration failures. None is a recommended rollback
target. Because `rc.12` through `rc.17` add no schema or data migration, a
coordinated application rollback from `rc.17` to `rc.11` does not require a
database restore solely because one of those releases was deployed. Stop or
replace all application Pods together, deploy the `rc.11` chart and images as
one revision, and repeat the representative application and access-control
checks. Restore the pre-upgrade backup when unrelated writes, data corruption,
or the incident being handled requires point-in-time recovery.

### Upgrade from `rc.15` to `rc.16`

This release completes the positioning part of the Headless UI 2 migration.
Plane's inherited Headless UI 1 structure attached each Popper ref, style, and
attributes object to an inner `<div>` beneath `Combobox.Options`,
`Listbox.Options`, `Menu.Items`, or `Popover.Panel`. Under Headless UI 2 and
React 19, the descendant did not become the active positioned panel, so Popper
could retain its initial absolute position at the upper-left corner.

All 28 affected panels now own the Popper integration directly on their Headless
UI root: 17 combo boxes, 2 list boxes, 1 menu, and 8 popovers across the web,
Space, and shared UI packages. Repository contract tests reject nested Popper
targets and unsafe Fragment-backed panels. A browser geometry exercise confirmed
that the corrected panel follows its trigger instead of remaining at `(0, 0)`.

There is no Django migration and no Helm values, Secret, permission, Kubernetes
resource, or network-policy contract change. The inherited Plane source remains
`v1.4.0-rc2` (`package.json` version `1.4.0`). Existing `rc.15` values are
compatible with the `rc.16` chart. Upgrade the API, workers, Live service, and
frontends together as one Helm revision; mixed application versions are not a
qualified steady state.

Before upgrading:

1. take a PostgreSQL backup, prove that it can be restored in isolation, and
   record the current Helm revision and application image digests;
2. confirm the target package is `0.1.0-rc.16`, its application version is
   `v0.1.0-rc.16`, and its signatures and digests pass the
   [release verification procedure](security.md#verify-release-010-rc16);
3. render the existing values against the target chart and verify that only the
   expected release versions and immutable image digests change; and
4. schedule all Hangar application components as one coordinated rollout.

After the rollout, use a clean browser profile and verify:

- sign-in, workspace navigation, project navigation, Live updates, and
  representative API operations;
- opening and selecting values in priority, state, estimate, member, project,
  module, cycle, date, date-range, label, intake-state, onboarding role, and
  account or workspace menus;
- every panel is placed beside its trigger, including after scrolling and near
  viewport edges;
- keyboard focus, Escape, outside-click, and repeated open/close behavior; and
- the browser console contains no Headless UI Fragment or panel-positioning
  error.

`rc.15` is the immediately previous complete publication, but it contains the
positioning failure corrected here. `rc.14`, `rc.13`, and `rc.12` contain the
earlier frontend migration failures. None is a recommended rollback target.
Because `rc.12` through `rc.16` add no schema or data migration, a coordinated
application rollback from `rc.16` to `rc.11` does not require a database restore
solely because one of those releases was deployed. Stop or replace all
application Pods together, deploy the `rc.11` chart and images as one revision,
and repeat the representative application and access-control checks. Restore
the pre-upgrade backup when unrelated writes, data corruption, or the incident
being handled requires point-in-time recovery.

### Upgrade from `rc.14` to `rc.15`

This release completes the behavioral part of the Headless UI 2 dropdown
migration. Headless UI 2 makes `Combobox.Options`, `Listbox.Options`, and
`Menu.Items` modal by default. Hangar's inherited dropdowns use external open
state and, in several cases, Popper or portals. The new modal default could apply
`inert` and `aria-hidden` to focused task content, while an independent internal
close could leave an externally rendered panel visible but unable to select an
option.

All 30 legacy Headless UI option panels across the web, Space, admin, and shared
UI packages now explicitly retain the non-modal Headless UI 1 contract. All 11
shared `ComboDropDown` consumers synchronize Headless UI close events with their
external state. Open and close callbacks use an immediate state ref so one
interaction cannot invoke a lifecycle callback twice. Import-aware repository
contract tests reject a new modal legacy panel or an unsynchronized shared
combo-box.

There is no Django migration and no Helm values, Secret, permission, Kubernetes
resource, or network-policy contract change. The inherited Plane source remains
`v1.4.0-rc2` (`package.json` version `1.4.0`). Existing `rc.14` values are
compatible with the `rc.15` chart. Upgrade the API, workers, Live service, and
frontends together as one Helm revision; mixed application versions are not a
qualified steady state.

Before upgrading:

1. take a PostgreSQL backup, prove that it can be restored in isolation, and
   record the current Helm revision and application image digests;
2. confirm the target package is `0.1.0-rc.15`, its application version is
   `v0.1.0-rc.15`, and its signatures and digests pass the
   [release verification procedure](security.md#verify-release-010-rc15);
3. render the existing values against the target chart and verify that only the
   expected release versions and immutable image digests change; and
4. schedule all Hangar application components as one coordinated rollout.

After the rollout, use a clean browser profile and verify:

- sign-in, workspace navigation, project navigation, Live updates, and
  representative API operations;
- opening and selecting values in priority, state, estimate, member, project,
  module, cycle, date, date-range, label, intake-state, onboarding role, and
  account or workspace menus;
- keyboard focus, Escape, outside-click, and repeated open/close behavior;
- focused task content does not acquire an `aria-hidden` or inert ancestor when
  a dropdown opens; and
- the browser console contains no Headless UI Fragment error and no warning that
  `aria-hidden` was blocked because a descendant retained focus.

`rc.14` is the immediately previous complete publication, but it contains the
dropdown interaction failure corrected here. `rc.13` and `rc.12` contain the
earlier frontend migration failures. None is a recommended rollback target.
Because `rc.12` through `rc.15` add no schema or data migration, a coordinated
application rollback from `rc.15` to `rc.11` does not require a database restore
solely because one of those releases was deployed. Stop or replace all
application Pods together, deploy the `rc.11` chart and images as one revision,
and repeat the representative application and access-control checks. Restore
the pre-upgrade backup when unrelated writes, data corruption, or the incident
being handled requires point-in-time recovery.

### Upgrade from `rc.13` to `rc.14`

This release completes the Headless UI 2 migration that was incomplete in
`rc.13`. Shared `ComboDropDown` triggers now give `Combobox.Button` ownership of
a native `<button>` instead of asking Headless UI to forward refs, accessibility
attributes, state, and event handlers through a React Fragment. The migration
covers member, module, project, intake-state, priority, state, estimate, and
cycle selectors.

Repository-wide contract tests now execute both the failing Fragment-backed
`Combobox.Button` case and the supported native-button case. They also scan every
application and package for Fragment-backed Headless UI components, and verify
that every shared combo-box trigger resolves to a native button. This extends the
hydration and transition coverage added in `rc.13`.

There is no Django migration and no Helm values, Secret, permission, Kubernetes
resource, or network-policy contract change. The inherited Plane source remains
`v1.4.0-rc2` (`package.json` version `1.4.0`). Existing `rc.13` values are
compatible with the `rc.14` chart. Upgrade the API, workers, Live service, and
frontends together as one Helm revision; mixed application versions are not a
qualified steady state.

Before upgrading:

1. take a PostgreSQL backup, prove that it can be restored in isolation, and
   record the current Helm revision and application image digests;
2. confirm the target package is `0.1.0-rc.14`, its application version is
   `v0.1.0-rc.14`, and its signatures and digests pass the
   [release verification procedure](security.md#verify-release-010-rc14);
3. render the existing values against the target chart and verify that only the
   expected release versions and immutable image digests change; and
4. schedule all Hangar application components as one coordinated rollout.

After the rollout, use a clean browser profile and verify:

- sign-in, workspace navigation, project navigation, Live updates, and
  representative API operations;
- member, module, project, intake-state, priority, state, estimate, and cycle
  selectors on routes where the operator's test account can access them;
- keyboard focus and selection behavior for those selectors; and
- the browser console contains neither React error `#418` nor a Headless UI
  `Passing props on "Fragment"` error from `Transition.Child` or
  `Combobox.Button`.

`rc.13` is the immediately previous complete publication, but it contains the
remaining combo-box failure corrected here. `rc.12` contains the earlier
hydration and transition failures. Neither is a recommended rollback target.
Because `rc.12`, `rc.13`, and `rc.14` add no schema or data migration, a
coordinated application rollback from `rc.14` to `rc.11` does not require a
database restore solely because one of those releases was deployed. Stop or
replace all application Pods together, deploy the `rc.11` chart and images as
one revision, and repeat the representative application and access-control
checks. Restore the pre-upgrade backup when unrelated writes, data corruption,
or the incident being handled requires point-in-time recovery.

### Upgrade from `rc.12` to `rc.13`

This release corrects two frontend runtime incompatibilities introduced by the
React 19 and Headless UI 2 update in `rc.12`. The SPA hydration fallback now
produces the same initial tree during prerendering and in the browser, preventing
React error `#418` and duplicate head resources. The project-sidebar transition
now owns a DOM element so Headless UI can forward its transition ref instead of
throwing while rendering multiple children.

There is no Django migration and no Helm values, Secret, permission, Kubernetes
resource, or network-policy contract change. The inherited Plane source remains
`v1.4.0-rc2` (`package.json` version `1.4.0`). Existing `rc.12` values are
compatible with the `rc.13` chart. The release images must still be upgraded as
one Helm revision; mixed application versions are not a qualified steady state.

Before upgrading:

1. take a PostgreSQL backup, prove that it can be restored in isolation, and
   record the current Helm revision and application image digests;
2. confirm the target package is `0.1.0-rc.13`, its application version is
   `v0.1.0-rc.13`, and its signatures and digests pass the
   [release verification procedure](security.md#verify-release-010-rc13);
3. render the existing values against the target chart and verify that only the
   expected release versions and immutable image digests change; and
4. schedule the API, workers, Live service, and frontends as one coordinated
   rollout.

After the rollout, use a clean browser profile and verify:

- the sign-in page renders without React error `#418`;
- `config.js` and the global stylesheet occur only once in the hydrated document;
- opening the project list in a workspace does not raise the Headless UI
  `Passing props on "Fragment"` error; and
- representative sign-in, workspace navigation, project navigation, Live
  updates, and API operations still work.

`rc.12` is the immediately previous published release, but it contains the
frontend defects corrected here and is not a recommended rollback target.
Because neither release adds a schema or data migration, a coordinated
application rollback from `rc.13` to `rc.11` does not require a database restore
solely because `rc.12` or `rc.13` was deployed. Stop or replace all application
Pods together, deploy the `rc.11` chart and images as one revision, and repeat the
representative application and access-control checks. Restore the pre-upgrade
backup when unrelated writes, data corruption, or the incident being handled
requires point-in-time recovery.

### Upgrade from `rc.11` to `rc.12`

This upgrade synchronizes the inherited Plane source from `v1.3.1` to
`v1.4.0-rc2` (`package.json` version `1.4.0`). It includes upstream authorization
and privacy corrections for project cycles and modules, project-member
permissions, page-version reads, guest issue listings, and bulk asset association.
The asset correction allows an uploader to associate a new unassigned asset with
its target project while rejecting assets uploaded by another user or already
assigned to a different project. Uploaded filenames also have control characters
removed before storage.

The release updates `mistune` to 3.3.3, `postcss` to 8.5.23, `sharp` to 0.35.3,
React Router to 8.3.0, `js-yaml` to 4.3.0, and `valibot` to 1.4.2. There is no new
Django migration and no Helm values, Secret, permission, or network-policy
contract change. Because the Plane update includes coordinated client and server
changes, deploy the API, workers, Live service, and frontends together rather than
running mixed application versions as a steady state.

Before upgrading:

1. take a PostgreSQL backup, prove that it can be restored in isolation, and
   record the current Helm revision and application image digests;
2. confirm the target package is `0.1.0-rc.12`, its application version is
   `v0.1.0-rc.12`, and its signatures and digests pass the
   [release verification procedure](security.md#verify-release-010-rc12);
3. render the existing values against the target chart and review the immutable
   image digests, migration Job, Secret references, and NetworkPolicies; and
4. schedule the API, workers, Live service, and frontends as one coordinated
   rollout.

After the rollout, verify:

- a workspace member who is not a member of a private project cannot list that
  project's cycles, modules, member permissions, or page versions;
- a guest issue listing contains only issues the guest created;
- a project member can still read the correct project's member roster and page
  history;
- an uploader can associate a fresh unassigned asset with its target project,
  while another user's asset and an asset from a different project are rejected;
  and
- uploads with control characters in their filenames are accepted only under a
  safely sanitized stored name.

Because `rc.12` adds no schema or data migration, a coordinated application
rollback to `rc.11` does not require a database restore solely for this release.
Stop or replace all `rc.12` application Pods together, deploy the `rc.11` chart
and images as one revision, and then re-run the representative access-control and
asset checks. Restore the pre-upgrade backup if unrelated writes or an incident
require data recovery. Do not operate mixed `rc.11` and `rc.12` application
versions as a steady state.

### Upgrade from `rc.10` to `rc.11`

This upgrade replaces the separate Epic web collection with the canonical Work
Items state and API path. It also provisions stable Task and Epic system types,
backfills active untyped work items, and enforces project-scoped type and hierarchy
invariants on the server. Treat the upgrade as data-affecting and keep old and new
application versions from accepting concurrent project or work-item writes during
the migration window.

Before upgrading:

1. take a PostgreSQL backup, prove that it can be restored in isolation, and
   record the current Helm revision and application image digests;
2. stop or externally block project and work-item mutations, then allow active
   background tasks to reach a safe boundary before the migration Job starts;
3. confirm the target package is `0.1.0-rc.11`, its application version is
   `v0.1.0-rc.11`, and its signatures and digests pass the
   [release verification procedure](security.md#verify-release-010-rc11); and
4. render the existing values against the target chart and review the migration
   Job, immutable image digests, and unchanged Secret and NetworkPolicy contract.

The migration Job applies `db.0127_issue_type_system_keys`. For every active
project it creates or repairs a canonical Task type at level 0 and a canonical
Epic type at level 1, links Task as the project default, and assigns Task to active
work items that have no type. A user-defined type is not claimed merely because
its display name is `Task`; stable `system_key` values identify the two system
types. The migration reuses the oldest active legacy Epic type when possible and
does not delete other custom or legacy type rows.

The schema and data changes are one atomic PostgreSQL migration. Provisioning can
create deferred foreign-key checks, so the migration explicitly settles those
checks before creating the partial unique index and system-invariant constraint.
Any failure rolls back the new column, provisioning, backfill, and constraints
together. The index and project-wide backfill can hold database locks; qualify the
runtime against a restored production-sized database before scheduling the live
maintenance window.

After the rollout, verify:

- **Project settings → Work item types** shows one canonical default Task and one
  canonical Epic at level 1;
- an Epic can be created, filtered, opened, updated, archived, and restored from
  the ordinary Work Items surfaces;
- a Task can be attached below an Epic, while cross-project parents, Epic parents,
  direct cycles, and indirect cycles are rejected without a partial mutation;
- existing active work items that previously had no type now use the canonical
  Task type; and
- the former project `/epics` web route redirects to Work Items while legacy Epic
  API clients remain scoped to Epic records.

Rolling the application back to `rc.10` restores its separate Epic client model
and does not undo the new type rows, project links, or work-item assignments. The
reverse migration removes the `system_key` schema and constraints but intentionally
does not delete provisioned data. Prefer a forward correction and redeploy
`rc.11`. For an exact rollback, stop all newer Pods, restore the coordinated
pre-upgrade PostgreSQL backup, and deploy the `0.1.0-rc.10` chart and images as one
revision before accepting writes.

### Upgrade from `rc.9` to `rc.10`

This upgrade repairs the Epic collection contract and normal work-item/comment
creation after the Todoist idempotency constraints introduced in `rc.9`. Keep
Todoist import workers and the API on one release during the rollout; the partial
unique indexes remain active and mixed application versions are not a supported
steady state.

Before upgrading:

1. take a PostgreSQL backup and record the current Helm revision and application
   image digests;
2. allow active Todoist imports to reach a terminal state, or disable new import
   mutations and record the remaining jobs before replacing API and worker Pods;
3. confirm the target package is `0.1.0-rc.10`, its application version is
   `v0.1.0-rc.10`, and its signatures and digests pass the
   [release verification procedure](security.md#verify-release-010-rc10); and
4. render the existing values against the target chart and review the migration
   Job and image changes before applying them.

The migration Job applies `db.0126_optional_issue_external_identifiers`. It makes
the already-nullable `external_source` and `external_id` fields explicitly
default to `None` in Django's model state for work items and comments. It does not
rewrite existing rows, relax the Todoist-only partial unique indexes from
`db.0125`, or make external identifiers operator-controlled through the ordinary
create API. The default restores the serializer contract: normal work items,
Epics, and comments do not need importer identifiers, while Todoist-created rows
remain idempotent.

After the rollout, verify:

- an ordinary work item and comment can be created without either external field;
- the Epics page reaches a terminal rendered or explicit error state rather than
  loading indefinitely;
- Epic list, grouped, and paginated views contain only Epic work items and report
  counts that match the visible filter; and
- if imports are enabled, one synthetic preview/import/report cycle still creates
  no duplicate work items, comments, or modules when delivery is retried.

The forward migration is schema-compatible with the `rc.9` database layout, but
rolling the application back to `rc.9` reintroduces its serializer and Epic
collection defects. Do not treat that rollback as a repair. Prefer correcting the
rollout or configuration and completing the forward upgrade. If an emergency
application rollback is unavoidable, keep the PostgreSQL backup, do not reverse
`db.0126` while newer Pods are running, and repeat the creation and importer
integrity checks after returning to `rc.10`.

### Upgrade from `rc.8` to `rc.9`

Treat this upgrade as data-affecting and schedule an import maintenance window.
Before rendering the target release:

1. prevent workspace administrators from starting, cancelling, or retrying
   Todoist imports, then wait for existing jobs to reach a terminal state;
2. record active import jobs, oldest pending dispatch, queue depth, retained
   source objects, and any unresolved cleanup failures without copying sensitive
   source identifiers into the change record;
3. take a coordinated PostgreSQL and object-storage backup and prove it can be
   restored into an isolated environment; and
4. render the `rc.9` values with `todoistImports.enabled=false` for the first
   upgrade. Enable imports only after the migration and post-upgrade checks pass.

The migration Job applies `db.0125` and `ext.0007` through `ext.0010`.
`db.0125` deliberately stops before creating its partial unique indexes if active
Todoist-created tasks, comments, or modules contain duplicate external IDs. Do not
delete arbitrary duplicates merely to make the migration pass. Preserve the
affected records, identify the authoritative import result, test a reviewed repair
against a restored copy, and repeat the coordinated backup after remediation.

`ext.0007` fails any still-active import with the safe reason
`security_upgrade_required`, clears its retained execution configuration and
broker task identifier, and installs the fenced lease, retry, dispatch, retention,
and audit state. `ext.0008` through `ext.0010` initialize admission budgets and a
rolling 24-hour usage ledger from existing jobs. A migration-failed job is not
resumed automatically; review its history and project effects before creating an
explicit retry.

After the upgrade, verify authentication, representative project writes, uploads,
background work, Runner error handling, and the deployment-managed telemetry and
email status. Before enabling Todoist imports, verify the private bucket, Valkey,
PostgreSQL, RabbitMQ, Beat, and the dedicated `imports` worker; then complete the
synthetic preview/import/report and over-limit checks in
[release verification](#verify-a-release).

Application rollback to `rc.8` is not qualified after these migrations. Helm
rollback does not reverse transformed job state or the new database protocol. To
return to `rc.8`, restore the coordinated pre-upgrade PostgreSQL and object-storage
recovery point into clean services and deploy the `0.1.0-rc.8` chart.

### Upgrade from `rc.7` to `rc.8`

Treat this upgrade as data-affecting. Before rendering the target release:

1. take a coordinated PostgreSQL and object-storage backup and prove it can be
   restored into an isolated environment;
2. disable OIDC and SAML login and prepare authoritative stable-subject mappings
   according to the
   [federated SSO migration guide](../federated-sso-security.md); apply and review
   the mappings after the schema migration and before re-enabling either provider;
   do not infer bindings from matching email addresses;
3. if secure email will be enabled, complete the SES, SQS, DNS, IAM, Secret, and
   retention prerequisites in the
   [SES operations guide](../aws-ses-email-operations.md); and
4. if Todoist imports will be enabled, configure and verify the distinct private
   import bucket described by the [configuration reference](configuration.md).

The migration Job applies database migrations `db.0122` through `db.0124`,
`license.0008`, and `ext.0004` through `ext.0006`. Runner hardening intentionally
stops if existing installation or audit records lack required actor, target, or
consent evidence. Investigate and preserve that evidence; do not delete records
merely to make the migration pass.

After the upgrade, verify ordinary and federated authentication, representative
project writes, uploads, background work, and any enabled email or import path.
Application rollback to `rc.7` is not qualified after these migrations. Restore
the coordinated pre-upgrade recovery point into a clean environment if a return
to `rc.7` is required.

### 1. Read release-specific constraints

Read the target GitHub Release and the
[Kubernetes support boundary](README.md#support-boundary). Confirm that the
current version is an allowed upgrade source and whether its database migration
is backward-compatible.

Do not upgrade from `plane-ce` by changing only the chart reference. Hangar does
not define that migration path.

### 2. Verify artifacts

Follow [security and artifact verification](security.md) for the target chart
and images. Record the chart version and OCI digest in the change request.

### 3. Create a coordinated recovery point

Back up PostgreSQL and object storage so both represent the same application
recovery point. Record:

- backup identifiers and timestamps;
- application and chart version;
- external-service versions;
- restoration encryption keys or key references; and
- the tested restore procedure.

Do not treat Helm history, retained PVCs, or a database-only backup as a complete
Hangar recovery point.

### 4. Render and compare

```bash
export TARGET_CHART_VERSION=REPLACE_ME

helm --namespace "$NAMESPACE" get manifest "$RELEASE_NAME" \
  > current-rendered.yaml

helm template "$RELEASE_NAME" oci://ghcr.io/szymczag/charts/hangar \
  --version "$TARGET_CHART_VERSION" \
  --namespace "$NAMESPACE" \
  --values production-values.yaml \
  > target-rendered.yaml

diff --unified current-rendered.yaml target-rendered.yaml
```

Review workload images and digests, environment sources, Ingress, Services,
NetworkPolicies, security contexts, resource changes, and migration settings.
Rendered output must not contain Secret values.

### 5. Upgrade atomically

```bash
helm upgrade "$RELEASE_NAME" oci://ghcr.io/szymczag/charts/hangar \
  --version "$TARGET_CHART_VERSION" \
  --namespace "$NAMESPACE" \
  --values production-values.yaml \
  --rollback-on-failure \
  --wait \
  --wait-for-jobs \
  --timeout 20m
```

Use the evaluation values file for an evaluation release. The migrator waits for
the configured database endpoint, retries within bounded limits, and must finish
before Helm reports success.

### 6. Run post-upgrade checks

Repeat [release verification](#verify-a-release), then test authentication,
representative writes, an upload and download, WebSockets, and background work.
Confirm that a new migration Job exists for the new Helm revision.

## Respond to a failed migration

1. Stop retrying the upgrade until the failure is understood.
2. Preserve the Job name, Pod status, events, and redacted migration logs.
3. Confirm database reachability and that `DATABASE_URL` exists, without printing
   its value.
4. Determine whether the migration made any schema or data changes.
5. Follow the target release's migration recovery procedure.

Do not delete the failed Job merely to make Helm appear healthy. Do not run the
migration entrypoint manually against production data unless the release-specific
recovery procedure explicitly requires it.

## Decide between Helm rollback and data restore

`helm rollback` restores Kubernetes resources. It does not undo database
migrations, object writes, queue state, or external-service configuration.

| Situation                                           | Action                                                                                        |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Upgrade failed before any incompatible state change | Roll back to the prior Helm revision, then verify                                             |
| Migration is documented as backward-compatible      | Rollback may be used after release-specific review                                            |
| Migration changed schema or data incompatibly       | Restore the coordinated backup into a clean environment and deploy the matching chart version |
| Compatibility is unknown                            | Treat it as incompatible; do not guess                                                        |

To inspect Helm history:

```bash
helm --namespace "$NAMESPACE" history "$RELEASE_NAME"
```

When rollback is safe:

```bash
helm --namespace "$NAMESPACE" rollback "$RELEASE_NAME" REVISION \
  --wait \
  --timeout 20m
```

Always repeat application-flow tests after rollback.

## Back up and restore

### Production profile

The chart does not orchestrate application-consistent backups. Use native,
supported tooling for PostgreSQL and the object-storage provider.

A valid exercise must:

1. prevent or account for writes while selecting a common recovery point;
2. back up PostgreSQL and uploaded objects;
3. restore into clean services or isolated recovery targets;
4. deploy the chart version matching the backup;
5. verify authentication, representative projects, uploads, downloads, and
   background jobs; and
6. record actual recovery-point and recovery-time results.

Cache and transient queue state may be reconstructed only when the application
and release procedure explicitly permit it. Durable queue state and provider
configuration still require an operator decision.

### Evaluation profile

Evaluation uses four retained PVCs. Snapshot PostgreSQL and object-storage
volumes only with a CSI driver and backend whose crash/application consistency
has been tested. Copying files from live volumes is not a supported backup.

PVC retention reduces accidental deletion risk; it does not create a separate
copy and is not a backup.

## Rotate credentials

Updating a Secret does not automatically restart its consumers.

| Credential                 | Workloads to restart or replace                                       |
| -------------------------- | --------------------------------------------------------------------- |
| `SECRET_KEY`               | API, worker, beat worker; invalidate sessions and retest signed links |
| `LIVE_SERVER_SECRET_KEY`   | Live                                                                  |
| `DATABASE_URL`             | API, worker, beat worker, and the next migrator Job                   |
| `REDIS_URL`                | API, Live, worker, beat worker, and the next migrator Job             |
| `AMQP_URL`                 | API, worker, beat worker                                              |
| Object-storage credentials | API, general worker, and enabled Todoist import worker                |

Use the dependency provider's overlap procedure when old and new credentials can
coexist:

1. create the new provider credential;
2. update the managed Kubernetes Secret;
3. restart only affected Deployments;
4. wait for rollout and exercise the affected flow;
5. revoke the old provider credential; and
6. verify that logs and events contain no credential values.

Restart an affected Deployment with:

```bash
kubectl --namespace "$NAMESPACE" rollout restart deployment/DEPLOYMENT_NAME
kubectl --namespace "$NAMESPACE" rollout status deployment/DEPLOYMENT_NAME \
  --timeout=5m
```

Treat database and object-storage rotations as maintenance operations when the
provider cannot support overlap.

## Scale workloads

Change replicas through a values file and `helm upgrade`, not with an imperative
`kubectl scale`, so Helm remains the source of desired state.

- Web, admin, space, Live, and task workers accept one or more replicas.
- The Todoist import worker accepts one or more replicas only when imports are
  enabled; its process concurrency and prefetch remain separately bounded.
- API replicas are fixed at one for this release.
- Beat worker replicas are fixed at one because scheduler leader election is not
  implemented.
- Evaluation dependencies are single replica.

Review resource usage, database connections, queue throughput, PDB behavior, and
node capacity before increasing replicas.

## Operate Todoist imports

Keep API, import-worker, and Beat on the same chart revision and importer
configuration. Before enabling the feature, apply the chart's database migration,
verify the private bucket rejects anonymous reads, and confirm PostgreSQL,
Valkey, RabbitMQ, and Beat health. Render the target values and verify that the
private import bucket has no Ingress or HTTPRoute.

Inspect workload and queue state without printing environment or Secret values:

```bash
kubectl --namespace "$NAMESPACE" get deployment,pod \
  --selector app.kubernetes.io/component=import-worker
kubectl --namespace "$NAMESPACE" logs deployment/"$RELEASE_NAME"-hangar-import-worker \
  --since=15m
```

Use the actual rendered Deployment name if name overrides are configured. Log
output may contain identifiers; keep it inside the incident boundary and do not
add CSV rows, filenames, mappings, object keys, digests, presigned URLs, or raw
exceptions to tickets.

Monitor active jobs by state, oldest pending dispatch, import queue depth, lease
age/recovery/loss, cancellation latency, quota and throttle denials, source age,
deletion failures, terminal duration/result, and imported/reused/failed counts.
Page an operator when a dispatch remains pending for five minutes, a lease
expires without recovery, a source exceeds retention plus cleanup grace,
cleanup failures repeat, or workspace denials spike.

For immediate containment, set `todoistImports.enabled=false` and perform a
normal Helm upgrade. This rejects new mutations and prevents queued execution;
history, reports, durable jobs, dispatch records, quota ledgers, and audit events
remain for recovery. Do not delete jobs, budget rows, audit events, or private
objects manually to make the UI look healthy. Diagnose the dependency, restore
the same validated settings across API/import-worker/Beat, then re-enable and
verify recovery. Beat must remain single-replica and available for dispatch,
lease recovery, and source reconciliation.

## Uninstall

```bash
helm uninstall "$RELEASE_NAME" --namespace "$NAMESPACE"
```

Production external services and their data are not deleted. Evaluation PVCs are
intentionally retained where supported. Inventory them after uninstall:

```bash
kubectl --namespace "$NAMESPACE" get pvc
```

Delete PVCs or the namespace only after confirming that no recovery or forensic
need remains. Namespace deletion also removes Secrets and the TLS certificate.
