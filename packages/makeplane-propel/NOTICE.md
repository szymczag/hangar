# Notice

The files under `src/` and the `LICENSE` file are the work of the authors of
`@makeplane/propel` (Plane Software, Inc. and contributors), licensed under the
GNU Affero General Public License, version 3 only (`AGPL-3.0-only`), as stated in
the package they were recovered from.

## Origin

- Package: `@makeplane/propel`, version 0.9.7, published to the npm registry on
  2026-10-08.
- Tarball integrity:
  `sha512-6BAEr6IBhou6jjfKCTK3ocJ1p9SbQ1OW938ASXGWgAXu64o2UghCBPYlnpNhM2hC/qSjZXhz8A/cNHtlK+Tr5w==`,
  the value upstream's `pnpm-lock.yaml` pins at tag `v1.5.0`.
- Recovered in Hangar on 2026-11-20 with `scripts/propel/recover.mjs`.

## What was recovered and how

- 1684 files are reproduced verbatim from the `sourcesContent` of the source
  maps published in the package. They are unchanged.
- 129 re-export modules (`index.ts`), `src/components/menu/menu-footer.ts`,
  `src/internal/variant-props.ts` and `src/internal/dropdown-edge-gap.ts` had no
  source map; they were rebuilt from the published JavaScript and declaration
  files, as described in `README.md`.
- The stylesheets under `src/styles/` and the images under
  `src/components/logo-spinner/` were copied from the package byte for byte.

`RECOVERY.json` lists every file with its SHA-256 and origin.

## Hangar's own files

`package.json`, `tsconfig.json`, `tsdown.config.ts`, `types/`, `tests/`,
`README.md`, this notice, `RECOVERY.json` and the scripts under
`scripts/propel/` are Hangar's, written to recover, build and verify the package.
Hangar has not modified the recovered files.
