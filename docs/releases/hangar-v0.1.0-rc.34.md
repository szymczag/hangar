## Security and privacy

**Auto-join has never worked on any instance configured from God Mode.** The
defect shipped in `rc.32` and was ours. The domain policy editor serialised the
workspace role as a number — `corp.com=example:5` — while the server accepted
role names only. An entry naming a role the parser does not recognise is
discarded whole, deliberately, so that an unknown role can never become a
privileged one. The consequence was that every policy saved from the panel was
thrown away in silence: no membership was created, no error was shown, and the
page continued to display the configuration it had just written.

The panel now writes names, the server accepts both names and the known numeric
values so instances already holding the broken format recover on their own, and
a test compares the two sides directly — it fails if the format the panel writes
ever stops being one the parser reads.

The same editor had three further faults, each losing configuration without
saying so. It kept one row per domain while the server accumulates several, so
saving from the panel deleted every additional workspace mapping for that
domain. It matched only numeric roles when reading, so a policy written as
`:member` displayed as Guest and was rewritten as Guest on the next save — a
silent demotion. And it listed only the first page of workspaces, so on an
instance with more than ten the intended workspace was absent from the menu
entirely, which is what an operator sees as being unable to change it.

Eleven authentication error codes had no message anywhere in the web app.
`authErrorHandler` returned undefined for them, so no banner rendered and the
person was returned to the sign-in page with nothing but a number in the URL;
the "Something went wrong." fallback did not apply, because the banner list
gates the fallback too. `SSO_ACCOUNT_LINK_REQUIRED` was among them: the instance
refused a sign-in for a reason an administrator could act on, and told the
person nothing at all. Each now explains the situation and names the code to
pass on. A test compares the two sides by code number rather than by name,
because they spell several of them differently.

An administrator can now authorise existing accounts to be linked by pasting
email addresses. Sign-in refuses to match an account by address, because an
address proves nothing — the binding key is a digest over provider, issuer,
subject format and subject, and the email takes no part in it. Obtaining each
person's Google `sub` claim requires the Admin SDK, which is why the existing
CSV import was out of reach for most operators.

This relaxes that rule narrowly rather than removing it. Nothing is linked in
advance: the record states only that the next assertion from a named issuer for
that address may bind whatever subject it actually carries. Four conditions must
hold together at sign-in — an unspent and unexpired authorisation, a domain
pinned in `SSO_ENFORCED_DOMAINS` to that provider, an address the provider has
verified, and an account with no existing identity at that issuer. Domain
pinning is the one the rest rests on: without it, authorising a `gmail.com`
address would mean trusting whoever answers for `gmail.com`. Authorisations
expire after fourteen days, so a list nobody acted on stops being a way in.
Issuing them requires the console's second factor and the administrator's
password at the point of use, and every link writes an immutable record of who
authorised what and which subject was ultimately bound.

Sign-in through Google no longer forces the consent screen on every attempt.

Five packages carried vitest suites that no workflow had ever run: `apps/web`,
`apps/live`, `packages/editor`, `packages/codemods` and `packages/utils`. They
passed once, when someone ran them by hand, and nothing would have reported it
had they stopped. They run on every pull request now.

## Migrations and compatibility

Two migrations, both additive. `ext.0014_federated_link_authorization` creates
the authorisation and audit tables described above. `license.0016_google_auto_redirect`
seeds one configuration key. No data backfill, and no existing row is modified.

**An account that auto-join had already admitted to a workspace could not get
past onboarding.** The first step was chosen once, from an effect that ran
before the workspace list had loaded, and it consulted only the recorded
onboarding steps — never the memberships that actually exist. Auto-join creates
a `WorkspaceMember` directly and issues no invitation, and the onboarding screen
chooses between joining and creating by counting invitations. So an account that
had been admitted was shown the create-a-workspace screen, and on an instance
with `DISABLE_WORKSPACE_CREATION=1` there was no way forward from it. Onboarding
now settles when a membership exists, and reacts to the workspace list arriving.

Onboarding also stopped offering what the instance will not honour. The optional
password block appeared for everyone whose password was auto-set, which is
everyone who arrived through SSO — including on instances where password sign-in
is disabled and the password could never be used to sign in. It is now shown
only where password sign-in is enabled.

Where attribute sync is on for the provider an account signs in through, the
name field is read-only and explains why: the provider overwrites it on every
sign-in, so an edit made there would be undone by the next login without
explanation. The avatar control is hidden rather than disabled, because sync
deletes an uploaded avatar from object storage outright — offering the control
would be offering to lose the file. Operators enabling `ENABLE_GOOGLE_SYNC` or
its siblings should know that this removes avatars people have already uploaded.
Which providers have sync enabled is now reported by the instance endpoint;
nothing else about what is stored has changed.

An instance whose only enabled sign-in method is Google can send people straight
to Google rather than presenting a page with a single button. It is off by
default, and does not engage when an error is being shown or after an explicit
sign-out, so an account can still reach the page to see why it was refused.

The inherited Plane baseline remains final `v1.4.0` at commit `917b23a6`. The
qualification boundary remains Kubernetes 1.30 through 1.36 (including 1.36.2),
Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress with
WebSocket support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.34`, the chart version is `0.1.0-rc.34`, the
signed Git tag is `hangar-v0.1.0-rc.34`, and the OCI chart reference is
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.34`. `rc.32` is the immediately
previous complete publication. `rc.1`, `rc.2`, `rc.20`, `rc.24`, `rc.25`,
`rc.28`, and `rc.33` were consumed by incomplete publication attempts and are
not upgrade or rollback targets.

## Known limitations and rollback

Hangar `rc.34` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

Rolling back to `rc.32` returns auto-join to the state where nothing configured
from the panel takes effect, and returns the refused sign-ins to explaining
nothing. It is otherwise available: both migrations are additive, so the added
tables and configuration row can remain in place and neither needs reversing. An
instance that has issued link authorisations should treat a rollback as leaving
them unspendable rather than as revoking them — `rc.32` does not read those
rows, and returning to `rc.34` makes any that have not yet expired spendable
again.

`rc.33` published nothing. Its tag exists and its notes do not, which is exactly
why: the publication workflow refused it at the first validation gate, before
any image, signature or attestation was produced. It is not installable and is
not a rollback target.

Two paths in this release have automated coverage but no manual verification
against a real deployment, and each should be exercised on a non-production
instance first: linking by authorised address end to end against Google, and
the automatic redirect on an instance where Google is the only enabled method.
