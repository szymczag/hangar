## Security and privacy

**Microsoft Clarity is gone rather than switched off.** Upstream loads a session
recorder from `clarity.ms` behind an environment flag. It was the only executable
code in the application fetched from a host the instance does not run — everything
else that leaves is a link somebody has to click. Off by default is not the same
as absent: the code sat one environment variable away from sending every
signed-in person's address, and whatever the recorder chose to collect, to a third
party, inside deployments whose point is that their contents stay in the building.
The switch is deleted along with the code, because leaving the switch is leaving
the code, and a test now holds an empty allow-list of script hosts.

**An invitation is retired once the membership it offered exists.** Invitations
were consumed only when accepted through the emailed link. Somebody invited by
address who signed in through their identity provider instead never accepted one —
auto-join adds the membership directly — so the invitation stayed outstanding and
the person appeared under Members and Pending Invites at the same time.

That is not only untidy. An unaccepted invitation remains usable until it expires,
so once the person is removed from the workspace it is a way back in that nobody
granted. A membership that has been **deactivated** deliberately does not retire
an invitation, because that is exactly the case where someone may need to be let
back in. A migration retires the ones already outstanding, matching only where the
address is an active member of the very workspace the invitation names.

**An instance can refuse to let anything be read from outside it.**
`FORCE_PRIVATE_VISIBILITY`, off by default and set in God Mode, keeps pages and
views to the project they belong to and refuses to publish anything to the
internet. It is a refusal rather than a default: the choice is not offered and not
accepted, and requested values are overwritten rather than rejected so an older
client produces a private object instead of an error it will not act on.

Publishing has no per-object value to force — a board either serves or it does
not — so it is refused where a board is created and again at the single point
every public request passes through. Nine views on that surface filter on a
disabled flag today; a tenth that forgot would serve exactly what the instance
said must not be served.

Note that `Page.access` numbers public as `0` while `IssueView.access` numbers
private as `0`. One "make it private" value applied to both would publish one of
them, so each is named separately and a test compares it against its own model's
choices.

A project's own network setting is deliberately **not** governed. It decides
whether members of a workspace can discover a project they have not been added to,
not whether outsiders can read it.

## Migrations and compatibility

Four migrations. Three seed configuration keys and change nothing else. The
fourth, `db.0130`, retires invitations as described above.

**Three changes are visible to the people using an instance.**

`INSTANCE_SHOW_EXTERNAL_LINKS` is **off by default**, so "Star us on GitHub"
disappears from the header and the invitation page, along with the release-notes
and documentation buttons in the Hangar Community dialog and the issue-tracker
links. Hangar is deployed inside organisations, where a link to a code-hosting
site is a link out of the building for somebody who did not ask to leave it. The
AGPL section 13 source offer is **not** covered by this setting and is never
hidden; point `HANGAR_SOURCE_URL` at an internal mirror to keep even that inside.
The startup-failure page and the production error boundary keep their links, since
they render when no configuration can be read and are seen by whoever is fixing
the instance.

The startup-failure page and the crash page no longer tell people to open a
public issue. `INSTANCE_SUPPORT_TEXT`, set on the Branding page, is what they show
instead — a help desk, an extension number, whatever the operator puts there. Left
empty they say only that something went wrong and offer no destination at all.

Those pages render precisely when the configuration endpoint could not be reached,
so they cannot ask what to say. The answer is kept from the last time the instance
could be asked and read back from there. Anyone who has opened the application
before has it; a first-time visitor arriving during an outage gets the neutral
wording and no links. The crash page keeps its source link either way, for the
same section 13 reason as everywhere else.

New accounts now start on **Monday** rather than Sunday, on a **light theme**
rather than whatever the operating system is set to, and in whichever timezone the
operator names. These are starting values and not rules: everyone changes their
own afterwards, and changing the instance setting does not reach back into
accounts that already exist. Nothing changes for anyone who already has an
account.

**Onboarding no longer appears when it would ask nothing.** Somebody admitted by
auto-join whose provider supplies their name still landed on the onboarding
screens, which rendered a profile form and navigated away once loaded — a visible
flash of a name field and avatar picker offering exactly what recent releases made
read-only. The sign-in workflow now marks such an account onboarded outright,
because the application routes on that flag rather than on the individual steps,
and the screens no longer render a step before one has been chosen. Accounts whose
provider has attribute sync switched off still see the step, because nobody else
supplies their name.

The pending invites section on workspace member settings stopped opening onto
nothing. It nested a second panel inside a component that already provides one,
and the inner panel followed a different open state that starts closed.

The inherited Plane baseline remains final `v1.4.0` at commit `917b23a6`. The
qualification boundary remains Kubernetes 1.30 through 1.36 (including 1.36.2),
Helm 4.2, `linux/amd64`, Restricted Pod Security Admission, TLS ingress with
WebSocket support, a `NetworkPolicy`-enforcing CNI, and persistent storage.

The product version is `v0.1.0-rc.37`, the chart version is `0.1.0-rc.37`, the
signed Git tag is `hangar-v0.1.0-rc.37`, and the OCI chart reference is
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.37`. `rc.36` is the immediately previous
complete publication. `rc.1`, `rc.2`, `rc.20`, `rc.24`, `rc.25`, `rc.28`, and
`rc.33` were consumed by incomplete publication attempts and are not upgrade or
rollback targets.

## Known limitations and rollback

Hangar `rc.37` remains a prerelease qualified for evaluation rather than
production. Published images are AMD64-only. The production-profile install,
backup and restore, migration-failure recovery, vulnerability and license
approval, and full support matrix remain open qualification gates.

Rolling back to `rc.36` restores the outbound links and the session recorder's
switch, and returns invitations to outliving the memberships they granted. The
invitations already retired stay retired: what was consumed is recorded as
consumed, and `rc.36` reads that the same way. Configuration keys seeded here are
ignored by `rc.36` rather than misread, and no schema changes need reversing.

An operator who turns `FORCE_PRIVATE_VISIBILITY` on should know that bringing
existing pages and views into line is **one-way**. What each was readable by is
not recorded, because a table describing what to re-expose is the opposite of what
turning the policy on asks for. Published boards are disabled rather than deleted,
so their addresses cannot later be reissued for unrelated content.

The timezone picker in personal preferences opens and selects correctly, but its
search field cannot be focused. It is known and not fixed here.
