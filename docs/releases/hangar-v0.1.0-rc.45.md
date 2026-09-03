## Security and privacy

**Trainer capacity changes send the CSRF proof the server requires.** Opting in,
editing availability, starting or disconnecting Google Calendar, selecting
calendars, and saving or deleting workshop schedules now fetch a server-issued
CSRF token before sending the mutation. Deployments enforcing Django's CSRF
checks previously rejected those actions even for an authenticated and
authorised user. The token is read from the existing same-origin endpoint and is
sent only back to the Hangar API.

**Every part of workspace Home defaults is reachable again.** The page now owns
the same bounded scroll container as the other workspace settings pages. Its
parent layout deliberately clips overflow, so rendering the content without that
container left controls below a short viewport inaccessible by mouse, touch, or
keyboard scrolling. The loading and loaded states both use the corrected
boundary.

## Migrations and compatibility

There is no database migration and no change to Helm values, Secrets, storage,
RBAC, NetworkPolicies, public routes, or the inherited Plane baseline. Existing
`rc.44` deployment configuration remains compatible.

The capacity fix changes only authenticated browser requests: each mutation adds
one same-origin request for a CSRF token immediately before the write. The API
and its permission checks are unchanged. Deploy the web and API images together
as the normal release unit.

## Known limitations and rollback

The capacity requests are covered by frontend unit tests for every mutation and
an API contract test proving that a state-changing capacity endpoint rejects a
request without a CSRF token. The Home defaults page has a source contract test
covering both render states. Neither correction has been exercised manually in
a browser as part of release preparation.

The evaluation profile remains qualified on AMD64 only; the production profile
is still available for review but unsupported. No new live-cluster qualification
was performed because the chart contract and workload topology did not change.

Rolling back to `rc.44` requires no schema reversal or configuration change. It
restores the broken capacity mutations and clipped Home defaults page, so prefer
a forward correction if this release needs replacement.
