# Secure file uploads

Hangar uploads browser-selected files directly to the configured S3-compatible
object store. Browser-provided filenames, MIME types, sizes, and completion
requests are untrusted hints; they do not publish an object.

## Validation flow

1. The API sanitizes the filename, enforces `FILE_SIZE_LIMIT`, and derives a
   canonical MIME type from an explicit, case-insensitive extension allowlist.
2. The browser receives a presigned POST for a server-generated `pending` key.
   The policy fixes the key and Content-Type, limits the object to the declared
   size, and expires after ten minutes.
3. Completion performs an object HEAD, requires the exact declared size and
   Content-Type, and reads no more than 64 KiB under an ETag precondition.
4. `libmagic` identifies binary formats. Signatureless text formats require a
   textual UTF-8 prefix without NUL or excessive control characters.
5. The API conditionally copies the validated ETag to a new final key. Only
   that key is marked uploaded and attached to the application entity.

The staging key is deleted after its presigned credentials expire. A recurring
task removes abandoned pending assets and their objects after one hour.

## Rendering policy

Only validated JPEG, PNG, GIF, and WebP assets used as avatars, logos, or covers
are rendered inline. Attachments and all other formats are returned with
`Content-Disposition: attachment` and an `application/octet-stream` response
type. SVG, XML, JavaScript, and similar active formats therefore cannot execute
in Hangar's origin.

Public inline assets must carry the current server-generated validation-version
marker. Assets uploaded before this validation boundary was introduced are not
implicitly trusted from their old filename or client-supplied MIME metadata.
On first access, eligible legacy avatars, covers, logos, and project covers are
checked against their current object size, immutable ETag, filename policy, and
actual bounded content signature. A valid raster is copied conditionally to a
new immutable key with canonical metadata and marked with the current validation
version. Invalid, missing, active-content, or changed objects remain quarantined
and return `404`; their old object is never made public by the migration. When
no other database row references the old key, it is deleted after the maximum
signed-URL lifetime.
First access queues a deduplicated background revalidation and returns `404`
until that job succeeds, so anonymous requests never perform storage reads,
content inspection, or object copies synchronously. Operators can proactively
process the backlog with the management command before switching traffic.
The trusted validation state lives in a dedicated server-owned database column,
not in the legacy client-writable JSON metadata.
Policy-rejected legacy objects are marked as quarantined so repeated anonymous
requests cannot trigger repeated storage inspection. Transient storage failures
remain retryable.

Operators can pre-validate legacy public assets after deployment instead of
waiting for first access:

```sh
python manage.py revalidate_legacy_static_assets
```

Use `--limit N` to process a bounded batch. The command reports validated,
quarantined, and retryable objects separately and never promotes an object on a
storage or policy failure.

## Legacy multipart compatibility

The legacy workspace, user, and issue-attachment multipart URLs remain
available for older API clients. They now accept only the uploaded `asset` and
the minimum explicit entity context required by that URL. Client-supplied
publication flags, relationships, sizes, MIME attributes, storage metadata,
and object keys are rejected. Django validates the actual multipart filename,
size, canonical type, and bounded content before writing the object once to
the final private storage namespace.

The user legacy route accepts only avatar and cover images. Workspace entity
identifiers are resolved inside the authenticated workspace and, where
applicable, an actively accessible project. The issue legacy route resolves
the issue under the exact URL workspace and project before accepting bytes.
Operators should migrate integrations to the v2 direct-upload flow; the legacy
routes exist only as a constrained compatibility layer.

## Security boundary

This validation protects Hangar from MIME spoofing, active-content rendering,
cross-context publication, and post-validation replacement. It deliberately
does not claim that a downloadable attachment is malware-free. Deployments
that need malware classification must add a separately operated antivirus or
content-disarm pipeline before allowing users to download accepted files.

Completion is idempotent. It is limited to the uploader or an administrator
authorized for the same workspace/project/entity. Validation failures are
logged without filenames or file contents and return stable, non-sensitive
error codes to the client.

Legacy and current mutation routes share the same ownership boundary:
workspace logos require an active workspace administrator, project assets
require their creator or an active project/workspace administrator, and
restoring an asset applies the same checks as deleting it. Bulk association
fails closed unless every uploaded asset belongs to the caller, has one common
entity type, and the target entity has an active link to the URL project.
Private reads and downloads apply the corresponding active workspace/project
membership, page visibility, draft ownership, and user-profile ownership
checks. Server-side duplication accepts only a readable source carrying the
current trusted validation marker, copies it conditionally against its ETag,
and verifies the resulting size and canonical MIME type before creating the
new database row.
Entity association treats UUIDs as untrusted references: private drafts require
their creator, and public pages still require an active project link and
membership in that linked project. This applies consistently to current,
legacy multipart, bulk, duplicate, and draft-conversion paths.
Public Spaces and API downloads render raster content inline only when the
trusted database validation marker is current; historical unvalidated assets
remain available only as forced `application/octet-stream` attachments.

The pending-object sweep includes soft-deleted database rows, retains references
when object-storage deletion is partial or fails, and hard-deletes rows only
after storage confirms the full batch. OAuth avatar mirroring runs outside the
authentication request in a Celery task with soft and hard time limits; URL and
content validation remain unchanged, and the worker publishes the result only
if the user's remote avatar URL is still current.
