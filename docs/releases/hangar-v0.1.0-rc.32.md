## Security and privacy

**Google sign-in does not work on `rc.30` or `rc.31`.** This release fixes it,
and the defect was ours rather than any provider's.

The hardened outbound transport keeps at most eight validated addresses as
connect candidates, and refused any host that resolved to more. That was written
as a bound on work and behaved as a rule about who may be talked to.
`www.googleapis.com` answers with eight A and eight AAAA records, so Google's
userinfo and JWKS endpoints were rejected before a connection was attempted, on
any deployment whose resolver returns both families.

The failure lands at the userinfo step, after the token exchange has already
succeeded — the account exists, the authorization code was valid, the network is
fine — and surfaces to the person signing in as `GOOGLE_OAUTH_PROVIDER_ERROR`.
Every external signal pointed at Google. Every resolved address is still checked,
so a reply mixing public and private addresses is refused as a whole and the
rebinding protection is unchanged; only how many are carried forward to connect
with is capped, and a reply beyond any plausible size is still refused outright.

A failing provider call is now diagnosable. One error code still reaches the
browser, deliberately, so the endpoint cannot be used to probe a deployment — but
the log now carries what was previously discarded. Providers name the problem
exactly through the `error` and `error_description` fields that OAuth 2.0 defines
for it, and `invalid_client`, `redirect_uri_mismatch` and `invalid_grant` are
each a specific misconfiguration an operator can go and correct; all of them
previously arrived as `Provider returned HTTP 400`. Only those two fields are
repeated, both truncated, and the request itself is still never logged: its body
carries the client secret and the authorization code, its headers the access
token.

Each record also carries `refused_by_egress_policy`, distinguishing a destination
this instance refused before anything left the network from a provider that did
not answer. The two arrive as the same exception types and previously logged the
same line, so a deployment problem an operator could fix was indistinguishable
from one they could not. OIDC had the same three call sites, one of which —
discovery — logged nothing whatsoever.

Colour values configurable for the sign-in page are validated as plain hex on
write and again on read. They reach a `style` attribute on the one page that
collects passwords, so a value written straight into the database, or by a
version predating the check, is dropped rather than served. There is
deliberately no free-form CSS field: a `url()` in a stylesheet makes every
visitor's browser fetch from wherever it points, handing their address to a third
party before they have signed in.

Uploading a project cover no longer fails with an answer that named nothing. An
identifier that cannot identify anything — the empty string the project-creation
form sends, since the project does not exist yet — reached a filter on a UUID
column and raised, which the generic handler reported as "Please provide valid
detail". Absent is now distinguished from unusable, and the unusable case names
the field.

## Migrations and compatibility

One migration, additive: `license.0015_login_page_appearance` seeds four
configuration keys. No data backfill, and no existing row is modified.

The sign-in page gains a background image, an accent colour and a backdrop
colour, all optional and all empty by default, so an instance that sets none
looks exactly as before. `INSTANCE_LOGIN_BACKGROUND` joins `INSTANCE_LOGO` as a
publicly served asset type, held to the same server-side raster validation as
the other public inline images.

`INSTANCE_SHOW_LICENSE_NOTICE` controls whether the AGPL source offer appears on
the sign-in page. Turning it off **moves** the offer rather than removing it: the
link remains in the in-app help menu, which every signed-in person reaches and
which is not configurable. Section 13 of the AGPL requires that people using a
modified version over a network be offered its source.

That setting also corrects existing behaviour worth knowing about: the notice
previously appeared **only** when neither a terms nor a privacy URL was
configured, so setting those silently dropped the source offer with nobody
deciding to. Legal links and the source offer now render independently.

The Branding page shipped in `rc.31` present, routed and working, but missing
from the God Mode menu — reachable only by typing `/god-mode/branding/`. It is
in the menu now.

Uploading a custom cover while creating a project is still not possible, and the
Upload tab no longer appears there rather than offering something that cannot
complete. A custom cover can be set from project settings once the project
exists.

Panel behaviour changes without any change to what is stored. The publication
workflow's artifact actions moved off Node 20, still pinned by full SHA.

The inherited Plane baseline remains final `v1.4.0` at commit `917b23a6`. The
qualification boundary remains Kubernetes 1.30 through 1.36 (including 1.36.2),
Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress with
WebSocket support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.32`, the chart version is `0.1.0-rc.32`, the
signed Git tag is `hangar-v0.1.0-rc.32`, and the OCI chart reference is
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.32`. `rc.31` is the immediately
previous complete publication. `rc.1`, `rc.2`, `rc.20`, `rc.24`, `rc.25`, and
`rc.28` were consumed by incomplete publication attempts and are not upgrade or
rollback targets.

## Known limitations and rollback

Hangar `rc.32` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

Three paths have complete automated coverage but no recorded manual
verification, and each should be exercised on a non-production instance first:
the WebAuthn flow against a hardware key in a browser, the console identity
import against a real directory export, and administrator-managed OpenPGP keys
against a real certificate. Google sign-in is fixed against a test reproducing
the exact resolver answer that broke it, but has not been confirmed end to end
against Google itself.

Neither `rc.31` nor `rc.30` is a useful rollback target for a deployment that
uses Google: both refuse Google's userinfo endpoint. `rc.31` is otherwise
structurally compatible — the added configuration rows can remain in place and
no migration needs reversing — so a rollback for an unrelated reason is
available, at the cost of returning Google sign-in to the broken state and
losing the diagnosis in the logs that would explain it.
