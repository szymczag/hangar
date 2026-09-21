## Security and privacy

No security or privacy changes identified. This release repairs a defect
introduced in `0.1.0-rc.62` and does not alter what is read, written, stored or
shown.

## Migrations and compatibility

Upgrade from `0.1.0-rc.62`. **Anybody running `rc.62` with Google Calendar
capacity enabled should upgrade immediately**: on that release every call to
Google raises, so the capacity ledger, the workshop planner and every booking
check answer with a server error. A deployment that has not enabled calendar
capacity is unaffected.

This release introduces no database migrations and no schema change, so the
ordinary release Job is all that is required and rollback is not constrained by
schema state.

Product version is `v0.1.0-rc.63`, Git tag `hangar-v0.1.0-rc.63`, Helm chart
version `0.1.0-rc.63`, and OCI chart
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.63`.

**Every authorized Google Calendar request failed in rc.62.** The hardened
outbound transport answers with a response object that carries its bytes on one
attribute, and a check for an empty body — added so that deleting a calendar
event, which answers with no content at all, would not be retried forever —
asked it for a different attribute belonging to another library's response type.
The two are not interchangeable, and the difference is invisible to a test that
mocks the client rather than the transport, which every existing capacity test
does. That seam is now tested, and those tests fail with the exact production
exception against the previous release.

**A failed read no longer takes the screen down with it.** That the defect above
reached a browser as a server error is a second fault, and the more consequential
one. Both calendar reads caught a short list of expected failures and let
anything else propagate, so one unexpected exception ended the whole request.

The rule this subsystem is built on runs the other way: a read that failed must
read as _unverified_, and unverified refuses a booking rather than permitting
one. Both reads now catch what they did not expect, record its type in the log,
and answer with a status that is not fresh. The booking preflight accepts only a
fresh answer, so an unexpected failure costs a refused booking and a marked row
in the ledger — never a trainer who appears free because the code broke.

There is deliberately no fallback to the last known answer on that path. A known
provider failure is a state the software understands and can serve a previous
answer for; an unexpected one is not, so it is reported rather than papered over.

## Known limitations and rollback

The limitations described in `0.1.0-rc.62` are unchanged: recognition depends on
trainers holding their own copy of each invitation, a trainer who has not granted
training recognition is reported as such rather than as having run no training,
and calendar write-back depends on one person's token remaining healthy.

Only the type of an unexpected failure is logged, never its message or any
payload, which is deliberate — this subsystem handles calendar contents — but it
does mean diagnosing one needs the surrounding request context rather than the
log line alone.

Rollback to `rc.62` restores the previous images and, with it, the defect this
release repairs: with calendar capacity enabled, every capacity request fails.
`rc.61` is the last release before it. No schema changes are involved in either
direction.

The evaluation qualification boundary remains AMD64. The production profile
remains unsupported; this release does not claim a new live-cluster
qualification. Publication verifies the chart and images through the release
workflow. Deployment and acceptance on the user's environment remain a separate
step.
