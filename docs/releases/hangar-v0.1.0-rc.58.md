## Security and privacy

**A work item with five or more updates at once now notifies its watchers.**
Notifications for one work item and one recipient are batched, and the batch was
identified by joining the notification identifiers together — 92 characters plus 37
per notification. The outbox column that stores it, and the check in front of that
column, stop at 255. Four updates produced a 240-character identifier and were
delivered; five produced 277 and were refused. The batch is rebuilt from the same
unprocessed rows on every run, so one that was too long failed identically every five
minutes rather than once, and the busier the work item the more reliably it failed —
the opposite of what anyone would look for. The identifier is now a fixed-length digest
of the same inputs, so it cannot outgrow the limit at any batch size while still
identifying the same batch, and a retry still cannot send a second copy.

This was the last of four faults stacked in front of activity notification email, and
it was invisible until the other three were cleared: the template did not parse before
rc.56, and the base URL came from an expiring cache key before rc.57. Instances that
upgraded through those releases and still saw nothing arrive for busy work items were
seeing this.

**A release can no longer be tagged with documentation naming the previous one.**
The publication requires the Kubernetes guide to name the release being tagged, and
refuses when it does not — but that check runs after the tag is pushed, and a pushed tag
consumes its version, so the recovery is a new release number rather than a retry. The
release version is the highest set of release notes present, which needs no tag to
determine, so the same assertions now run on every pull request that touches either
file. A guide left naming the previous release fails at review, where the cost is an
edit.

## Migrations and compatibility

Upgrade from `0.1.0-rc.57`. This release introduces no database migrations and no schema
change, so no migration Job is required beyond the ordinary release Job and rollback is
not constrained by schema state.

Product version is `v0.1.0-rc.58`, Git tag `hangar-v0.1.0-rc.58`, Helm chart version
`0.1.0-rc.58`, and OCI chart `ghcr.io/szymczag/charts/hangar:0.1.0-rc.58`. No chart
resources, Secrets, storage, RBAC or NetworkPolicy contract changes are introduced.

Identifiers already recorded against delivered notifications keep their previous form.
Nothing recomputes an identifier for a notification that has already been processed, so
the change of format cannot produce a duplicate message.

A notification batch that was refused under the old limit and has not yet exhausted its
delivery attempts is sent on the first scheduled run after the upgrade. One that already
reached its attempt ceiling stays terminal and is not revived; the underlying activity
remains visible in Hangar.

## Known limitations and rollback

Notifications that reached the attempt ceiling before this release are not retried by it.
The reason each gave up is recorded on its row, so an operator can see which were lost
and to whom, but they are not resent.

Rollback to rc.57 restores the previous images and the joined identifier, which
reintroduces the refusal for any batch of five or more. Because no migration is
introduced, a rollback has no schema consequence, and identifiers written by this
release remain valid for the messages already sent under them.

The evaluation qualification boundary remains AMD64. The production profile remains
unsupported; this release does not claim a new live-cluster qualification. Publication
verifies the chart and images through the release workflow. Deployment and acceptance on
the user's environment remain a separate step.
