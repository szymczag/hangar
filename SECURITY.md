# Security policy

Hangar is an independent fork of [Plane](https://github.com/makeplane/plane). Hangar
vulnerabilities should not be sent to Plane’s security contact unless the issue has
also been confirmed in upstream Plane.

## Supported versions

Only the latest stable Hangar release receives security fixes. Prereleases
(`-alpha`, `-beta` and `-rc` versions) and `preview-*` images are for testing and are
not supported; upgrade to the latest stable release before reporting an issue found in
an older one.

A fix ships as a new patch release. Published release artifacts, Git tags and
versioned image tags are never overwritten; only the `stable` image tag moves to each
new stable release. A deployment pinned to a verified digest therefore keeps running
exactly what was verified, and picks up a fix by moving to the new release.

The container images of the latest stable release are scanned for known
vulnerabilities every night and again right after each release. Findings in operating
system packages inside the images are fixed by a new release, whose build refreshes
those packages; they are not patched into an existing release.

Before deploying, verify that an image was produced by the Hangar release workflow as
described in [Verifying release images](README.md#verifying-release-images)
(`cosign verify` against the release workflow identity).

## Reporting a vulnerability

Report vulnerabilities privately through
[GitHub Private Vulnerability Reporting](https://github.com/szymczag/hangar/security/advisories/new).
Include the affected revision, impact, reproduction steps, and any proposed mitigation.
Remove unrelated secrets and personal data from the report.

Hangar is maintained by a single maintainer. As a best-effort target, reports are
acknowledged within 7 days; the acknowledgement includes an initial assessment or the
questions needed to make one, and you will be kept informed until the report is
resolved.

If the vulnerability also affects upstream Plane, report it separately according to
[Plane’s security policy](https://github.com/makeplane/plane/blob/preview/SECURITY.md).

Please keep findings confidential until a fix is available. Do not access or alter
data beyond what is necessary for a proof of concept, and do not run disruptive tests,
social engineering, spam, or denial-of-service attacks against systems you do not own.

## Scope

In scope is code maintained in this repository, including fork-specific authentication,
epics, work-item properties, and worklog functionality.

Reports about upstream dependencies must demonstrate an impact on Hangar. Findings that
require physical access, a man-in-the-middle position, or attacks against unrelated
third-party deployments are out of scope.
