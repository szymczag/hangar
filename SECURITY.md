# Security policy

Hangar is an independent fork of [Plane](https://github.com/makeplane/plane). Hangar
vulnerabilities should not be sent to Plane’s security contact unless the issue has
also been confirmed in upstream Plane.

## Reporting a vulnerability

Report vulnerabilities privately through
[GitHub Private Vulnerability Reporting](https://github.com/szymczag/hangar/security/advisories/new).
Include the affected revision, impact, reproduction steps, and any proposed mitigation.
Remove unrelated secrets and personal data from the report.

If the vulnerability also affects upstream Plane, report it separately according to
[Plane’s security policy](https://github.com/makeplane/plane/blob/preview/SECURITY.md).

Please keep findings confidential until a fix is available. Do not access or alter
data beyond what is necessary for a proof of concept, and do not run disruptive tests,
social engineering, spam, or denial-of-service attacks against systems you do not own.

## Scope

In scope is code maintained in this repository, including fork-specific authentication,
epics, work-item properties, and worklog functionality once those features merge.

Reports about upstream dependencies must demonstrate an impact on Hangar. Findings that
require physical access, a man-in-the-middle position, or attacks against unrelated
third-party deployments are out of scope.
