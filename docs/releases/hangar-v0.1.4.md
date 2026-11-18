## Security and privacy

**Accounts that sign in through SSO can no longer obtain a Hangar password.**
Changing the password of an account bound to an identity provider was already
refused, but such an account could still set a first password, or ask for a
reset link and use it. A local password signs in without the provider, so its
second factor, lockout and deprovisioning stop being the only way in. Setting a
password, asking for a reset link and using one are now all refused for these
accounts with `PASSWORD_MANAGED_BY_IDENTITY_PROVIDER` (`5132`). The
forgot-password form answers exactly as it does for any other address, so it
does not reveal which accounts are federated, and a reset link issued before the
identity was linked is refused even though it is otherwise valid. Onboarding no
longer offers these accounts the password step.

A password an account already holds keeps working for sign-in. Run
`python manage.py audit_user_identities --federated-with-password` after
upgrading and clear the passwords it lists, as described in
[Federated accounts that still hold a password](../federated-sso-security.md#federated-accounts-that-still-hold-a-password).

The all-in-one image no longer trusts the emSign ECC Root CA - G3 outside the
system certificate store; see below.

## Migrations and compatibility

This release adds no database migrations. Nothing changes in the Helm chart's
Secrets; the chart gains one optional value, described below, whose default
keeps the previous behaviour. Upgrade from `0.1.3` with the `0.1.4` `setup.sh`
or `swarm.sh`, or with `helm upgrade` on Kubernetes.

**The all-in-one image runs the API again.** The all-in-one images `0.1.0`
through `0.1.3` lacked `libmagic` and `gnupg`. Without `libmagic` the API could
not import its views and failed with `ImportError: failed to find libmagic`;
without `gnupg` OpenPGP-encrypted mail could not be sent. Both are installed
now, together with the rest of the API image's runtime packages, and a test
keeps the two images' package lists aligned. Everybody running the all-in-one
image should upgrade to `0.1.4`. Docker Compose, Docker Swarm and Kubernetes
use the API image, which was not affected.

**The Helm chart can set the number of trusted proxies.** The new value
`application.numProxies` (`null`, or `0` through `10`) is rendered as
`NUM_PROXIES` in the API ConfigMap and tells the API how many proxies append to
`X-Forwarded-For`, which it uses to identify clients for the sign-in rate
limits. Set it to `1` when clients reach the ingress controller or Gateway
directly, plus one for each load balancer or CDN in front of it. The default,
`null`, keeps the previous behaviour. See the
[Kubernetes configuration reference](../kubernetes/configuration.md#client-ip-for-rate-limits).

**Live gets 30 seconds to save open pages when Docker Compose stops it.** The
`live` service now has `stop_grace_period: 30s`, so a restart or upgrade no
longer kills it before it has written the documents still open.

**The all-in-one image no longer trusts certificates outside the system
store.** gRPC, used by the OpenTelemetry exporter, read its own bundled root
list, which still trusted the emSign ECC Root CA - G3; it now reads the system
CA bundle, which the image's OS updates keep current. `pip`, whose vendored
`certifi` trusted the same root
([GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2)), is
removed from the image after installation.

Other changes for operators and developers:

- The Compose and all-in-one READMEs and the bug report form are updated:
  `setup.sh` takes its action as an argument and exits after one action, and
  the Swarm, HTTPS, external service, SMTP, backup and restore notes are
  corrected.
- The API carries a migrations lockfile, and pull requests now fail when a
  migration is missing from it, when an app gains a second leaf, or when two
  migrations of one app share a number.
- Automated tests now guard each of Hangar's own security controls, so that a
  later upstream sync cannot drop one without failing.

Upgrade from `0.1.3`. An upgrade from `0.1.3` to this release, followed by a
restore of its backup into a new installation, is tested as part of the release.

Product version is `v0.1.4`, Git tag `hangar-v0.1.4`, Helm chart version
`0.1.4`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.1.4`.

## Known limitations and rollback

The Kubernetes production profile has still not completed qualification, so do
not run the chart in production yet. The all-in-one image does not send
`Strict-Transport-Security` itself; put it behind a proxy that does. Hangar is
still based on upstream Plane 1.4.0 with the 1.4.3 changes backported; the
upstream 1.5.0 interface and its other features are not included. Passwords
federated accounts obtained before this release are reported, not removed; an
operator has to clear them.

**Rolling back to `0.1.3`** needs no schema change: only the images change.
Rolling back reopens the password paths above for federated accounts. Do not
roll an all-in-one installation back to `0.1.3` or earlier: those images cannot
run the API. On Kubernetes, remove `application.numProxies` from your values
before rolling back the chart, because the `0.1.3` schema does not accept it.
