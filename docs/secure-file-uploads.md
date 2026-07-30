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
and return `404`; their old object is never made public by the migration.
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
