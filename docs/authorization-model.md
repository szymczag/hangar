# Authorization model and its boundaries

How Hangar decides who may see and change what, which boundaries exist, and how
they are kept from eroding. Written for people changing access-controlled code
or reviewing such a change.

## The boundaries

Four, from outermost to innermost. A defect at any level is only visible if you
test at that level, which is why the probes described below use distinct
personas rather than one "unauthorised" caller.

| Boundary | Question                                                            | Typical failure                                    |
| -------- | ------------------------------------------------------------------- | -------------------------------------------------- |
| Instance | Does this person have an account at all?                            | an unauthenticated route                           |
| Tenant   | May they act on **this workspace**?                                 | a queryset filtered by id but not workspace        |
| Project  | May they act on **this project** inside a workspace they belong to? | a check that stops at workspace membership         |
| Role     | May they perform **this operation** on it?                          | a decorator admitting a role that should not write |

The project boundary is the one most often missed. Every caller in that scenario
legitimately belongs to the workspace, so the request looks ordinary and the
common workspace-level check passes.

## Six enforcement mechanisms

Authorization is not expressed one way. A change to access control has to
identify which of these the endpoint uses, because they fail differently:

1. **`permission_classes`** — DRF classes such as `ProjectEntityPermission`.
2. **`@allow_permission`** — role decorator, `level="PROJECT"` by default.
3. **Membership filtering in the queryset** — no explicit gate; the filter _is_
   the gate.
4. **Service-layer checks** — the view delegates, e.g. `resolve_for_admin(actor=…)`.
5. **Self-scoping** — the record is keyed to `request.user`, so identity is the
   scope.
6. **Helper functions** — e.g. `user_has_issue_permission`, `can_read_file_asset`.

Mechanism 3 is the dangerous one: a missing `.filter()` is indistinguishable
from correct code by reading.

### Permission classes branch on HTTP method, not on operation

`ProjectBasePermission` answers `POST` from a branch written for _creating_ a
project, which deliberately ignores `project_id` because no project exists yet.
Any other `POST` endpoint using that class inherits a check that never asks
about the target object. This produced a real defect: archiving a project asked
only for a workspace role.

**When adding a `POST` endpoint that acts on an existing object, do not reach
for `ProjectBasePermission`.** Use `ProjectEntityPermission` (membership to
read, `ADMIN`/`MEMBER` to write) or the `@allow_permission` decorator.

### The two APIs disagree unless you make them agree

The same operation exists in the session-authenticated app API
(`plane/app/views/`) and the token-authenticated external API
(`plane/api/views/`), with **separate** permission wiring. A change to one is
not a change to the other. Both defects found in the archive endpoint and in
member listings were divergences of this kind, so when changing an operation's
authorization, check whether the other API exposes it too.

## Caller-supplied identifiers

Filters built from query parameters must be constrained to the workspace in the
URL. Two endpoints appended a caller-supplied `project_ids` to a queryset
without it; one leaked member counts **across tenants**.

```python
# wrong — the caller chooses the scope
ProjectMember.objects.filter(project_id__in=project_ids)

# right — the URL chooses the scope, the caller narrows within it
ProjectMember.objects.filter(workspace__slug=slug, project_id__in=project_ids)
```

The same applies to ids in a request body: a `state_id` or `assignee_id` from
another workspace must be rejected, not trusted because the route was.

## How the boundaries are tested

Three suites, each covering what the previous cannot reach.

| Suite                                | Covers                                                                                                                         |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `test_route_authorization_matrix.py` | every workspace-scoped route, non-member persona; plus the standing check that no route lacks a recognised mechanism           |
| `test_horizontal_authorization.py`   | boundaries inside one workspace: member-without-project, guest, project admin, deactivated account, IDOR, self-role escalation |
| `test_authorization_surfaces.py`     | token-authenticated API, published boards, assets by id, analytics                                                             |

Shared setup is in `plane/tests/support/`: `personas.py` builds a workspace with
**two** projects and seven personas, `route_inventory.py` enumerates routes and
classifies them.

### Conventions worth keeping

- **Assert on content, not status codes.** Several routes legitimately answer
  `200` with an empty body to a caller who may see nothing. Each project seeds a
  canary string that exists nowhere else; its presence in a response is the
  leak. A `5xx` is a failure too — a route that crashes has not denied anything.
- **Writes are stricter.** There is no benign empty answer to a write, so a
  `2xx` is always wrong. Row counts are compared before and after, since a `4xx`
  that still mutated something would otherwise pass.
- **Keep a positive control.** `test_a_project_member_can_actually_see_their_project`
  exists so the suite cannot pass against a build that denies everything.
- **Two projects, not one.** With a single project, "member of the project" and
  "member of the workspace" give the same answer everywhere, and a missing
  project filter is invisible.
- **Do not build personas from `plane/tests/factories.py`.** Its member
  factories default to `role=20`, so a persona named "guest" would silently be
  an administrator.
- **`force_authenticate` bypasses the external API's token authentication.** It
  reports acceptances that cannot happen. Probe `/api/v1/` with a real
  `APIToken`.
- **Filter by generated path, not view module.** Some route names are registered
  in both url confs, so `reverse()` can return an `/api/v1/` path for a record
  whose module says `plane.app.views`.
- **Read URL parameters from the whole resolver chain, not the leaf.** Under
  `include()` the workspace `slug` is captured by the parent, so a leaf's own
  `groupindex` reports no parameters for routes such as
  `workspaces/<slug>/runner/installation/`. Because `workspace_scoped()` selects
  on `slug` being present, those routes dropped out of every probe while the
  report still looked complete — fifteen of them, including the external API's
  invitation endpoints. `test_a_route_is_never_scoped_by_less_than_its_url_captures`
  compares each entry's captures against its URL text so this cannot recur at
  any nesting depth.

### Recording a finding without going red

A confirmed defect that is not being fixed in the same change is marked
`@pytest.mark.xfail(strict=True)` with a reason naming the file and line. The
suite stays green, the finding stays visible, and `strict=True` forces whoever
fixes it to remove the marker — a fixed defect makes the test pass, which fails
a strict xfail.

## API tokens

A token authenticates as its owner and names the workspace it may act in. It is
confined to that workspace in `BaseAPIView.initial()` rather than by a permission
class, because views override `permission_classes` freely and the rule must not
be switchable off by omission.

Creating one requires holding a role in that workspace, at or above
`API_TOKEN_MINIMUM_ROLE` (guest by default, raised in God Mode). The two halves
depend on each other: without the workspace on the token a role requirement means
nothing, because someone who is an administrator of their own workspace would
mint a token that reaches one where they are a guest. That was the behaviour
before — any signed-in account could mint a token, and it reached everywhere its
owner did.

Tokens created before this keep `workspace = NULL` and their previous reach: the
owner's memberships. Nothing revokes them, and raising the threshold does not
either — it governs minting, not tokens already issued.

The threshold is reported to the application on `/api/instances/`, so it offers
the feature only where creating a token would succeed: the workspace chooser
lists the memberships that qualify, and where none do the offer is withdrawn with
the reason rather than accepting a form and refusing it on save. Existing tokens
stay listed and revocable regardless — someone below the threshold can still see
and revoke what they already hold.

This is presentation, not enforcement. `ApiTokenEndpoint` decides, and it decides
the same way whatever the interface showed. The threshold is read from one place,
`plane.utils.api_token_policy`, precisely so the offer and the refusal cannot
drift apart; a drifting copy would either hide a feature that works or offer one
that does not.

A route with no workspace slug in its path is not confined by this, since there
is nothing to compare against. Every such route under `/api/v1/` today addresses
the caller's own record — their profile and their own uploads — where a scoped
token acting as its owner is correct. That is an assumption about the route
table, so `test_api_token_workspace_scope.py` asserts the set has not grown into
anything workspace-bound.

The secret is returned **only** when the token is created. Reads and renames
answer with `APITokenReadSerializer`, which excludes it.

## Assets served without a session

`StaticFileAssetEndpoint` is deliberately `AllowAny`, but not uniformly:

| Entity type                 | Who may read it                                               |
| --------------------------- | ------------------------------------------------------------- |
| `USER_AVATAR`, `USER_COVER` | anyone — rendered on sign-in screens and public boards        |
| `WORKSPACE_LOGO`            | workspace members                                             |
| `PROJECT_COVER`             | project members, **or** anyone while the project is published |

A project cover follows publication rather than membership because the public
board lists it. Gating covers on membership alone would break published boards —
worth re-checking before changing this table.

## The instance-admin console

The console is a separate authentication world: its own session cookie (selected
by the substring `instances` in the request path), its own permission class, and
no relation to workspace membership. It is **not** covered by the domain policy —
it checks the password directly rather than going through the provider adapters —
so it carries its own second factor instead. See
[second factor for the God Mode console](god-mode-second-factor.md).

Two consequences for anyone adding an endpoint there:

- It **must** be mounted under a path containing `instances`, or the session
  middleware will read and write the application session instead.
- `InstanceAdminPermission` requires a second-factor marker in the session, so
  `force_authenticate` is not enough in tests. Use
  `plane/tests/support/admin_session.py`.

## Configuration that participates in authorization

| Setting                        | Effect                                                |
| ------------------------------ | ----------------------------------------------------- |
| `ENABLE_SIGNUP=0`              | account creation requires an invitation               |
| `DISABLE_WORKSPACE_CREATION=1` | only instance administrators create workspaces        |
| `SSO_ENFORCED_DOMAINS`         | pins an email domain to designated identity providers |
| `SSO_AUTO_JOIN_WORKSPACES`     | places federated users into a workspace on sign-in    |

An account with no membership sees no content, so those two flags are what make
"anyone can sign in" safe. See [federated SSO security](federated-sso-security.md).
