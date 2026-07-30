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
