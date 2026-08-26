# Instance branding

The sign-in page is the one screen everyone sees, including people who have no
account yet. This is what an operator can change about it, and what stays fixed.

## What is configurable

All of it lives in **God Mode → Branding**, and every value is optional. An
instance that sets none looks exactly as it did before this existed.

| Setting                      | Effect when empty                |
| ---------------------------- | -------------------------------- |
| Logo                         | The Hangar wordmark              |
| `INSTANCE_BRANDING_NAME`     | The footer names no organisation |
| `INSTANCE_SIGN_IN_HEADER`    | "Work in all dimensions."        |
| `INSTANCE_SIGN_IN_SUBHEADER` | "Welcome back to Hangar."        |

The organisation name also replaces "Hangar" in the browser tab title.

## The logo is public, and validated accordingly

The sign-in page is rendered before anyone authenticates, so the logo has to be
readable without a session. That puts it in the same category as user avatars
rather than workspace logos: public and inline.

Because it is public, it is held to the same rules as the other inline images —
the file is validated as a raster image **server-side**, from its actual content
rather than the upload's declared type, and carries the current validation
marker. An asset that does not is not served. PNG, JPEG, WebP and GIF are
accepted.

Clearing the logo restores the wordmark. It unsets the pointer rather than
deleting the stored file, so an accidental click is recoverable.

## What was removed

The sign-in footer used to read "Join 10,000+ teams building with Hangar" above
the logos of Zerodha, Sony, Dolby and Accenture. Those are inherited Plane
marketing assets: companies that are not customers of your deployment and never
agreed to appear on its sign-in page. They are gone, replaced by a line naming
what the instance runs on and, if set, whose instance it is.

## Colours

`INSTANCE_ACCENT_COLOR` overrides `--brand-default` within the sign-in page, so
it recolours the sign-in button, links and focus outlines in one move.
`INSTANCE_LOGIN_BACKDROP_COLOR` fills the page behind the form, and behind the
background image where it does not cover.

Both must be a plain hex colour such as `#1d4ed8`. They are checked **on write
and again on read**, because they end up in a `style` attribute on the one page
that collects passwords — a value written straight into the database, or by an
older version before the check existed, is dropped rather than served.

There is no free-form CSS field, deliberately. A `url()` in a stylesheet makes
every visitor's browser fetch from wherever it points, handing their address to a
third party before they have signed in, and unbounded CSS can restyle a
password prompt into anything at all.

## Licensing

Hangar is AGPL-3.0-only. Presenting it under your own name and logo is permitted.

`INSTANCE_SHOW_LICENSE_NOTICE` controls whether the source offer appears on the
sign-in page. Turning it off **moves** the offer rather than removing it: the
link stays in the in-app help menu, which every signed-in person reaches, and
that one is not configurable. Section 13 of the AGPL requires that people using a
modified version over a network be offered its source, so a switch that removed
it everywhere would hand an operator a licence violation in one click.

Note for anyone upgrading: the notice used to appear **only** when neither a
terms nor a privacy URL was configured, so setting those silently dropped the
source offer. The two are now separate — legal links and the source offer render
independently.
