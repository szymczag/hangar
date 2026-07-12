# Contributing to Hangar

Hangar welcomes focused bug reports, feature proposals, documentation improvements,
and code contributions. This repository is an independent fork of Plane; contribute
here when the change concerns Hangar or its fork-specific behavior.

## Before opening an issue

Search [existing Hangar issues](https://github.com/szymczag/hangar/issues) first. For a
bug, include:

- the branch or commit you tested;
- deployment type and relevant environment details;
- minimal reproduction steps;
- expected and actual behavior;
- relevant logs or screenshots with secrets removed.

Use [GitHub Private Vulnerability Reporting](https://github.com/szymczag/hangar/security/advisories/new)
instead of a public issue for security vulnerabilities. See [SECURITY.md](SECURITY.md).

If the behavior reproduces on an unmodified Plane build and does not involve Hangar,
report it to [upstream Plane](https://github.com/makeplane/plane) instead. When uncertain,
open a Hangar issue and explain what you tested.

## Development setup

### Requirements

- Docker Engine with Docker Compose
- Node.js 22.18 or newer
- Corepack
- At least 12 GB of RAM recommended

Set up the repository:

```sh
git clone https://github.com/szymczag/hangar.git
cd hangar
./setup.sh
```

Start infrastructure and application development servers:

```sh
docker compose -f docker-compose-local.yml up -d
pnpm dev
```

The web application runs at <http://localhost:3000>. Open
<http://localhost:3001/god-mode/> to register the instance administrator.

## Making changes

- Branch from the current `preview` branch.
- Keep fork-specific backend code in `apps/api/plane/ext/` and frontend code in the
  community-edition extension surface whenever possible.
- Record every necessary edit to an upstream-owned file in the core-touch ledger in
  [FORK.md](FORK.md).
- Preserve existing upstream copyright headers. Use the Hangar copyright header for
  new fork-authored files as described in `FORK.md`.
- Use Conventional Commit messages and do not add attribution trailers.
- Add unit or contract tests for behavior changes.

## Checks

Run the complete repository checks before submitting a pull request:

```sh
pnpm check
```

Useful targeted commands include:

```sh
pnpm check:lint
pnpm check:types
pnpm turbo run <command> --filter=<package>
```

The Django test suite runs in the isolated stack described in
[`apps/api/tests/RUNNING_TESTS.md`](apps/api/tests/RUNNING_TESTS.md). Run the complete
suite with:

```sh
docker compose -f docker-compose-test.yml up --build --abort-on-container-exit --exit-code-from api-tests
```

## Pull requests

Open pull requests against `preview`. Explain the user-visible outcome, test evidence,
and any upstream-owned files touched. Keep unrelated changes in separate pull requests.

By participating, you agree to follow the project’s [Code of Conduct](CODE_OF_CONDUCT.md).
