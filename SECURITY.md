# Security policy

Hangar is an independent fork of [Plane](https://github.com/makeplane/plane).
**Do not report Hangar vulnerabilities to Plane's security contact** — issues
in this fork are not their responsibility.

## Reporting a vulnerability

Report vulnerabilities privately through
[GitHub Private Vulnerability Reporting](https://github.com/szymczag/hangar/security/advisories/new)
on this repository. Include everything needed to reproduce and assess the
issue.

If the vulnerability also affects upstream Plane, please additionally report
it to [security@plane.so](mailto:security@plane.so) following
[their policy](https://github.com/makeplane/plane/blob/preview/SECURITY.md).

Please practice responsible disclosure: keep findings confidential until a fix
is available, do not exploit vulnerabilities beyond what is needed for a proof
of concept, and do not run disruptive tests (DDoS, spam, social engineering)
against instances you do not own.

## Scope

In scope: the code in this repository — fork-specific features (SSO, epics,
issue types, worklogs) are the most valuable targets, as upstream code is also
covered by Plane's own program.

Out of scope: vulnerabilities requiring MITM or physical device access, email
spoofing, missing DNS/CSP hardening on third-party deployments, and issues in
upstream dependencies without a demonstrated impact here.
