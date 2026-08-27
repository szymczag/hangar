# Linting in Hangar - How It Works

This page covers the TypeScript and JavaScript side. The Python API is linted
separately with [ruff](https://docs.astral.sh/ruff/) — see [Linting the API](#linting-the-api).

We use [OxLint](https://oxc.rs/docs/guide/usage/linter) for linting across the entire monorepo. OxLint is a single Rust binary that's 50-100x faster than ESLint, with zero Node.js dependencies at runtime.

## Key Points

1. **Single Root Config** - One `.oxlintrc.json` at the repo root handles all packages and apps
2. **No Build Required** - OxLint doesn't need TypeScript build artifacts, so lint runs independently of build
3. **Plugin Coverage** - react, typescript, jsx-a11y, import, promise, unicorn, oxc

## How to Run

From the root of the repo:

```bash
# Check for lint errors
pnpm check:lint

# Auto-fix lint errors
pnpm fix:lint
```

To lint a specific package:

```bash
pnpm turbo run check:lint --filter=@plane/ui
```

## VS Code Integration

Install the [OxLint extension](https://marketplace.visualstudio.com/items?itemName=nicolo-ribaudo.vscode-oxlint) for inline errors/warnings as you type.

## What Gets Linted

The config applies to all TypeScript and JavaScript files across:

- `apps/web`, `apps/admin`, `apps/space`, `apps/live`
- All packages in `packages/`

**Ignored paths:**

- `node_modules/`, `dist/`, `build/`, `.next/`, `.turbo/`
- Config files (`*.config.{js,mjs,cjs,ts}`)
- Public folders, coverage, storybook-static

## Rules Overview

OxLint uses category-based configuration:

| Category        | Level | What It Catches                          |
| --------------- | ----- | ---------------------------------------- |
| **correctness** | error | Real bugs that will cause runtime errors |
| **suspicious**  | warn  | Code patterns that are likely mistakes   |
| **perf**        | warn  | Performance anti-patterns                |

Additional rule overrides:

- `react/prop-types` off (TypeScript handles prop validation)
- `no-unused-vars` warns with `_` prefix pattern ignored
- Several noisy unicorn rules disabled

## Backward Compatibility

OxLint supports `eslint-disable` comments, so existing inline suppressions continue to work.

## Suppressing Warnings

```typescript
// Single line
// eslint-disable-next-line no-unused-vars
const data = response;

// Block
/* eslint-disable no-unused-vars */
// ... code
/* eslint-enable no-unused-vars */
```

**Please use sparingly** - most warnings indicate real issues that should be fixed.

## Pre-commit Hook

Lint-staged runs automatically on commit via Husky:

- oxfmt formats your staged files
- OxLint fixes what it can (with `--deny-warnings`)

If the commit fails due to lint errors, fix them before committing.

## Reference Files

- [.oxlintrc.json](../.oxlintrc.json) - OxLint configuration
- [package.json](../package.json) - Available scripts

## Linting the API

`apps/api` is linted with ruff, configured in `apps/api/pyproject.toml`. Only
pycodestyle (`E`) and Pyflakes (`F`) are enabled, at a line length of 120.

```bash
# from the repo root
ruff check apps/api
```

### The version is pinned in one place

`apps/api/requirements/local.txt` holds the pin, and the CI workflow reads it
from there rather than repeating it:

```yaml
run: python -m pip install "$(grep '^ruff==' apps/api/requirements/local.txt)"
```

Change the version in that file and CI follows. Installing ruff unpinned means a
ruff release can change the result of a check nobody re-ran, and it means CI and
your machine can disagree about whether the code is clean.

### The check has to be able to fail

The workflow runs `ruff check apps/api` — deliberately **without** `--fix`. With
`--fix`, ruff repairs what it finds and exits zero, so the job reports success
whatever it found, and the repair is thrown away with the runner. A check that
cannot fail is not a check.

If ruff reports something, fix it in your branch. `ruff check --fix apps/api` is
fine to run locally, where the result is kept.

### Formatting is checked for fork-owned code only

```bash
ruff format --check apps/api/plane/ext
```

`apps/api/plane/ext` holds Hangar's own API code, it is already formatted, and CI
keeps it that way.

The rest of `apps/api/plane` is deliberately **not** checked. Ruff would reformat
48 files there, and 41 of them are inherited from Plane at the upstream baseline
recorded in `UPSTREAM_BASE.json` — carrying Plane's own formatting rather than any
drift introduced here. Rewriting those would put a formatting conflict in every
future upstream merge and buy nothing for it.

If you are editing an inherited file, match the style around you rather than
running the formatter over the whole file.

### The API checks gate merges

`API lint` and `API tests` are required status checks on `preview`. They are not
the jobs that do the work — they are small jobs that run whatever the real ones
did and report the result, in the same shape as `Verify publication` in
`build-branch.yml`.

The indirection is necessary. A path filter under `on:` stops the **whole
workflow** from starting, and a required check that never reports leaves a pull
request blocked forever — so the API workflows can no longer filter by path at
the trigger. Instead a `changes` job asks the API which files the pull request
touches, the heavy jobs are gated on its answer, and the gate job runs
unconditionally and treats a skipped job as success.

So a front-end-only change still does not pay for an eleven-minute API test run,
and a change that breaks the API can no longer be merged because the check that
would have caught it was advisory.

### Test exemptions cover less than they look like they do

`[tool.ruff.lint.per-file-ignores]` exempts `tests/*` from `E402`, `F401` and
`F811`. That glob matches `apps/api/tests/` — three files — and **not**
`apps/api/plane/tests/`, where nearly every test actually lives. The main test
tree is therefore held to the same rules as the rest of the code.

This is left as it is on purpose. Widening the glob would weaken the check across
hundreds of files to accommodate a pattern the codebase does not currently need.

