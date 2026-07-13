## Security and privacy

This release candidate completes the public Hangar identity across the web,
administration, Space, API, email, deployment, and documentation surfaces. User
support now points to public GitHub issues, while sensitive vulnerability reports
point to GitHub private vulnerability reporting. No maintainer email address is
presented as product support.

`rc.5` also replaces password composition rules with a minimum of 15 Unicode
code points and guessability-based validation. The browser meter and server-side
password setters use zxcvbn dictionaries to reject common, predictable, and
context-derived passwords without requiring digits, symbols, or mixed case.

The frontend loads its canonical public origin from a no-store runtime
configuration file, the backend trusts only the deployment's forwarded host,
port, and TLS scheme settings, and bundled NGINX servers no longer disclose
internal listener ports in redirects.

Images and running applications expose the exact Hangar source revision and
repository URL. Upstream Plane copyright, license, provenance, and compatibility
identifiers remain intact. Existing release-candidate production security
limitations still apply.

## Migrations and compatibility

There is no database migration. This release replaces public product copy,
logos, favicons, social images, email branding, and translated Plane product
references with Hangar equivalents. Internal `plane` modules, `@plane/*`
packages, database contracts, and other compatibility-sensitive identifiers are
unchanged. New and reset passwords must satisfy the new 15-character and
guessability policy; existing password hashes remain valid.

The chart retains the validated branding metadata and Hangar defaults introduced
with the rebrand. It also gains optional Gateway API resources for Envoy-style
deployments. Set `gateway.enabled=true`, configure an existing Gateway parent or
let the chart create one, and leave the NGINX Ingress disabled. The chart renders
explicit routes for `/god-mode`, `/spaces`, `/live`, `/api`, and `/`, and
normalizes the four application prefixes with relative-host 308 redirects.
Existing Ingress deployments and `rc.4` values remain supported. Normal upgrade
precautions still apply: use `--wait-for-jobs` and take a coordinated PostgreSQL
and object-storage backup before upgrading.

## Known limitations and rollback

The chart's runtime `config.js` supplies deployment-specific Vite URLs for Helm
installs. Other packaging must either serve an equivalent file or build the
static frontend images with all five `VITE_*_BASE_URL` variables set to the
external origin.

Gateway API redirect and request-header filters require a controller that
implements the corresponding HTTPRoute features. Translations preserve the
existing upstream wording and substitute the product identity; they have not all
received native-speaker review. Some accurate Plane references intentionally
remain in upstream attribution, license, source-history, and compatibility
contexts. The branding regression check documents and enforces that boundary.

Rolling back application images and the chart to `rc.4` restores the previous
branding, password, and routing behavior. It does not invalidate passwords
created under `rc.5`, require a reverse database migration, or reverse external
Gateway resources managed outside the release. Helm rollback does not reverse
external-service changes, and the broader production qualification gaps
documented for earlier release candidates remain open.
