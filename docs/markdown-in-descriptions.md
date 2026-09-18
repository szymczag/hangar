# Markdown in descriptions and comments

Hangar accepts markdown in work item descriptions and comments, both in the
editor and through the API. This page says exactly what converts, what does not,
and what happens to HTML written inside markdown.

## In the editor

**Typing** markdown works as it always has: `# ` at the start of a line becomes a
heading, ` ``` ` opens a code block, `- ` starts a list, `**bold**` and
`` `code` `` apply as you finish them.

**Pasting** markdown now works from any source. Applications differ in what they
put on the clipboard: a terminal or a plain text editor writes text only, while a
browser, Notion, VS Code or Slack also writes an HTML version of the same
selection. Previously only the text-only case converted, which is why pasting
from a browser left a literal `#` behind.

A paste is read as markdown when all of the following hold:

- the clipboard carries plain text;
- its HTML version, if any, carries no formatting of its own — only the wrappers
  applications add around plain lines (`div`, `span`, `br`, `p`);
- the text contains at least one markdown construct;
- the cursor is not inside a code block, where text is always taken literally.

Otherwise the paste behaves exactly as before. So pasting a formatted paragraph
from a web page keeps its formatting, and pasting prose that merely mentions
`#42` keeps the `#`.

**"Paste without formatting"** — `Ctrl+Shift+V`, or `Cmd+Shift+V` on macOS — also
converts markdown, because the browser hands the editor the plain text only.
That shortcut is a browser feature and works in Chrome, Edge, Safari and
Firefox.

## Through the API

Work items and comments accept a markdown field alongside the HTML one. Send one
or the other: sending both is rejected with 400, because there is no sensible
way to merge them.

| Endpoint                                                                   | HTML field               | Markdown field               |
| -------------------------------------------------------------------------- | ------------------------ | ---------------------------- |
| `POST/PATCH /api/v1/workspaces/{slug}/projects/{id}/issues/`               | `description_html`       | `description_markdown`       |
| `POST/PATCH /api/v1/workspaces/{slug}/projects/{id}/issues/{id}/comments/` | `comment_html`           | `comment_markdown`           |
| `POST/PATCH /api/v1/workspaces/{slug}/projects/{id}/intake-issues/`        | `issue.description_html` | `issue.description_markdown` |

````bash
curl -sS -X POST \
  -H "X-API-Key: $HANGAR_API_KEY" \
  -H "Content-Type: application/json" \
  "$HANGAR_URL/api/v1/workspaces/$SLUG/projects/$PROJECT_ID/issues/" \
  -d '{
        "name": "Filed by a script",
        "description_markdown": "## Steps\n\n1. open the page\n2. press the button\n\n```\nTraceback ...\n```\n"
      }'
````

The field is write-only: responses carry the rendered `description_html`, and
`GET` never returns the markdown source. Markdown is rendered once, at write
time; editing the work item afterwards in the editor works on the rendered
content, as it does for any other work item.

Supported: headings, emphasis, strikethrough, inline and fenced code, ordered and
unordered lists, task lists, quotes, tables, thematic breaks, links and bare URLs.
Markdown source is limited to 1 MB.

## HTML written inside markdown

HTML inside markdown is escaped, not rendered: `<b>x</b>` in a markdown field
arrives as the literal text `<b>x</b>`. The rendered HTML then passes the same
sanitizer that hand-written `description_html` passes, which allows a fixed list
of tags and attributes and only the `http`, `https`, `mailto` and `tel` URL
schemes. A link written as `[click](javascript:alert(1))` loses its target.

Two consequences worth stating plainly:

- markdown is not a way to inject markup the HTML field would refuse;
- the sanitizer applies to what the API stores. Content written through the
  collaborative editor is persisted as a binary document that this sanitizer
  does not inspect, which is a known gap recorded in `sast/xss-results.md` and
  not addressed by markdown support.
