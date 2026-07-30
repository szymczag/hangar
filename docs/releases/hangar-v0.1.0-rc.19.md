## Security and privacy

`rc.19` establishes a server-enforced trust boundary for every current and
legacy file-upload path. Browser filenames, MIME types, sizes, entity UUIDs,
completion requests, and object-storage metadata are treated as untrusted.
Direct uploads use short-lived presigned policies for server-generated pending
keys; completion verifies the exact object size, canonical MIME type, bounded
content signature, and immutable ETag before conditionally copying the object
to its final key. Legacy multipart routes apply the same filename, size, MIME,
content, workspace, project, and entity authorization policy before publishing
an object.

Only server-validated raster avatars, covers, and logos can render inline.
Attachments and other formats are forced to download as
`application/octet-stream`; SVG, XML, JavaScript, MIME-spoofed files, and
historical objects without the current validation marker cannot execute in the
Hangar origin. Eligible historical public rasters are revalidated and
immutably republished asynchronously, while rejected objects remain
quarantined.

Asset reads, downloads, duplication, completion, association, deletion, and
restoration now share explicit ownership and active-membership checks. Private
pages and drafts retain their visibility boundaries. Project-cover mutations
require an active project member or administrator; project guests are rejected
on current, legacy, duplicate, bulk, completion, delete, and restore paths. A
bulk cover update rechecks the role under database row locks before changing
shared project state.

Server-side S3-compatible HEAD, GET, COPY, upload, and delete operations always
use the configured internal endpoint. Browser presigning uses the configured
public endpoint, or the trusted `WEB_URL` MinIO compatibility fallback. An
untrusted request `Host` header cannot select an outbound object-storage
destination.

The security review mapped 35 changed authentication surfaces and 25 outbound
request sinks. Independent missing-authorization and SSRF verification found
no remaining project-guest bypass or request-controlled storage destination.
Path-traversal review classified all 12 changed candidates as not vulnerable,
and no changed remote-code-execution sink was found. The focused upload and
storage suite passed 125 tests; the complete API, migration, lint, CodeQL, and
build workflows passed both on the pull request and on its exact merge commit.

## Migrations and compatibility

`rc.19` adds Django migration
`0128_fileasset_upload_validation_version`. It adds a non-null small-integer
validation marker with default `0`; it does not rewrite existing object data.
The Helm migration Job must complete before application traffic is admitted.
Do not deploy a mixture of `rc.18` and `rc.19` API, worker, or frontend images.

After the migration, proactively process historical public avatars, covers,
logos, and project covers from an API container:

```sh
python manage.py revalidate_legacy_static_assets
```

Use `--limit N` for controlled batches. The command reports validated,
quarantined, and retryable objects without logging filenames or content.
Until an eligible legacy object is successfully revalidated, its public request
returns `404`; ordinary attachments remain downloadable only under the forced
attachment policy.

Existing `rc.18` Helm values remain structurally compatible. Operators using
external MinIO or another S3-compatible service must verify that the internal
endpoint is reachable only by the application workloads and that
`AWS_S3_PUBLIC_ENDPOINT_URL` is the browser-facing origin. MinIO compatibility
deployments may instead use the trusted `WEB_URL`. Keep anonymous bucket access
disabled and test a representative upload, completion, download, rejection,
and legacy-image revalidation after rollout.

There is no Helm values, Secret, Kubernetes resource, RBAC, or network-policy
contract change. The inherited Plane source remains `v1.4.0-rc2`, whose root
`package.json` reports version `1.4.0`.

The qualified boundary remains Kubernetes 1.30 through 1.36, including 1.36.2,
Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress with
WebSocket support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.19`, the chart version is
`0.1.0-rc.19`, the signed Git tag is `hangar-v0.1.0-rc.19`, and the OCI
chart reference is `ghcr.io/szymczag/charts/hangar:0.1.0-rc.19`.
`rc.18` is the immediately previous complete publication.

## Known limitations and rollback

The inherited Plane version and Hangar `rc.19` remain prereleases qualified for
evaluation rather than production. Published images are AMD64-only. Content
validation prevents active-content execution and MIME spoofing; it does not
claim that accepted downloadable attachments are malware-free. Deployments
requiring malware classification need a separately operated antivirus or
content-disarm pipeline.

There is no security-equivalent rollback target among the earlier release
candidates. An emergency application rollback can leave the additive
`upload_validation_version` column in place, but rolling back to `rc.18` or
earlier restores the upload and authorization weaknesses corrected here.
Perform such a rollback only for availability recovery after disabling uploads
and isolating object-storage access, then return to `rc.19` as soon as possible.
Restore the pre-upgrade database backup only when unrelated writes, corruption,
or the incident requires point-in-time recovery; the additive migration alone
does not require a restore.
