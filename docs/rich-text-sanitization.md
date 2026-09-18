# Rich-text sanitization

Descriptions, comments, pages and stickies are stored as HTML written by the
editor, but the API accepts that HTML from any client. Everything that stores it
runs it through one allowlist, `validate_html_content` in
`apps/api/plane/utils/content_validator.py`, built on
[nh3](https://github.com/messense/nh3) (Python bindings to the Rust `ammonia`
sanitizer, the server-side counterpart of DOMPurify).

## What the allowlist decides

- **Tags and attribute names.** Script, style, iframe, form and every `on*`
  handler are gone. URL attributes accept `http`, `https`, `mailto` and `tel`.
- **Attribute values.** nh3 does not look inside values, and some values are
  turned into styling or request paths by whoever renders the HTML, so
  `attribute_filter` checks them:
  - colour attributes (`data-text-color`, `data-background-color`,
    `data-background`, `background`, `textcolor`) accept palette keys only; the
    legacy form `var(--editor-colors-<key>-…)` is mapped to its key;
  - `data-text-align` accepts `left`, `center`, `right`;
  - `id`, `data-id` and mention identifiers must be UUIDs (other names can
    clobber globals in a page that renders the HTML);
  - `class` keeps editor-owned classes only (`editor-*`, `language-*`);
  - `image-component src` must be an asset id or an http(s) URL;
  - `input` can only be a checkbox; link targets are always `_blank`.
- **No `style` attribute.** The editor renders colour and alignment as data
  attributes styled by its stylesheet, which is also what lets the
  Content-Security-Policy refuse inline style (see
  [content-security-policy.md](content-security-policy.md)).

The editor checks the same values when it renders (`attribute-guards.ts` in
`packages/editor`). That matters for the collaborative page editor: its updates
travel between browsers through the live server and never pass the API, so the
editor is the one place every path goes through. A test keeps the palette keys
in `content_validator.py` equal to the editor's `COLORS_LIST`.

## Where it is applied

Audited on every model field that stores rich text and every code path that
writes one.

| Field                                                                         | Written by                                                                                                    | Sanitized                                                                                                                                                           |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Issue.description_html`                                                      | app, API v1, Spaces and epic serializers; intake create (app, API v1, Spaces) and intake edit                 | yes, in each serializer or view                                                                                                                                     |
| `IssueComment.comment_html`                                                   | app and API v1 comment serializers; Spaces comments (through the app serializer, body only); Todoist importer | yes                                                                                                                                                                 |
| `DraftIssue.description_html`                                                 | draft serializer                                                                                              | yes                                                                                                                                                                 |
| `Page.description_html`                                                       | page create, page edit, page description endpoint                                                             | yes                                                                                                                                                                 |
| `Sticky.description_html`                                                     | app and API v1 sticky serializers                                                                             | yes                                                                                                                                                                 |
| `Project.description_html`                                                    | app and API v1 project serializers                                                                            | yes                                                                                                                                                                 |
| `Module.description_html`                                                     | app module serializer (API v1 does not accept it)                                                             | yes                                                                                                                                                                 |
| `Description`, `DescriptionVersion`, `IssueDescriptionVersion`, `PageVersion` | copied from the rows above by tasks and model hooks                                                           | inherits                                                                                                                                                            |
| `IssueActivity.old_value` / `new_value` (comment, description)                | `issue_activity` task, from the request body                                                                  | yes, in the task for every call site                                                                                                                                |
| Notification e-mails                                                          | `email_notification_task`                                                                                     | yes, a narrower allowlist without `style`, `class`, `id`, forms or images, before the `\|safe` in the template; the whole message then passes `sanitize_email_html` |
| `Notification.message_html`                                                   | nothing writes it; the only update path accepts `snoozed_till`                                                | n/a                                                                                                                                                                 |
| AI assistant `response_html`                                                  | not stored; returned to the browser                                                                           | model output is escaped, only line breaks become `<br/>`                                                                                                            |
| Work item and project copies, seeds                                           | copy stored rows or bundled data                                                                              | inherits                                                                                                                                                            |

Stored HTML reaches readers through the editor (web and space), through the API
(integrations) and through notification e-mails. The editor would drop most of
what the allowlist removes; the API and e-mails would not, which is why every
write path sanitizes rather than relying on the editor.

## Rows written before the current rules

Rows stored before a rule existed keep what they were stored with. The command
below reports them, and rewrites them when asked:

```bash
python manage.py resanitize_rich_text           # report only; writes nothing
python manage.py resanitize_rich_text --apply   # rewrite the affected rows
```

It scans every field in the table above, including soft-deleted rows. A row is
counted as **affected** when sanitizing removes a tag or attribute or changes an
attribute value; a row whose only difference is serialization is reported but
never rewritten. The report names up to ten affected ids per field, so the
content can be looked at before `--apply`. Rewrites use `bulk_update`, so they
create no activity, version or notification.

Collaborative documents (`description_binary`) are not rewritten: changing a Yjs
document outside its editing session would give it a history the clients do not
share. The editor's render-time checks cover them.

## Object storage served on the application origin

Uploads are private and served through short-lived signed URLs with a forced
download disposition and `application/octet-stream`. The inherited
`manage.py update_bucket` command is the exception: meant for migrating old
public buckets, it sets a public-read policy on the whole bucket while it checks
permissions, then leaves every object that existed at that moment publicly
readable. Nothing in this repository runs it; it only runs by hand.

To check a deployment, read the bucket policy:

```bash
aws s3api get-bucket-policy --bucket <bucket> --endpoint-url <endpoint>   # S3-compatible
mc anonymous get <alias>/<bucket>                                          # MinIO client
```

"No policy" (or `NoSuchBucketPolicy`) is the expected state. A policy granting
`s3:GetObject` to `"Principal": "*"` means the command was run; remove it with
`aws s3api delete-bucket-policy` (or `mc anonymous set none`). Behind Caddy the
bucket route also sends `X-Content-Type-Options: nosniff` and
`Content-Security-Policy: sandbox`, so a public object cannot run as a page on
the application origin even then.
