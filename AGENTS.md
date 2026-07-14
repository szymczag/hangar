# Agent Development Guide

## Commands

- `pnpm dev` - Start all dev servers (web:3000, admin:3001)
- `pnpm build` - Build all packages and apps
- `pnpm check` - Run all checks (format, lint, types)
- `pnpm check:lint` - OxLint across all packages
- `pnpm check:types` - TypeScript type checking
- `pnpm fix` - Auto-fix format and lint issues
- `pnpm turbo run <command> --filter=<package>` - Target specific package/app
- `pnpm --filter=@plane/ui storybook` - Start Storybook on port 6006

## Code Style

- **Imports**: Use `workspace:*` for internal packages, `catalog:` for external deps
- **TypeScript**: Strict mode enabled, all files must be typed
- **Formatting**: oxfmt, run `pnpm fix:format`
- **Linting**: OxLint with shared `.oxlintrc.json` config
- **Naming**: camelCase for variables/functions, PascalCase for components/types
- **Error Handling**: Use try-catch with proper error types, log errors appropriately
- **State Management**: MobX stores in `packages/shared-state`, reactive patterns
- **Testing**: All features require unit tests, use existing test framework per package
- **Components**: Build in `@plane/ui` with Storybook for isolated development

## Kubernetes Chart Documentation

- Every change under `charts/hangar/**` MUST include a substantive update to
  `docs/kubernetes/README.md` in the same pull request. This applies to chart
  metadata, templates, values, schemas, dependencies, examples, scripts, and tests.
- Release-preparation changes MUST update `docs/kubernetes/README.md` with the exact
  product version, chart version, Git tag, OCI chart reference, compatibility
  boundary, and previous-release information for that release.
- Review the rest of `docs/kubernetes/` and `charts/hangar/README.md` for affected
  instructions whenever the chart contract or operator workflow changes. Update
  every affected page; changing only the landing page is not sufficient when other
  guidance has become inaccurate.
- Do not satisfy the documentation requirement with whitespace, formatting-only,
  or unrelated edits. A Kubernetes chart or release change is incomplete until the
  documentation describes the resulting operator-visible behavior accurately.

## Backend tests (Docker)

The Django/pytest suite for `apps/api` runs in an isolated stack defined by `docker-compose-test.yml` at the repo root.

Prereq (once): `./setup.sh` — generates `apps/api/.env` from `.env.example`.

- Full suite: `docker compose -f docker-compose-test.yml up --build --abort-on-container-exit --exit-code-from api-tests`
- Subset: `docker compose -f docker-compose-test.yml run --rm api-tests pytest -m unit`
- Teardown: `docker compose -f docker-compose-test.yml down -v`

See `apps/api/tests/RUNNING_TESTS.md` for the full walkthrough and troubleshooting; see `apps/api/tests/TESTING_GUIDE.md` for test conventions and fixtures.
