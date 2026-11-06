## Security and privacy

**Compose and Swarm installs no longer run object storage on a public login.**
The bundled object storage took its login from the `access-key` / `secret-key`
pair in `variables.env`, and the proxy serves its S3 API on the application's
origin, so anybody who knew the template could sign requests that list, read,
overwrite and delete every upload. The Compose and Swarm installers (both
downloaded as `setup.sh`) now generate a random pair on install, and on upgrade
replace any pair whose secret is still `secret-key`; another secret, and
external S3 storage, are left alone. The object storage and the API pick up the
new pair together when the services start, and uploads stay where they are. The
API settings no longer default to the template pair; the Compose file still
does, so that an older `plane.env` keeps starting, and the API logs a critical
warning while `USE_MINIO` is on with the template secret. Source builds get a
generated pair from `setup.sh` at the repository root. The Helm chart is not
affected: it has always taken these credentials from an operator-supplied
Secret. Ported from makeplane/plane#10074 and adapted to SeaweedFS.

**Only project admins change states through the public API.** The `v1` state
endpoints let a project member, or a member's API token, create, rename and
delete states and change the default, which the web application's API already
reserved for admins. Writes now need a project admin (or a workspace admin who
is a member of the project); reading is unchanged. On `v1`, setting `default`
now clears the project's previous default in the same transaction, and a failed
save keeps it: a `PATCH` used to leave two defaults, and a `POST` that then
failed left none. In the web application's API, the default changes only through
mark-as-default, which now answers `404` for an unknown state instead of
clearing the default; a `default` sent with an ordinary state update is ignored.
Ported from makeplane/plane#10008.

**A magic sign-in code can no longer be guessed without limit.** Running out of
the five attempts on a code deleted the record that also counted how many codes
had been issued, so requesting a new code reset the limit of four codes per
address and the guessing could go on indefinitely, slowed only by the per-IP
rate limit. The issue count now has its own record, so an address gets at most
four codes and twenty guesses in each ten-minute window, which starts with the
first code and is not extended by later ones. Each attempt is counted before the
code is compared, so concurrent requests cannot get more than five comparisons
per code. Ported from makeplane/plane#10040.

**An API token can no longer be hidden from its owner's list.** Tokens carried
an unused service flag that the token endpoints accepted on update and filtered
out of the list and the revoke action, so a token could be made to disappear
from the account settings while it kept working. The flag and an unused rate
limit field are removed, also from token responses; a token flagged that way
before reappears in its owner's list and can be revoked. Ported from
makeplane/plane#10032.

**Sign-in redirects refuse paths that name another host.** A `next_path` such as
`///example.com`, or one with an embedded tab or line break, passed the checks
on both the API and the web application. The API kept such redirects on the
instance's host; the web application's previous check did not reject them. The
API now removes tabs and line breaks and rejects a leading `//`, and the web
application uses the shared path validator. Ported from makeplane/plane#9709.

## Migrations and compatibility

Upgrade from `0.1.0-rc.68`. This release adds one database migration,
`db.0135_remove_apitoken_is_service_and_allowed_rate_limit`, which drops the two
unused token columns described above. It reads nothing and rewrites no rows.
rc.68 loads both columns whenever it authenticates an API key, so rc.68 pods
still running once the migration has applied refuse API-key requests until the
rollout replaces them; sessions are not affected. The Compose upgrade stops the
services first, so it has no such window.

**Compose and Swarm operators: download the latest `setup.sh` before
upgrading.** The upgrade runs the local copy of the script, and only the new
one replaces the template pair; it prints a notice when it does. Anything
outside Hangar that used the old pair needs the new one from `plane.env`. The
old pair is kept as `LEGACY_MINIO_ROOT_USER` / `LEGACY_MINIO_ROOT_PASSWORD` so
that `migrate-object-storage.sh` can still read a volume written by MinIO. If
the API logs the placeholder warning after the upgrade, the CLI README describes
how to replace the pair by hand.

The `v1` state endpoints now answer `POST`, `PATCH` and `DELETE` from a project
member who is not an admin with `403`. An integration that manages states needs
a project admin's token. Token responses no longer carry `is_service` or
`allowed_rate_limit`.

Product version is `v0.1.0-rc.69`, Git tag `hangar-v0.1.0-rc.69`, Helm chart
version `0.1.0-rc.69`, and OCI chart
`ghcr.io/szymczag/charts/hangar:0.1.0-rc.69`.

## Known limitations and rollback

The limitations described in `0.1.0-rc.68` are unchanged. With `USE_MINIO=0` or
an external `AWS_S3_ENDPOINT_URL`, the Compose bundle still starts its own object
storage and routes the bucket path to it, and the installer leaves its login
alone. With empty `AWS_*` values that store runs on the template pair: it holds
no Hangar uploads, but anybody can store objects in it and have them served on
the application's origin. Set your own `AWS_ACCESS_KEY_ID` and
`AWS_SECRET_ACCESS_KEY` in that case; putting the service and its route behind
`USE_MINIO` is planned.

Rolling back to `0.1.0-rc.68` needs the migration reversed first: rc.68 loads
both token columns whenever it authenticates an API key, so API-key requests and
the token endpoints fail without them. Run
`python manage.py migrate db 0134_reset_project_deploy_board_identity` with the
rc.69 API image (on Kubernetes, in an rc.69 API pod) before returning the images
to rc.68. Reversing recreates both columns with their former defaults, so every
token comes back unflagged with the default rate limit, which is what rc.68
expects. Between the reversal and the rollback, creating an API token fails on
rc.69, and an rc.69 container that restarts waits for migrations (the Compose
migrator would re-apply `0135`), so keep that window short and restart nothing in
it. A Compose install keeps its generated storage pair after a rollback, which
rc.68 accepts.
