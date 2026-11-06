# Deploy Hangar on Kubernetes

Hangar publishes a Helm chart for Kubernetes at:

```text
oci://ghcr.io/szymczag/charts/hangar
```

The current release is `0.1.0-rc.68`. It is qualified for evaluation on
AMD64 Kubernetes clusters. It is not yet a supported production release.

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
through its generated, non-cacheable runtime `config.js`. Collaboration
WebSockets therefore use `/live/collaboration`, matching the chart proxy route
and the Live service. Published images also bake `/live` as a fallback, so a
missing runtime file cannot silently move collaboration traffic to the root.

Start with the [evaluation installation tutorial](evaluation-install.md) to
exercise the released chart. Use the [production installation guide](production-install.md)
only to review and help qualify the production profile.

## Compatibility

The `0.1.0-rc.68` qualification boundary is:

| Item                   | Qualified boundary                                               |
| ---------------------- | ---------------------------------------------------------------- |
| Kubernetes             | 1.30 through 1.36, including 1.36.2                              |
| Helm                   | 4.2                                                              |
| Inherited Plane source | `v1.4.0` (`917b23a6`, `package.json` version `1.4.0`)            |
| Node architecture      | `linux/amd64`                                                    |
| Pod Security Admission | Restricted                                                       |
| Ingress                | TLS-enabled controller with WebSocket support                    |
| Networking             | A CNI that enforces `NetworkPolicy`                              |
| Storage                | A default `StorageClass`, or explicit evaluation storage classes |

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

## Release identity

The product, chart, and Git identifiers are deliberately different:

| Identifier         | Current value                                |
| ------------------ | -------------------------------------------- |
| Product version    | `v0.1.0-rc.68`                               |
| Helm chart version | `0.1.0-rc.68`                                |
| Git tag            | `hangar-v0.1.0-rc.68`                        |
| OCI chart          | `ghcr.io/szymczag/charts/hangar:0.1.0-rc.68` |

`rc.1`, `rc.2`, `rc.20`, `rc.24`, `rc.25`, `rc.28`, `rc.33`, and `rc.59` were consumed
by incomplete publication attempts. `rc.59` carried the same changes as `rc.60` and
refused publication on an unsigned tag, so nothing was published under it.
Releases `rc.31` through `rc.38` are retired
after a repository-history privacy correction and are not supported
installation, upgrade, or rollback targets. `rc.64` through `rc.67` are **not
upgrade targets for a deployment that holds a Workshop**: their migration
`ext.0037` fails there, so upgrade to `rc.68` instead. `rc.67` is the
immediately previous retained GitHub release and the supported rollback target
for this one; rolling back to it needs no schema change. Rolling back to `rc.66`
needs none either and restores the larger `space` and `live` images. Rolling
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

- [Release `v0.1.0-rc.68` notes](../releases/hangar-v0.1.0-rc.68.md) — review
  security changes, migrations, compatibility, limitations, and rollback.
- [Install the evaluation profile](evaluation-install.md) — complete a first
  installation in a dedicated namespace.
- [Prepare the production profile](production-install.md) — configure external
  services and review the unsupported production path.
- [Configuration reference](configuration.md) — understand values, Secrets,
  routes, workloads, storage, and networking.
- [Operations](operations.md) — verify, upgrade, rotate credentials, back up,
  restore, roll back, and uninstall.
- [Security and artifact verification](security.md) — understand the security
  model and verify checksums, attestations, signatures, and anonymous access.
- [Troubleshooting](troubleshooting.md) — diagnose common installation and
  runtime failures without collecting credentials.
- [Chart source](../../charts/hangar/README.md) — chart-maintainer entry point.
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
The previous release is `0.1.0-rc.67`, tag `hangar-v0.1.0-rc.67`, and chart
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.67`. Anybody still on rc.62 with
calendar capacity enabled should leave it immediately: every Google request fails
on that release.

Release rc.68 adds no migrations. It repairs `ext.0037`, shipped in rc.64, which
failed the release Job on every database holding a Workshop with
`AttributeError: type object 'Issue' has no attribute 'objects'`; the migration
is atomic, so such a deployment is still at `ext.0036` and the rc.68 release Job
applies the rest. Nothing in the chart changes.

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

The release workflow verifies anonymous access to the rc.68 chart archive, OCI
chart and digest-pinned images, and creates provenance attestations and keyless
Cosign signatures. No new live-cluster qualification is claimed for rc.68.

Production support remains blocked on production-profile installation and
application-flow testing, coordinated backup and restore, migration-failure
recovery, vulnerability and license review, and a completed support matrix. See
the [qualification checklist](../kubernetes-deployment-plan.md#release-qualification-checklist)
for the authoritative gate status.
