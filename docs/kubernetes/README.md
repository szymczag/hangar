# Deploy Hangar on Kubernetes

Hangar publishes a Helm chart for Kubernetes at:

```text
oci://ghcr.io/szymczag/charts/hangar
```

The current release is `0.6.0-rc.2`. It is a release candidate for `0.6.0`;
the current stable Hangar release for Docker Compose, Docker Swarm and the
all-in-one image remains `0.5.0`. Helm installs a release candidate only when
you name its version. On Kubernetes, both are qualified for evaluation on AMD64
clusters only and are not yet a supported production release.

> [!IMPORTANT]
> Do not use the upstream Plane `plane-ce` chart for Hangar. It does not contain
> the Hangar images, configuration contract, security controls, or release
> evidence described here.

## Choose a deployment profile

| Profile      | Use it for                                           | Stateful services                                                       | Current status                      |
| ------------ | ---------------------------------------------------- | ----------------------------------------------------------------------- | ----------------------------------- |
| `evaluation` | Labs, demonstrations, and compatibility testing      | Bundled single-replica PostgreSQL, Valkey, RabbitMQ, and object storage | Live-qualified on AMD64             |
| `production` | Durable installations with operator-managed services | External PostgreSQL, Valkey, RabbitMQ, and S3-compatible storage        | Available for review, not supported |

Both profiles use a dedicated private object-storage bucket for temporary import
sources. The chart passes that bucket only to the API and import-capable workers; it never adds
the bucket to public Ingress or Gateway routes. Operators must keep anonymous
access disabled. See [configuration](configuration.md#external-object-storage).

Live PDF export never hands document-provided URLs or paths to the renderer.
It resolves and validates image destinations, pins each connection to the
validated address, revalidates every redirect, bounds and re-encodes the image,
and renders only the resulting local data URI. Public object-storage URLs work
without extra configuration. If a deployment intentionally returns a private
storage hostname in presigned URLs, list that exact hostname under
`live.pdfAssetAllowedHosts`; do not use broad domain or network exceptions.

The Live shared secret is also consumed by the general worker for the
authenticated `/convert-document/` server-to-server call. Rotating it therefore
requires a coordinated restart of Live and the general worker deployment.

The web frontend receives the Live origin and `VITE_LIVE_BASE_PATH=/live`
through its generated, non-cacheable runtime `config.js`. The published images
compile in no origin, so outside the chart (Compose, Swarm and the AIO image)
the frontends reach the API, Live, Spaces and God Mode on the page's own origin;
before rc.72 they carried the chart's placeholder `https://hangar.example.com`
instead, which only the chart replaced. Collaboration
WebSockets therefore use `/live/collaboration`, matching the chart proxy route
and the Live service. Published images also bake `/live` as a fallback, so a
missing runtime file cannot silently move collaboration traffic to the root.

Start with the [evaluation installation tutorial](evaluation-install.md) to
exercise the released chart. Use the [production installation guide](production-install.md)
only to review and help qualify the production profile.

The tutorial installs stable `0.5.0`; the [chart README](../../charts/hangar/README.md)
names the same versions and rollback targets. Each guide renders the chart with
`helm template` before installing it and passes the target cluster's version with
`--kube-version`: without a cluster connection Helm checks the chart's
`kubeVersion` range (`>=1.30.0-0 <1.37.0-0`) against its own default, and Helm
4.3 defaults to Kubernetes 1.37, which is outside that range.

## Compatibility

The `0.6.0-rc.2` qualification boundary is:

| Item                   | Qualified boundary                                               |
| ---------------------- | ---------------------------------------------------------------- |
| Kubernetes             | 1.30 through 1.36, including 1.36.2                              |
| Helm                   | 4.2                                                              |
| Inherited Plane source | `v1.4.0` (`917b23a6`) with the `v1.4.3` changes backported       |
| Node architecture      | `linux/amd64`                                                    |
| Pod Security Admission | Restricted                                                       |
| Ingress                | TLS-enabled controller with WebSocket support                    |
| Networking             | A CNI that enforces `NetworkPolicy`                              |
| Storage                | A default `StorageClass`, or explicit evaluation storage classes |

The backend, the editor and the live server are also converged with upstream
`v1.5.0`. God Mode, the instance admin console, and Spaces, which serves the
published boards, use the upstream `v1.5.0` design. The web app loads the
upstream `v1.5.0` design tokens, and every screen, including the
notifications, the profile pages and Hangar's capacity, work item type,
workshop and import screens, uses the `v1.5.0` components; the web app no
longer loads the `v1.4` component libraries. The editor's own toolbar, menus,
code block and table colour picker are still the `v1.4` design.

The chart does not install an ingress controller, cert-manager, a CNI, a CSI
driver, an external secret operator, or observability infrastructure.

## Secure email delivery

Secure email delivery is disabled by default. When `mail.enabled=true`, the
chart adds a dedicated `mail-worker` for Amazon SES API delivery, feedback
processing, audit receipts, suppression handling, and optional OpenPGP
encryption. The workload is isolated from the general workers and is the only
application pod that receives the mail service account or optional SES and SQS
credentials. OpenPGP notifications are encrypted to the recipient before
durable storage, while unencrypted account messages are submitted directly
and retain receipt metadata only.

Before enabling it, an operator must provide a verified SES identity, DKIM and
DMARC DNS records, production SES access, configuration sets, an SNS topic, an
SQS queue, and least-privilege IAM. A `hangar-mail` Secret is needed only for
the optional static AWS credential fallback; workload identity requires no
mail Secret values. The chart does not create or validate those AWS resources.

Use the [configuration reference](configuration.md#secure-email-delivery) for
the Helm values and Secret contract. Follow the
[Amazon SES operations guide](../aws-ses-email-operations.md) for provisioning,
rollout, deliverability monitoring, suppression recovery, and incidents. The
[email security model](../email-delivery-and-openpgp.md) explains data handling,
retention, and OpenPGP policy.

## Content-Security-Policy

The web, admin and space images send a Content-Security-Policy of their own, and
`contentSecurityPolicy.reportOnly` now defaults to `false`: the policy is
enforced, and violations are reported to the API, which logs them as
`Content-Security-Policy violation`. Set it to `true` to watch reports without
blocking anything, for example while adding an origin.

Two rules decide whether a deployment needs anything else:

- **Images are this instance's own.** The chart adds the object-storage origin
  itself; `contentSecurityPolicy.imgSrc` is only for storage served from a
  further origin of yours. An image a description points at on another host is
  not loaded, and a profile picture from an identity provider is copied into
  object storage at sign-in. For rows written before this release, run
  `python manage.py localize_external_images` (reports first, then `--apply`)
  in an API pod.
- **Sign-in posts to the API, which answers with a redirect.** Chrome checks
  `form-action` on that redirect, so `hangar.publicOrigin` and the base URLs
  must be the origins users actually open, or the form is refused and sign-in
  silently does nothing.

The object-storage origins the chart adds follow how the API presigns, not
only `externalServices.objectStorage.pathStyle`. The API always presigns
against an endpoint (`publicEndpoint`, else `endpoint`), and with an endpoint
the published API image's botocore 1.34 signs path-style URLs on that
endpoint's origin, for example `https://s3.example.com/hangar/...`, even when
`pathStyle` is `false`. The chart therefore always allows the endpoint origin
in `img-src`, `connect-src` and `media-src`. While `pathStyle` is `false` it
also allows the bucket's virtual-hosted origin, `https://hangar.s3.example.com`,
so a change to virtual-hosted addressing does not break uploads; that second
origin is left out when the endpoint host is an IP address or the bucket name is
not a single DNS label (for example, it contains a dot). Before this fix a
production install with `pathStyle: false` allowed only the virtual-hosted
origin, so browser uploads and stored images were blocked by the policy. Both
origins belong to the configured bucket's storage; nothing else is added.
Evaluation mode is unchanged and allows the application's own origin, which
routes the bucket path.

Trusted Types keep their own switch, `contentSecurityPolicy.trustedTypes`, which
stays at `report`. See
[content-security-policy.md](../content-security-policy.md).

## Evaluation object storage

The evaluation profile's bundled SeaweedFS (`evaluationObjectStorage`) now runs
`docker.io/chrislusf/seaweedfs:4.48` (amd64 digest
`sha256:aba492e2a4e4c90bff795745e8e660affa1f09e7650f5981bd7bccd1a06cd931`,
previously 4.39) and is hardened inside the Pod rather than only by
NetworkPolicy:

- **Filer and volume servers require signed requests.** `weed mini` runs the
  master, volume, filer and S3 servers in one process. The filer (`8888`) and
  volume (`8080`/`9340`) HTTP ports otherwise serve and accept bucket contents
  without S3 credentials. The container now generates JWT signing keys at each
  start (they never leave the process and are not stored in a Secret), so those
  ports answer `401` to unsigned reads and writes. Only the authenticated S3
  port, `8333`, reaches objects. This holds even where NetworkPolicies are
  disabled (`networkPolicy.enabled=false`) or the CNI does not enforce them.
- **Telemetry, the admin UI and WebDAV are off.** SeaweedFS reports anonymous
  cluster statistics by default; the egress policy already blocked that, and
  now the server no longer tries. The unauthenticated admin UI and WebDAV
  server are not started.

The S3 Service, port, credentials Secret, buckets and PVC are unchanged; no
values change is needed. `helm upgrade` rolls the StatefulSet once, and objects
on the existing PVC remain available. Rolling back to the previous chart
restores 4.39 on the same data. Only the S3 port was ever exposed through the
Service, Ingress or Gateway, so clients are unaffected.

To confirm the hardening on a running install:

```bash
pod=$(kubectl -n <namespace> get pod -l app.kubernetes.io/name=evaluationObjectStorage -o name)
kubectl -n <namespace> exec "$pod" -- curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8888/buckets/
# 401
```

Production installs use external object storage and are not affected.

## Todoist import isolation

Todoist imports are disabled by default. Setting `todoistImports.enabled=true`
exposes the administrator workflow and renders a dedicated `import-worker` that
consumes only the `imports` Celery queue. General and mail workers cannot consume
import jobs. The import worker receives the private object-storage credentials,
uses the same Restricted-compatible security context and egress policy as other
API workloads, and has explicit concurrency, prefetch, resource, replica, and
optional PDB settings.

The API applies independent user/workspace preview and execute throttles. Hard
PostgreSQL admission budgets serialize concurrent user/workspace jobs, active
workspace source bytes, and accepted workspace rows in a 24-hour window. The
chart schema rejects malformed rates and unsafe numeric ranges, while application
startup rejects invalid environment values. Enabling imports therefore requires
the private bucket, Valkey-backed throttling, PostgreSQL migrations, RabbitMQ,
the import worker, and the single Beat scheduler to be healthy together. See the
[configuration reference](configuration.md#todoist-import-admission-and-worker)
and [operations runbook](operations.md#operate-todoist-imports).

## Client IP and rate limiting

The API throttles anonymous sign-in, sign-up, and magic-link requests per client
IP, which it reads from `X-Forwarded-For`. Set `application.numProxies` to the
number of proxies that append to that header: `1` when clients reach the
ingress controller or Gateway directly, plus one for each HTTP load balancer or
CDN in front of it. The chart renders it as `NUM_PROXIES` in the API ConfigMap.
The default, `null`, keeps the previous behaviour, in which the whole header is
the client identity; behind a proxy that appends to a client-supplied header, a
client can then change its throttle identity by sending its own `X-Forwarded-For`. See the
[configuration reference](configuration.md#client-ip-for-rate-limits).

## Release identity

The product, chart, and Git identifiers are deliberately different:

| Identifier         | Current value                               |
| ------------------ | ------------------------------------------- |
| Product version    | `v0.6.0-rc.2`                               |
| Helm chart version | `0.6.0-rc.2`                                |
| Git tag            | `hangar-v0.6.0-rc.2`                        |
| OCI chart          | `ghcr.io/szymczag/charts/hangar:0.6.0-rc.2` |

`rc.1`, `rc.2`, `rc.20`, `rc.24`, `rc.25`, `rc.28`, `rc.33`, and `rc.59` were consumed
by incomplete publication attempts. `rc.59` carried the same changes as `rc.60` and
refused publication on an unsigned tag, so nothing was published under it.
Releases `rc.31` through `rc.38` are retired
after a repository-history privacy correction and are not supported
installation, upgrade, or rollback targets. `rc.64` through `rc.67` are **not
upgrade targets for a deployment that holds a Workshop**: their migration
`ext.0037` fails there, so upgrade to `rc.68` or later instead. The `0.2.0`
release candidates are superseded by `0.2.0` and are not rollback targets.
The `0.3.0` release candidates, `0.3.0-rc.1` and `0.3.0-rc.2`, are superseded
by `0.3.0` and are not rollback targets.
The `0.4.0` release candidates, `0.4.0-rc.1`, `0.4.0-rc.2`, `0.4.0-rc.3` and
`0.4.0-rc.4`, are superseded by `0.4.0` and are not rollback targets.
The `0.5.0` release candidate, `0.5.0-rc.1`, is superseded by `0.5.0` and is
not a rollback target.
`0.6.0-rc.1` was consumed by an incomplete publication: its container images
are in GHCR, but its `live` image does not start, so the chart qualification
failed and neither the chart nor a GitHub Release was published. Do not deploy
its images; it is neither an upgrade nor a rollback target.
`0.5.0` is the current stable release and the supported rollback target for
this one; rolling back to it needs no schema change and no change to the
values, only the images change, and it brings back the visual test seed
command that runs without an opt-in, the callout logo that the editor's
Markdown serializer writes unchecked, the active cycles upsell page, the old
callout logo picker, profile activity rows that do not say what a worklog entry
did, and the web app's profile, notifications, home page and Hangar's own
screens on the `v1.4` components. Rolling back further, to `0.4.0`, needs no
schema change or values change either, and only the images change; it also
brings back worklog entries, with the
logged time, in the profile activity feed and its export, the public API's
activity list and detail, and the notifications of project guests; the intake
endpoint that answers 500 and leaves a stray work item on a project without
intake, and the public API that accepts intake writes while intake is turned
off; the "Upgrade" button on the active cycles page that links off the instance regardless of the external
links switch, "No estimate" that does not clear an estimate, the create dialog
without a work item type's custom properties, and the web app's work items,
cycles, modules, views, pages and intake on the `v1.4` components. Rolling back
further, to `0.3.0`, needs no schema change or values change either, and only
the images change. License migration `0025` only adds a
configuration row that `0.3.0` does not read, so it stays in place. Rolling
back that far also brings back the previous design of the published boards, a public board
API that names every project member and assignee, the web app on the `v1.4`
design tokens and components, workspace members who can invite people and
change or withdraw any pending invitation, and a worker log that prints every
task's arguments, password-reset tokens and sign-in codes included. It also
stops recording page versions; those already recorded stay readable. Rolling back further, to `0.2.2`, needs no schema change or values
change either, but brings back the previous God Mode design. Rolling back
further, to `0.2.1`, needs no schema change or values
change either, but brings back the God Mode sessions that survive clone
detection. Rolling back further, to `0.2.0`, needs no
schema change or values change either. Rolling back further, to `0.1.4`, needs no
schema change either, and pages edited on `0.2.0` or later stay readable
there because the stored Yjs documents do not change. It brings back the
`0.1.4` collaboration bug, in which concurrent edits to one page are lost, so
roll back that far only when you need to. Rolling back further, to `0.1.3`, needs no schema change either, but
`application.numProxies` must be removed from the values first because the
`0.1.3` schema rejects it. Rolling back to `0.1.2` needs no schema change either (the `db.0136` index can
stay), and neither does rolling back further, to `0.1.1`, `0.1.0`, `rc.72`, `rc.71`, `rc.70` or `rc.69`. Rolling back to `rc.68` needs migration
`db.0135` reversed first, as described below. Rolling
back to `rc.67` after that needs no other schema change.
Rolling back to `rc.66` needs none either and restores the larger `space` and
`live` images. Rolling
back to `rc.65` also needs no schema change and restores the
looser asset rules and the previous Caddy build of the proxy. `rc.62`
is **not a usable target for any deployment with Google Calendar capacity
enabled**: every call to Google fails on it, so roll back past it, to `rc.61`.
Earlier `rc.12` through `rc.17` additionally contain frontend migration failures.
Rolling back further, to rc.64, is safe for the database: reversing migration `0134` is
allowed and does nothing, so the deploy boards it repaired stay repaired, which the older build reads
without trouble. The evaluation object store returns to SeaweedFS 4.39, which
reads what 4.48 wrote, and again leaves its filer and volume ports unsigned behind
NetworkPolicy alone. Rolling back to rc.63 additionally re-adds the Workshop type
to every project the next time system types are provisioned, drops the Workshop
role properties and everything recorded in them, and returns trainers whose hours
rc.64 moved to the previous default. Going back further, to rc.61, additionally
returns the frontends to a report-only Content-Security-Policy, removes the
calendar write-back surfaces, and restores the previous training recognition --
which on a calendar that hides its guest list recognizes almost nothing. A
workshop already written to the shared calendar stays there; the older build
stops maintaining it rather than removing it. The license key dropped by rc.62
is not restored by a downgrade. Preserve a
database backup before upgrading and review the rollback limits in the release notes.
Published versions are immutable and are never repaired in place. In
particular, `rc.24`, `rc.25`, and `rc.28` each published only a subset of their
container sets and published no chart or GitHub Release.

## Documentation

- [Release `v0.6.0-rc.2` notes](../releases/hangar-v0.6.0-rc.2.md) — review
  security changes, migrations, compatibility, limitations, and rollback.
- [Install the evaluation profile](evaluation-install.md) — complete a first
  installation in a dedicated namespace.
- [Prepare the production profile](production-install.md) — configure external
  services and review the unsupported production path.
- [Configuration reference](configuration.md) — understand values, Secrets,
  routes, workloads, storage, and networking.
- [Operations](operations.md) — verify, upgrade, rotate credentials, back up,
  restore, roll back, and uninstall. Upgrades from `rc.51` onward follow
  [one procedure](operations.md#upgrade-from-rc51-or-later), with the
  release-specific steps in each release's notes.
- [Security and artifact verification](security.md) — understand the security
  model and [verify a release](security.md#verify-a-release): checksums,
  attestations, signatures, and anonymous access.
- [Troubleshooting](troubleshooting.md) — diagnose common installation and
  runtime failures without collecting credentials.
- [Chart source](../../charts/hangar/README.md) — chart-maintainer entry point.
  It names the same current release, retired versions, and rollback target as
  [Release identity](#release-identity).
- [Delivery and qualification plan](../kubernetes-deployment-plan.md) — normative
  requirements and remaining release gates.

Google Calendar trainer capacity is disabled by default. Enable
`googleCalendarCapacity.enabled` only after registering the Calendar OAuth
callback and adding `CALENDAR_TOKEN_ENCRYPTION_KEYS` to the application Secret.
Capacity lookups are bounded to 25 trainers and 14 days. Atomic Valkey-backed
admission is configured through `googleCalendarCapacity.limits.userRate` and
`googleCalendarCapacity.limits.workspaceRate`; defaults are `20/minute` and
`60/minute`, and admission fails closed while Valkey is unavailable. The web
client coalesces capacity refreshes and honours the endpoint's `Retry-After`
response when either limit is reached.
The previous release is `0.5.0`, tag `hangar-v0.5.0`, and chart
`ghcr.io/szymczag/charts/hangar:0.5.0`, which is also the current stable
release and the rollback target. The stable release before it is `0.4.0`, tag
`hangar-v0.4.0`, and chart `ghcr.io/szymczag/charts/hangar:0.4.0`. Anybody still on rc.62 with
calendar capacity enabled should leave it immediately: every Google request fails
on that release.

Charts `0.2.0-rc.1`, `0.2.0-rc.2` and `0.2.0-rc.3` were release candidates
for `0.2.0` and are superseded by it; do not install them. `0.2.0-rc.1` and its
images exist in the registry, but that candidate has no GitHub Release because
a workflow bug skipped the release job. `0.2.0` is built from the `0.2.0-rc.3`
source, so an installation on any of the candidates upgrades to `0.5.0` with
`helm upgrade` and `--version 0.5.0`; read the 0.5.0 and 0.4.0 notes below
first.

Charts `0.3.0-rc.1` and `0.3.0-rc.2` were release candidates for `0.3.0` and
are superseded by it; do not install them. `0.3.0` is built from the
`0.3.0-rc.2` source, so an installation on either candidate upgrades to `0.5.0`
with `helm upgrade` and `--version 0.5.0`; read the 0.5.0 and 0.4.0 notes below
first.

Charts `0.4.0-rc.1`, `0.4.0-rc.2`, `0.4.0-rc.3` and `0.4.0-rc.4` were release
candidates for `0.4.0` and are superseded by it; do not install them, and
upgrade an installation on any of them to `0.5.0` with `helm upgrade` and
`--version 0.5.0`. The upgrade needs no change to the values. `0.4.0` is built
from the `0.4.0-rc.4` source, so from `0.4.0-rc.4` the upgrade brings only
what the 0.5.0 paragraph below describes. From `0.4.0-rc.1` or `0.4.0-rc.2`, read the 0.4.0-rc.3
invitation note below before you run it; from `0.4.0-rc.3`, the invitation
switch keeps its value. From any candidate up to `0.4.0-rc.3`, rotate or purge
the worker logs as the 0.4.0-rc.4 note below describes.

Chart `0.5.0-rc.1` was the release candidate for `0.5.0` and is superseded by
it; do not install it, and upgrade an installation on it to `0.5.0` with
`helm upgrade` and `--version 0.5.0`. The upgrade needs no change to the
values and runs no migration; only the images change. `0.5.0` is built from the
`0.5.0-rc.1` source plus the worklog and intake fixes of the 0.5.0 paragraph
below and the in-app release notes.

Release 0.6.0-rc.2 adds no database or license migration compared with 0.5.0
and changes nothing in the chart's templates, values or Secrets. Upgrade from
0.5.0 with `helm upgrade` and `--version 0.6.0-rc.2`; Helm does not select a
release candidate otherwise. No other action is required. Every release
rebuilds all its images, so every image digest changes. Of the application
code, the `web` image carries the changes: a user's profile, the notifications
inbox, the home page, Hangar's capacity, work item type, workshop and Todoist
import screens, the maintenance bar and the remaining screens move to the
upstream Plane 1.5.0 design, and the web app no longer loads the 1.4 component
libraries; the editor's callout logo picker opens; profile activity says what a
worklog entry did; sub-work items can be filtered by work item type; and the
workspace active cycles upsell page is removed. The `space` image changes only
in the editor's callout logo picker, and the `live` image only in which parts of
the editor it loads. In all three, the editor's Markdown serializer writes a
callout's logo only when it is a single emoji or a plain icon name. The `live`
image build now fails if the built server imports anything its production
install cannot resolve: the `0.6.0-rc.1` `live` image did not start for that
reason, which is why there is no `0.6.0-rc.1` chart. The
`api` image changes only in the visual test seed command, which now refuses
to run unless `HANGAR_VISUAL_FIXTURES=1` is set; no installation step uses it.
The `admin` and `proxy` code is unchanged. From a release older than 0.5.0,
including 0.5.0-rc.1, read the 0.5.0 paragraph below first. Rolling back to
0.5.0 needs no schema change and no change to the values.

Release 0.5.0 adds no database or license migration compared with 0.4.0 and
changes nothing in the chart's templates, values or Secrets. Upgrade from 0.4.0
with `helm upgrade` and `--version 0.5.0`. No other action is required. Every
release rebuilds all its images, so every image digest changes. Compared with
0.4.0, the `web` image carries the design move and fixes that the 0.5.0-rc.1
paragraph below describes, and hides worklog entries in the profile feeds and
the inbox from readers whose project role may not read worklogs. The `api`
image, which the Celery workers also run, now keeps worklog entries, which
carry the logged time, from project guests in the profile activity feed and
its CSV export, the public API's activity list and detail, and the
notifications to a work item's subscribers, in the app and by e-mail, including
notifications stored before the upgrade; it refuses to create an intake item
on a project without intake, which used to answer 500 and leave a stray work
item; and it no longer prints a `Server Error` line for every 404. **API
clients:** creating, updating and deleting intake items through `/api/v1/` is
now refused with 400 whenever the project's intake is turned off or missing;
before, only both together were refused. E-mails already queued when the new
workers start are sent without a new role check. The `admin` and `space` images
change only in the Hangar logo on light surfaces; the `live` and `proxy` code
is unchanged. From a release older than 0.4.0, including a 0.4.0 release
candidate, read the 0.4.0 paragraph below first. Rolling back to 0.4.0 needs no
schema change and no change to the values, and brings those faults back.

Release 0.5.0-rc.1 adds no database or license migration compared with 0.4.0
and changes nothing in the chart's templates, values or Secrets. Upgrade from
0.4.0 with `helm upgrade` and `--version 0.5.0-rc.1`; Helm does not select a
release candidate otherwise. No other action is required. Every release
rebuilds all its images, so every image digest changes. Of the application
code, the `web` image carries the changes: its work items and their layouts,
filters and create dialog, views, drafts, pages, stickies, cycles, modules,
analytics and intake, and Hangar's own settings pages move to the upstream
Plane 1.5.0 design; "No estimate" now clears an estimate; the create dialog
shows a work item type's custom properties again; and the "Upgrade" button on
the active cycles page, which linked off the instance regardless of the
external links switch, is removed. Guests still see no worklogs. The `api`
image no longer prints a `Server Error` line for every 404, and the `admin`
and `space` images change only in the Hangar logo on light surfaces. The
`live` and `proxy` code is unchanged. From a release older than 0.4.0,
including a 0.4.0 release candidate, read the 0.4.0 paragraph below first.
Rolling back to 0.4.0 needs no schema change and no change to the values.

Release 0.4.0 adds one license migration, `0025`, compared with 0.3.0, and no
database migration, and changes nothing in the chart's templates, values or
Secrets. Upgrade from 0.3.0 with `helm upgrade` and `--version 0.4.0`; the
chart's migration Job runs `0025` with the others, and it needs no step of its
own. The migration changes no table: it adds the `ALLOW_MEMBERS_TO_INVITE` row
to the instance configuration with the value `0`. Every release rebuilds all
its images, so every image digest changes; compared with 0.3.0, the `api`,
`web`, `space` and `admin` images carry code changes, which the 0.4.0-rc.1 to
0.4.0-rc.4 paragraphs below describe one candidate at a time. In short: the
public board API no longer names project members, a breaking change for its
clients outside Hangar's own Spaces; the published boards and the web app's
shell, sign-in and onboarding, projects and settings move to the upstream Plane
1.5.0 design; page version history is recorded from the upgrade on; workspace
invitations become an admin's act until an operator turns on **God Mode →
Workspaces → Members can invite to workspaces**, which is off after the
upgrade; setting a first password is rate limited; and the Celery workers no
longer write task arguments, which held password-reset tokens, sign-in and
e-mail-change codes and invitation join tokens, to their log. **Logs written
before the upgrade are not rewritten**: after the upgrade, rotate or purge the
worker pods' logs and every copy your cluster's log collection holds, or
restrict who can read them, and consider password-reset links and sign-in codes
issued while someone other than their user could read those logs as exposed.
The installer changes in this release, which make an outdated `setup.sh`
refuse to upgrade, concern Docker Compose and Swarm; nothing changes on
Kubernetes. Rolling back to 0.3.0 needs no schema change and no change to the
values: the configuration row stays and 0.3.0 does not read it. Rolling back
brings all those faults back and stops recording page versions.

Release 0.4.0-rc.4 adds no database or license migration compared with
0.4.0-rc.3 and changes nothing in the chart's templates, values or Secrets.
Compared with 0.3.0, 0.4.0-rc.1 and 0.4.0-rc.2 it carries license migration
`0025` from 0.4.0-rc.3, which the chart's migration Job runs with the others.
Upgrade from 0.3.0 or 0.4.0-rc.3 with `helm upgrade` and
`--version 0.4.0-rc.4`; Helm does not select a release candidate otherwise.
Every release rebuilds all its images, so every image digest changes; of the
application code, only the `api` image changes compared with 0.4.0-rc.3, and
the `web` image changes only in its in-app release notes. The `api` image also
runs the worker and beat-worker Deployments, the mail-worker and
import-worker Deployments where they are enabled, and the migration Job. Its Celery workers no longer write task arguments to their
log: up to and including 0.4.0-rc.3, and in upstream Plane, the workers'
`INFO` log carried password-reset tokens, sign-in and e-mail-change codes and
invitation join tokens, and now shows `[redacted]` in their place. **Logs
written before the upgrade are not rewritten**: after the upgrade, rotate or
purge the worker pods' logs and every copy your cluster's log collection holds,
or restrict who can read them, and consider password-reset links and sign-in
codes issued while someone other than their user could read those logs as
exposed; they expire on their own, and a user can request a new one. The `api`
image also keeps the sender on a workspace invitation after its e-mail is sent,
so a member with **Members can invite to workspaces** on sees and manages the
invitations they send. Invitations sent before the upgrade have no recorded
sender and stay with workspace admins. Rolling back to 0.3.0 needs no schema
change and no change to the values, and brings both faults back.

Release 0.4.0-rc.3 adds one license migration, `0025`, compared with 0.3.0
and 0.4.0-rc.2, and changes nothing in the chart's templates, values or
Secrets. The migration changes no table: it adds the `ALLOW_MEMBERS_TO_INVITE`
row to the instance configuration with the value `0` and never overwrites a
row that is already there. It runs in the chart's migration Job with the
others and needs no step of its own. Upgrade from 0.3.0 or 0.4.0-rc.2 with
`helm upgrade` and `--version 0.4.0-rc.3`; Helm does not select a release
candidate otherwise. Compared with 0.4.0-rc.2, three images carry code changes
(every image is rebuilt with a new digest in each release). The `api`
image makes workspace invitations an admin's act: after the upgrade, workspace
members can no longer invite people, change or withdraw pending invitations,
or see the pending-invitation list, until an operator turns on **God Mode →
Workspaces → Members can invite to workspaces**; even then a member sees and
manages only the invitations they sent. Workspace admins are unaffected, and
invitations already pending stay valid. The `api` image also rate limits
setting a first password, per account and per client address. The `admin`
image adds that switch. The `web` image moves its shell, sign-in and
onboarding, projects, and workspace, project and account settings to the
upstream Plane 1.5.0 components, keeps a new API token's secret out of its
cached token list, and offers the invitation controls only where the server
accepts them. The `space` and `live` application code is unchanged. The
installer changes in this candidate, which name the requested release in the
upgrade output, concern Docker Compose and Swarm; nothing changes on
Kubernetes. Rolling back to 0.3.0 needs no schema change and no change to the
values: the configuration row stays and 0.3.0 does not read it. Rolling back
gives workspace members their previous invitation rights again.

Release 0.4.0-rc.2 adds no database or license migration compared with 0.3.0
or 0.4.0-rc.1 and changes nothing in the chart's templates, values or Secrets.
Upgrade from 0.3.0 or 0.4.0-rc.1 with `helm upgrade` and
`--version 0.4.0-rc.2`; Helm does not select a release candidate otherwise. No
other action is required. Compared with 0.4.0-rc.1, three images change. The
`api` image records page version history, which no earlier Hangar release
did; versions are recorded from this release on, not for earlier edits. Its
public board API now returns a work item's votes and reactions from the
`issues/<issue>/votes/` and `issues/<issue>/reactions/` lists, which always
answered an empty list, still scoped to the board and reduced to the public
actor, and answers an empty `vote_items` and `reaction_items` instead of
`null`. The `space` image saves the first reaction on a work item, which it
used to drop. The `web` image loads the upstream Plane 1.5.0 design tokens, so
colours, font weights, line heights and letter-spacing shift slightly across
the web app while its components stay the same; it now waits for its
translations before it hydrates. The `admin` and `live` application code is
unchanged. The installer change in this candidate, which prints the command
that starts the services after an upgrade, concerns Docker Compose; nothing
changes on Kubernetes. Rolling back to 0.3.0 needs no schema change and no
change to the values; page versions recorded on this release stay in the
database and stay readable, but 0.3.0 records no new ones.

Release 0.4.0-rc.1 adds no database or license migration compared with 0.3.0
and changes nothing in the chart's templates, values or Secrets. Upgrade from
0.3.0 with `helm upgrade` and `--version 0.4.0-rc.1`; Helm does not select a
release candidate otherwise. No other action is required. Two images change.
The `space` image, which serves the published boards, moves to the upstream
Plane 1.5.0 design on the Propel component library with its per-request nonce
Content-Security-Policy unchanged; its emoji picker reads its data from the
instance, never from a CDN, and the boards still show only the key, state,
priority, labels and due date. The `api` image's public board API
(`/api/public/`) no longer names project members: work items lose
`assignee_ids` and `created_by`, `anchor/<anchor>/members/` answers 404,
commenters, voters and reactors are reduced to `id`, `display_name`,
`avatar_url` and `is_bot`, and grouping by a person answers 400 while person
filters are ignored. That is a breaking change for any client of that API
outside Hangar's own Spaces. The `web`, `admin` and `live` application code is
unchanged. The installer change in this release, which makes an outdated
`setup.sh` refuse to upgrade, concerns Docker Compose and Swarm; nothing
changes on Kubernetes. Rolling back to 0.3.0 needs no schema change and no
change to the values, and brings back the previous board design and member
data.

Release 0.3.0 adds no database or license migration compared with 0.2.2 and
changes nothing in the chart's templates, values or Secrets; upgrade from 0.2.2
with `helm upgrade` and `--version 0.3.0` and no other action. Only God Mode,
served by the `admin` image, changes visibly: it moves to the upstream Plane
1.5.0 design on the Propel component library, with its secrets still
write-only, its secret fields no longer filled with a browser's saved password,
and its Content-Security-Policy unchanged. The `web` and `space` images are
rebuilt with Tailwind 4.2.4 without a visible change; the `api` and `live`
application code is unchanged. The installer fix in this release, which keeps
`plane.env` and its copies readable by the owner only, concerns Docker Compose
and Swarm; on Kubernetes the secrets are Kubernetes Secrets and nothing
changes. Rolling back to 0.2.2 needs no schema change and no change to the
values, and brings back the previous God Mode design. The release was tested
on a Docker Compose installation; Kubernetes was not installed on a cluster,
so the chart stays qualified for evaluation on AMD64 only.

Release 0.3.0-rc.2 adds no database or license migration compared with 0.2.2
or 0.3.0-rc.1 and changes nothing in the chart's templates, values or Secrets.
Upgrade from 0.2.2 or 0.3.0-rc.1 with `helm upgrade` and
`--version 0.3.0-rc.2`; Helm does not select a release candidate otherwise. No
other action is required. Only God Mode, served by the `admin` image, changes
visibly: it moves to the upstream Plane 1.5.0 design on the Propel component library, with
its secrets still write-only and its Content-Security-Policy unchanged, and
this candidate fixes its toasts, dialog close buttons and repeat-load hydration
error found in `0.3.0-rc.1`. The `web` and `space` images are rebuilt with
Tailwind 4.2.4 without a visible change; the `api` and `live` application code
is unchanged. The installer fix in this release, which keeps `plane.env` and
its copies readable by the owner only, concerns Docker Compose and Swarm; on
Kubernetes the secrets are Kubernetes Secrets and nothing changes. Rolling back
to 0.2.2 needs no schema change and no change to the values, and brings back
the previous God Mode design.

Release 0.2.2 adds no database or license migration compared with 0.2.1 and
changes nothing in the chart's templates, values or Secrets; upgrade from
0.2.1, 0.2.0 or 0.1.4 with `helm upgrade` and `--version 0.2.2` and no other
action. Only its `api` image changes: when God Mode clone detection fires
because a security key's signature counter goes backwards, Hangar now ends
every application and console session of that administrator instead of only
disabling the key, and the counter is checked under a row lock so that a copy
used at the same moment as the real key is caught. The event is now logged to
`plane.security` instead of `plane.exception`. An upgrade from 0.2.0 or 0.1.4
also brings everything 0.2.1 and 0.2.0 changed, described below. Rolling back
to 0.2.1 needs no schema change and no change to the values, but brings back
the session that survives clone detection and the race.

Release 0.2.1 adds no database or license migration compared with 0.2.0 and
changes nothing in the chart's templates, values or Secrets; upgrade from
0.2.0 or 0.1.4 with `helm upgrade` and `--version 0.2.1` and no other action. Its
`api` image moves to mistune 3.3.4, which fixes two quadratic-time denials of
service in Markdown parsing (GHSA-phmp-hrw4-r36r and GHSA-ww7q-mxrj-5ffg) that
let a signed-in user tie up an API worker's CPU. The God Mode `5198` reset hint
now names the administrator's address. The other changes concern only the
all-in-one image, which Kubernetes does not use. An upgrade from 0.1.4 also
brings everything 0.2.0 changed, described below. Rolling back to 0.2.0 needs
no schema change and no change to the values, but brings the mistune denial of
service back.

Release 0.2.0 adds no database or license migration compared with 0.1.4 and
changes nothing in the chart's values or Secrets. Its only template change is the object-storage
origins of the frontends' Content-Security-Policy described in
[Content-Security-Policy](#content-security-policy): a production install with
`pathStyle: false` now allows the endpoint origin the API signs, so browser
uploads and stored images load. Upgrade from 0.1.4 with `helm upgrade` and
`--version 0.2.0`; no other action is required. The `live` image moves to
Tiptap 3 and Hocuspocus 3.4, which also repairs real-time collaboration: on
0.1.3 and 0.1.4 the live server could not load or store a page, so concurrent
edits by two people were lost and pages were saved only by the browser's
fallback. Stored page documents do not change, and browser tabs opened before
the upgrade keep syncing, but should be reloaded. During the rolling update the
old and new `live` pods share Valkey for a short time; their channels and
message format are the same, but that mix is not tested upstream, so a page
edited in that window may need a reload. The `api` image is now built from a
hash-locked uv environment and contains no `pip`; it removes PostHog support, so
`POSTHOG_API_KEY` and `POSTHOG_HOST` are ignored. Rolling back to 0.1.4 needs no
schema change and no change to the values, but brings back the collaboration
bug and the blocked production uploads; if you roll back, ask users not to edit
the same page at the same time.

Release 0.1.4 adds no migrations and changes nothing in the chart's Secrets.
It adds one optional value, `application.numProxies`, rendered as `NUM_PROXIES`
in the API ConfigMap; its default, `null`, keeps the previous behaviour, so an
upgrade from 0.1.3 with `helm upgrade` needs no other action. Set it as
[Client IP and rate limiting](#client-ip-and-rate-limiting) describes once you
know how many proxies sit in front of the API. The release also stops accounts
bound to an identity provider from obtaining a local password; run
`python manage.py audit_user_identities --federated-with-password` in an API pod
after the upgrade to find passwords such accounts obtained earlier. Rolling back
to 0.1.3 needs no schema change, but remove `application.numProxies` from the
values first, because the 0.1.3 schema does not accept it, and the rollback
reopens those password paths.

Release 0.1.3 adds one migration, `db.0136`, which builds an index on intake
snooze times concurrently, without locking the table, and changes nothing in the
chart, its values or its Secrets; upgrade from 0.1.2 with `helm upgrade` and no
other action. It backports the upstream Plane 1.5.0 access-control fixes Hangar
did not yet carry, among them a page access check on every live collaboration
connection, so the `live` and `api` images must come from the same release, which
the chart already guarantees. Rolling back to 0.1.2 needs no schema change but
reopens those issues.

Release 0.1.2 adds no migrations and changes nothing in the chart, its values or
its Secrets; upgrade from 0.1.1 with `helm upgrade` and no other action. It
backports two upstream Plane authorization fixes: project members no longer read
or change each other's personal member settings (GHSA-gx67-r6wp-3357), and
project guests limited to their own work items can no longer download or copy
the files of other work items by asset ID (GHSA-wq96-4xjj-j4qg). Rolling back to
0.1.1 needs no schema change but reopens both.

Release 0.1.1 adds no migrations and changes nothing in the chart, its values or
its Secrets; upgrade from 0.1.0 with `helm upgrade` and no other action. Its
images are rebuilt with current Alpine packages, which fixes the `libpq`
findings the nightly scan reported in the 0.1.0 `api` image. The API now refuses
to start with an empty or published template `SECRET_KEY`, and Live with an
empty or template `LIVE_SERVER_SECRET_KEY`; the chart reads both from the
operator's Secret, so a deployment that followed the configuration reference is
unaffected. Each release also publishes a signed `SHA256SUMS`, a
`release-manifest.json` naming every image digest, and one SPDX SBOM per image,
alongside the chart. Rolling back to 0.1.0 needs no schema change.

Release 0.1.0 adds no migrations and changes nothing in the chart. It carries the
application code of rc.72 and is the first release published as stable rather
than as a pre-release, so the images gain a `stable` tag. Kubernetes support is
unchanged: the chart remains qualified for evaluation only. The Compose and
Swarm installers now prefer the newest stable release over later release
candidates; neither concerns the chart.

Release rc.72 also added no migrations and changed nothing in the chart. It removed
the placeholder origin, `https://hangar.example.com`, that the `web`, `admin`
and `space` images carried compiled in: the frontends now call the origin the
page was opened from unless the runtime `config.js` names one. The chart has
always set the origin through `config.js`, so Helm installs behave as before;
the change repairs Compose, Swarm and all-in-one installs, whose installers also
find and download the release again. A rollback to rc.71 brings the placeholder
back, which the chart overrides as before. The `beat-worker` pod now stops on
SIGTERM: its start script ran `celery beat` as a child that never received the
signal, so every rollout or drain waited the full termination grace period and
ended in SIGKILL.

Release rc.71 also added no migrations and changed nothing in the chart. Its images
carry current Alpine packages, which fixes `libxslt` (CVE-2026-87636,
CVE-2026-9947) in the `web`, `admin` and `api` images and `krb5-libs` in the
`api` image: release builds now upgrade the Alpine packages afresh instead of
reusing that step from the build cache. The `live` image moves to `effect`
3.22.4 and `@effect/platform` 0.97 (GHSA-chp3-j5qr-2vfr), whose affected cookie
helpers Hangar does not call. The other change, idling the bundled object
storage when `USE_MINIO=0`, concerns Compose and Swarm installs only.

Release rc.70 also added no migrations and changed nothing in the chart. It fixed the
profile overview ("Your work"), which failed to render for anyone assigned a
work item without a state; the user stats and the user's workspace dashboard summary no longer
return a `state_distribution` row whose group is null. The `proxy` image's
Caddy was rebuilt with `golang.org/x/net` 0.62.0, past CVE-2026-78661.

An upgrade from rc.68 or earlier also takes in rc.69, which adds migration `db.0135_remove_apitoken_is_service_and_allowed_rate_limit`,
which drops two unused API token columns and rewrites no rows; the release Job
applies it as usual. rc.68 loads both columns whenever it authenticates an API
key, and the migration Job runs alongside the rollout, so rc.68 pods still
serving once it has applied refuse API-key requests until they are replaced;
sessions are not affected. To roll back to rc.68, first run
`python manage.py migrate db 0134_reset_project_deploy_board_identity` in an
rc.69 API pod, then roll the release back. The reversal recreates both columns
with their former defaults. Between the two steps creating an API token fails on
rc.69, and an rc.69 pod that restarts waits for migrations, so keep that window
short. The `v1` state endpoints now refuse writes from project members who are
not admins, so an integration that manages states needs a project admin's token.
The object-storage credential change in rc.69 concerns the Compose and Swarm
bundles only; the chart already takes those credentials from the
`existingSecrets.objectStorage` Secret, and nothing in the chart changes.

An upgrade from rc.67 or earlier also takes in rc.68, which adds no migrations. It repairs `ext.0037`, shipped in rc.64, which
failed the release Job on every database holding a Workshop with
`AttributeError: type object 'Issue' has no attribute 'objects'`; the migration
is atomic, so such a deployment is still at `ext.0036` and the release Job
applies the rest.

An upgrade from rc.66 or earlier also takes in rc.67, which adds no migrations
either. The `space` and `live` images now carry
runtime dependencies only, and the instance-admin console's workspace create
refuses a `logo_asset`.

An upgrade from rc.65 or earlier also takes in rc.66, which adds no migrations
either. It tightens who may change assets: only a
project admin or a workspace admin changes a project's cover, changing a
project's attachments needs membership of that project (for a workspace admin
too), and a project or workspace accepts only its own cover or logo in
`cover_image_asset` or `logo_asset`. Nothing in the chart changes.

An upgrade from rc.64 or earlier also takes in rc.65, whose three changes can stop
a running deployment from working as before, so check them before upgrading:

- **A `rediss://` Valkey must present a certificate the API trusts.** Connections
  now verify the certificate and hostname. The chart cannot mount a CA bundle, so
  for a self-signed or private-CA Valkey add `ssl_cert_reqs=none` to the URL in the
  cache Secret, which turns certificate verification off again as a temporary
  measure ([production install](production-install.md)).
- **Cookie-authenticated writes must come from the instance's own origins.** A
  browser on another origin gets 403, and so does a client whose origin is missing
  from the base URLs.
- **`/api/instances/` answers only the sign-in configuration without a console
  session.** A monitor or script that read the version from it must sign in and
  read `/api/users/me/instance-config/`, or use the image's version label.

rc.65 also adds migration `0134` in the `db` application, which re-points any
project deploy board that names another project at its own, soft-deleting (and so
unpublishing) the extra board where the project already has one.

The evaluation profile's SeaweedFS rolls once on an upgrade from rc.64 or earlier (see
[Evaluation object storage](#evaluation-object-storage)).

Before upgrading, check that `hangar.publicOrigin` and the base URLs are the
origins users actually open. The Content-Security-Policy is enforced from this
release, and Chrome checks `form-action` on the redirect the API answers sign-in
with -- if those origins are wrong, the form is refused and sign-in silently does
nothing.

Basic calendar access continues to consume free/busy ranges. Optional invitation
recognition requires `calendar.events.readonly`, a separate trainer consent, and
workspace administrator rules configured in Team capacity. It reads times and
participation without requesting event titles or descriptions. Optional
materialization (`googleCalendarCapacity.materialization.enabled`, off by
default, and inert unless `googleCalendarCapacity.enabled` is also set)
additionally reads the title of events that already match a rule, for the
training report and the calendar import; the availability path is unchanged and
still requests none. Leaving it off does not hide those two screens — they are
reachable and empty, and every trainer is reported as never synced.

Recognition reads each trainer's own calendar for identity, under a mask that
requests no titles, because a shared calendar that hides its guest list gives the
API no attendees to match. Optional write-back
(`ENABLE_GOOGLE_CALENDAR_WRITEBACK`, off by default) additionally creates events
on the rule's calendar through an account a coordinator connects per rule.
Missing access or unverified configured calendars block new bookings. See the
[configuration reference](configuration.md#google-calendar-trainer-capacity) and
[planner setup](../capacity-planner.md) before enabling those rules.

## Support boundary

The evaluation profile passed an ephemeral-cluster exercise covering Restricted
Pod Security, migrations, HTTPS ingress, WebSockets, positive and negative
network-policy checks, dependency connectivity, object-storage persistence, an
atomic upgrade, rollback-on-failure behavior, uninstall, and retained PVCs.

The release workflow verifies anonymous access to the 0.1.0 chart archive, OCI
chart and digest-pinned images, and creates provenance attestations and keyless
Cosign signatures. No new live-cluster qualification is claimed for 0.1.0.

Production support remains blocked on production-profile installation and
application-flow testing, coordinated backup and restore, migration-failure
recovery, vulnerability and license review, and a completed support matrix. See
the [qualification checklist](../kubernetes-deployment-plan.md#release-qualification-checklist)
for the authoritative gate status.
