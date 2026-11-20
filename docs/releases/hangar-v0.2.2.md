## Security and privacy

**A cloned God Mode security key now ends every session of its administrator.**
God Mode treats a security key whose signature counter goes backwards as copied.
On `0.2.1` it disabled the key and nothing more, so a session already opened
with the copy, by whoever used it first, stayed signed in until it expired.
Hangar now also ends every session of that administrator, in the application
and the console, and clears the pending sign-in that presented the copy, in one
transaction with disabling the key. The response is unchanged, so a clone
cannot tell that it was caught. The event is now logged as a warning to
`plane.security`, with the key id and the number of sessions ended; on `0.2.1`
it went to `plane.exception`, so move any alert that matched the old log line.
See [God Mode second factor](../god-mode-second-factor.md#when-a-key-is-disabled).

**A copied key used at the same moment as the real one is caught.** The counter
check read the stored counter without a lock, so two sign-ins with the same key
at the same time could both pass it, and a copy used alongside the real key
went unnoticed. The check now runs under a row lock, in one transaction with
the sign-in: the second sign-in waits for the first and is caught.

The shell reset `disable_instance_admin_2fa` now ends sessions through the same
code; what it does is unchanged. Its `--keep-sessions` help now says that it
keeps all of the user's sessions, which is what it always did.

## Migrations and compatibility

This release adds no database or license migration compared with `0.2.1`, and
the migrations lockfile is unchanged. The Helm chart's templates, values and
Secrets do not change, and neither do the Compose and Swarm deployment files or
the all-in-one image beyond the API change above.

Upgrade from `0.2.1`, `0.2.0` or `0.1.4`. The installers pick the newest stable
release on their own: run `./setup.sh upgrade` (or `swarm.sh upgrade`) with the
`0.2.2` script. Use the `v0.2.2` all-in-one image, which the `stable` tag now
also points to, or run `helm upgrade` with `--version 0.2.2` on Kubernetes. No
other operator action is required. An upgrade from `0.2.0` or `0.1.4` also
brings what the [`0.2.1` notes](hangar-v0.2.1.md) and the
[`0.2.0` notes](hangar-v0.2.0.md) describe; read them first.

Product version is `v0.2.2`, Git tag `hangar-v0.2.2`, Helm chart version
`0.2.2`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.2.2`.

## Known limitations and rollback

The interface is still the Plane 1.4 design: the upstream 1.5.0 Propel redesign
is not included, and whether to adopt it is still to be decided. The recorded
upstream base stays Plane 1.4.0 with the 1.4.3 changes backported. On
Kubernetes this release is qualified for evaluation on AMD64 only: the
production profile has still not completed qualification, so do not run the
chart in production yet. The all-in-one image does not send
`Strict-Transport-Security` itself; put it behind a proxy that adds it if you
need it.

**Rolling back to `0.2.1`** needs no schema change and no change to the Helm
values: only the images change. An all-in-one installation that follows the
`stable` tag has to name `v0.2.1` to roll back, because `stable` now points to
`0.2.2`. Rolling back brings back the session that survives clone detection
and the race in which a copy used at the same moment as the real key goes
unnoticed.

**Rolling back further, to `0.2.0` or `0.1.4`,** also brings back what `0.2.1`
fixed, and on `0.1.4` the collaboration bug in which concurrent edits to one
page are lost; see the
[`0.2.1` notes](hangar-v0.2.1.md#known-limitations-and-rollback) and roll back
that far only if you need to.
