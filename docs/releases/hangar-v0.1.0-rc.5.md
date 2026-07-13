## Security and privacy

This release candidate completes the public Hangar identity across the web,
administration, Space, API, email, deployment, and documentation surfaces. User
support now points to public GitHub issues, while sensitive vulnerability reports
point to GitHub private vulnerability reporting. No maintainer email address is
presented as product support.

Images and running applications now expose the exact Hangar source revision and
repository URL. Upstream Plane copyright, license, provenance, and compatibility
identifiers remain intact. This release does not claim to remediate a specific
security vulnerability, and the existing release-candidate production security
limitations still apply.

## Migrations and compatibility

This release has no application database migration. It replaces public product
copy, logos, favicons, social images, email branding, and translated Plane product
references with Hangar equivalents. Internal `plane` modules, `@plane/*` packages,
database contracts, and other compatibility-sensitive identifiers are unchanged.

The Helm chart adds validated branding metadata with Hangar defaults and passes
the existing render-policy suite. Existing `rc.4` values remain compatible, so no
operator configuration change is required. Normal upgrade precautions still
apply: use `--wait-for-jobs` and take a coordinated PostgreSQL and object-storage
backup before upgrading.

## Known limitations and rollback

Translations preserve the existing upstream wording and substitute the product
identity; they have not all received native-speaker review. Some accurate Plane
references intentionally remain in upstream attribution, license, source-history,
and compatibility contexts. The branding regression check documents and enforces
that boundary.

Rolling back application images and the Helm chart to `rc.4` restores the previous
public branding and requires no reverse database migration. Helm rollback does not
reverse external-service changes, and the broader production qualification gaps
documented for earlier release candidates remain open.
