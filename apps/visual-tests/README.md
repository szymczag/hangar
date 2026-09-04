# Visual regression

Screenshots of the real application, compared pixel for pixel against baselines
committed to this repository.

## Why this exists

Four releases shipped with the same line in their notes: _the interface has not
been looked at in a browser._ Three defects reached `preview` that no test saw:

| Defect                                                                        | How it was found                                            |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------- |
| The duplicate form prefilled `<name> (Copy)`, which its own endpoint rejected | reported by the operator                                    |
| The build identity dialog never showed its release notes                      | running the release and reading the version the API returns |
| Copied work items' images pointed at the source project                       | reading the code, then proving it against real storage      |

The first two now have contract tests. What none of them cover is the class that
produced the original complaint: **how it looks** — whether the bar and the shell
still fit together, whether a strip survives a narrow viewport.

The harness is verified to catch that class: growing the maintenance bar's icon
by four pixels fails all three maintenance stories, on every retry. It is also
verified _not_ to catch something it was originally claimed to — see the note in
`specs/maintenance.spec.ts` about `<main>`, which renders identically whether it
is `h-full` or `min-h-0 flex-1`. Both results came from running it rather than
from reasoning about it, which is the habit this suite is meant to encourage.

## Running it

```bash
pnpm vr            # build the SPAs, bring the stack up, compare
pnpm vr:update     # the same, but rewrite the baselines
```

Both go through `scripts/vr.mjs`, and that is the only supported entry point.

### Why there is a script instead of a documented command

`apps/web/.env` pins `VITE_API_BASE_URL` to `http://localhost:8000`, and
`apps/web/vite.config.ts` bakes every `VITE_` variable into the bundle at build
time. Inside the VR network that host does not exist, so the app renders its
"didn't start correctly" page — and a baseline captured from _that_ is stable,
green, and worthless. Everything is served from one origin here, so every base
URL must be empty. `scripts/vr.mjs` sets them, and then refuses to run if
either built bundle still contains an absolute URL.

**Both** bundles, and that word was earned. The check originally looked only at
`apps/web`, and a stale `apps/admin` bundle still calling `http://localhost:8000`
went straight past it -- every console page rendered "Unable to fetch instance
details", which is a perfectly stable thing to photograph. Building by hand and
restarting only the edge skips this check entirely, so generate baselines with
`pnpm vr:update` rather than driving compose directly.

`dotenv` does not overwrite a variable that is already set, which is why
exporting wins over the file. All of these are in turbo's `globalEnv`, so the
build cache key accounts for them and a differently-built bundle is never
restored from cache.

## Reviewing a baseline change

A changed baseline is a changed file in the diff. That is the whole point of
committing them, and it only works if the diff is actually looked at.

1. **Open the image diff on GitHub.** If you cannot say what changed, the change
   has not been reviewed.
2. **A baseline changes only alongside the code that changed it.** A PR that
   touches nothing but PNGs is either a rebase artefact or a regression being
   waved through.
3. **If the canary moved, stop.** `canary.spec.ts` renders no application code —
   only text, a hairline and a shadow. If it changed, the _environment_ changed,
   and every other diff in the PR is unreadable until that is explained.
4. **`--update-snapshots` never runs in CI.** If CI could rewrite baselines, the
   review would be theatre.

### The one baseline that changes on a schedule

`build-identity-*.png` photographs the release notes, so **preparing a release
changes it**. That is not drift: the dialog's content genuinely changed, the
diff shows exactly which lines, and the number of notes changes the dialog's
height, so there is nothing to mask that would leave the story worth telling.

Run `pnpm vr:update` as part of the release preparation and commit the two PNGs
with the notes. If a release PR is red on `visual-regression` and the only diff
is this dialog, that is the expected path and not a regression — but read the
image anyway, because it is the one moment anybody looks at the release notes
rendered rather than as markdown.

## Determinism

The suite refuses to run outside its pinned container (`src/guards.ts`), and
refuses to run if the container's Playwright differs from `@playwright/test`.
That is what turns font rendering from something to manage into something that
cannot vary — and it is why `snapshotPathTemplate` carries no `{platform}`
segment: exactly one environment is supported, and the path says so.

Tolerance is zero, defined once in `playwright.config.ts`. A tolerance is the
mechanism by which a visual suite becomes noise: it gets raised once during a
flake and never comes back down. `scripts/check-suite-invariants.mjs` fails the
build on an inline tolerance, on `networkidle`, on `waitForTimeout`, on
`fullPage`, and on any screenshot not taken through `capture()`.

The hazards this suite has actually hit, and how each is handled:

| Hazard                                    | Handling                                                                                                                                                                                         |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| The copy strip polls every 3s             | a broker but no celery worker, so `copied`/`total` never move and every poll returns identical JSON                                                                                              |
| i18n renders `null` until loaded          | `capture()` takes a **mandatory** readiness locator; asserting real content is self-synchronising                                                                                                |
| Modals animate for 300ms                  | `settled()` asserts the finished state rather than sleeping                                                                                                                                      |
| The bar renders `null` without a notice   | the seed must produce one, so a silently broken seed fails instead of recording an empty baseline                                                                                                |
| Work item numbers follow database history | the seed writes `sequence_id` explicitly, so a fresh volume in CI and a re-seed on a developer's machine agree                                                                                   |
| The API rate-limits anonymous requests    | every browser shares one address and the sign-in page is unauthenticated, so `ANON_RATE_LIMIT` is raised for this stack — otherwise 429s arrive in bursts and render as "didn't start correctly" |
| Hydration is starved under parallelism    | `workers: 3` and a 60s assertion ceiling, plus `retries: 2` — which cannot mask a pixel regression, since that reproduces on every attempt, as the icon experiment above shows                   |

### Waiting on the right thing

A readiness locator satisfied by a skeleton gives a stable, beautiful,
meaningless baseline. Two stories here learned it the hard way, and both lessons
generalise:

- The maintenance stories waited on the bar, which arrives long before the work
  items do, and captured a blank content pane. Wait on **seeded content** — the
  names come from the manifest, so the spec and the seed cannot drift.
- The console story waited on "any level-3 heading", which the console's own
  _Unable to fetch instance details_ screen also renders. It recorded that error
  page as the baseline: green, stable, and a photograph of the application
  failing. A readiness locator must be something **the broken state cannot also
  produce** — so it now waits on that page's own description text, and asserts
  the error text is absent.

The console stories learned a third variant, and it is the sneakiest. Their first
readiness locator was the page's own description text -- which turns out to live
in `apps/admin/hooks/use-sidebar-menu/core.ts`, i.e. in the **sidebar**, which
renders before the page has fetched anything. It was not satisfied by a skeleton
or by an error screen; it was satisfied by the furniture around them.

So every console story goes through `consolePage()` in `src/capture.ts`, which
waits for content inside `<main>` and then asserts the `<Loader>` skeleton
(`role="status"`, `packages/ui/src/loader.tsx`) is gone. Neither the shell nor
the console's "Unable to fetch instance details" screen can satisfy that: the
error screen renders no `<main>` at all.

The general rule: ask what the page looks like when the thing you are testing is
broken, **and what it looks like before it has loaded**, and check that your
locator would not be satisfied by either.

To confirm that guard still holds, block the console's configuration request and
check the story refuses rather than captures:

```ts
await page.route("**/api/instances/configurations/**", (r) => r.abort());
// consolePage(...) must now throw
```

That is a manual check rather than a committed test, because the failure path
costs a full assertion timeout every run.

## The instance console

Nineteen of the baselines are God Mode pages, captured through `<main>` rather
than the viewport. The console sidebar is identical on every one of them, so
putting it inside nineteen images would mean one sidebar tweak touches nineteen
files and review becomes a formality. The sidebar and shell get exactly one
baseline, `god-mode-general`, which is the only console story shot
full-viewport.

Four of the provider pages are inherited from upstream. They are here because
the fork put config-source badges, "this setting would be ignored" refusals and
the secret-field behaviour into the _shared_ console form components (FORK.md
rows 27, 35, 51), so a regression there lands on an upstream page as readily as
on OIDC or SAML.

## Scope

Light theme for everything; dark only where a story uses a semantic token no
existing dark story covers. Theme regressions are token regressions, so the
twenty-eighth dark baseline carries almost no information at linear review cost.

`light-contrast`, `dark-contrast` and `custom` are out of scope, as are
`apps/space` and `apps/live` — `Caddyfile.vr` deliberately does not route them.

## Not part of `pnpm check`

`check` is a pure-Node command that runs anywhere. This suite needs a container
stack and several GB of images, so folding it in would make the repo's fast path
slow and machine-dependent.
