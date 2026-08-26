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

## Licensing

Hangar is AGPL-3.0-only. Presenting it under your own name and logo is
permitted; the licence's requirement that the corresponding source remain
available to the people using the instance is unaffected by anything on this
page.
