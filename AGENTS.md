# Agent Development Guide

## Git Workflow

- Every new task MUST start on a new, dedicated branch created from the latest intended base branch.
- Before changing files, verify the current branch, worktree status, base branch, and associated pull request. Do not begin new work on a default branch, detached HEAD, merged pull-request branch, deleted remote branch, or a branch used by another task.
- Use one branch and one pull request per task. Keep unrelated changes out of the branch and PR.
- Use a descriptive branch name such as `fix/<topic>`, `feat/<topic>`, `docs/<topic>`, or `chore/<topic>`.
- Push the task branch and open or update its pull request after implementation and verification. Do not push task commits directly to the base branch.
- If the worktree already contains changes when a new task begins, do not carry them onto a new branch or mix them into the task implicitly. Determine their ownership and ask the user whether to preserve, commit, stash, or separate them before proceeding.
- Treat the branch and pull request as the deployment unit: changes must be reviewed, tested, and merged through the PR workflow before release.

### Parallel Agent Sessions

- Use one Git worktree per active agent session. Two sessions MUST NOT share or modify the same working directory.
- Keep the primary checkout clean and use it only to fetch, inspect, and create task worktrees. Do not implement features in the primary checkout while parallel sessions are running.
- Before starting a session, run `git worktree list` and verify that its branch and directory are not owned by another active session.
- Create each independent task worktree from the latest intended base, for example: `git worktree add ../hangar-worktrees/<task> -b <type>/<topic> origin/<base>`.
- Start the agent with its working directory set to the task worktree. All edits, tests, commits, pushes, and PR operations for that task must remain in that worktree.
- Do not switch branches, stash changes, clean files, reset state, or remove a worktree owned by another session.
- Give concurrent Docker Compose stacks a unique `COMPOSE_PROJECT_NAME`. Use separate host ports, `.env` files, databases, caches, and other mutable runtime state when those resources are exposed outside the Compose project.
- When one task depends on another, use stacked branches and PRs: create the dependent branch from the prerequisite branch, target its PR at the prerequisite branch, then rebase and retarget it after the prerequisite merges.
- Create independent tasks directly from the shared base branch. Resolve migration numbers and other merge-order conflicts by rebasing the later PR before merge.
- Remove a task worktree only after its session has stopped and its work is committed, preserved, or merged. Then run `git worktree prune` to clean stale metadata.

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
