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

## Links to places this instance does not run

`INSTANCE_SHOW_EXTERNAL_LINKS`, off by default and set on the Branding page,
decides whether the application may point anyone at a host the operator does not
run. Off, it hides "Star us on GitHub" in the header and on the invitation page,
the release-notes and documentation buttons in the Hangar Community dialog, and
the issue-tracker links.

Off by default because of where Hangar is deployed. Inside an organisation, a
link to a code-hosting site is a link out of the building for somebody who did
not ask to leave it, and following it tells the far end who is looking and from
where.

### The source offer is not covered

The AGPL-3.0 section 13 offer is never hidden by this setting. Anyone running a
modified version over a network owes it to the people using that version, and a
branding switch is not a reason to stop owing it.

An operator who wants that link to stay inside their network points
`HANGAR_SOURCE_URL` at their own mirror of the source. The link already reads
from there, so nothing else needs changing — the obligation is met and nobody
leaves the building.

### The failure pages say what you tell them to

`INSTANCE_SUPPORT_TEXT` is what the startup-failure page and the crash page show.
Set it to your own help desk. Left empty, those pages say only that something went
wrong and offer no destination at all.

These pages render precisely when `/api/instances/` could not be reached, so they
cannot ask what to say. The answer is therefore **remembered** from the last time
the instance could be asked, and read from there. Anyone who has opened the
application before has it. A first-time visitor arriving while the instance is
down gets the neutral wording and no links, which is the right thing to show
somebody the instance knows nothing about.

They were originally exempt from the setting above, on the reasoning that they are
seen by whoever is fixing the instance. That was wrong: on a deployment inside a
company they are what every member of staff sees the moment their tools stop
working, which is the worst possible time to be inviting them to file a public bug
report.

The crash page keeps the source link either way, for the same section 13 reason as
everywhere else — a page rendering after a crash is still a modified version being
run over a network.

A contract test holds all of this with **no exemptions**, so a link added later
has to be gated or be the licence offer.

