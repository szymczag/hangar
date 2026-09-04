#!/usr/bin/env node
// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only
// See the LICENSE file for details.

/**
 * Run the visual-regression suite.
 *
 * This exists as a script rather than a line in the README because the build
 * environment is the one thing that silently produces a *passing* run against
 * the wrong application. `apps/web/.env` pins VITE_API_BASE_URL to
 * `http://localhost:8000`, and `apps/web/vite.config.ts` bakes every VITE_ var
 * into the bundle at build time. A bundle built from that file talks to a host
 * that does not exist inside the container network, so the app renders its
 * "didn't start correctly" page -- and a baseline captured from that page is
 * stable, green, and completely worthless.
 *
 * The VR stack serves everything from one origin, so every base URL must be
 * empty (i.e. relative). dotenv does not overwrite a variable that is already
 * set, so exporting these wins over the file. All of them are in turbo's
 * `globalEnv`, so the build cache key accounts for them and a differently-built
 * bundle is never restored.
 */

import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, rmSync } from "node:fs";
import path from "node:path";
import process from "node:process";

const ROOT = path.resolve(import.meta.dirname, "..");
const COMPOSE_FILE = "docker-compose-visual.yml";
// Both SPAs, because both bake their own base URLs in and both are served by
// the edge. Checking only the web app let a stale admin bundle through that was
// still calling http://localhost:8000, and the symptom was the console showing
// "Unable to fetch instance details" on a screen nobody had a baseline for yet.
const BUILDS = [
  ["web", path.join(ROOT, "apps/web/build/client/assets")],
  ["admin", path.join(ROOT, "apps/admin/build/client/assets")],
];

// Same origin for everything: the edge routes /api, /god-mode and / itself.
const SAME_ORIGIN_ENV = {
  VITE_API_BASE_URL: "",
  VITE_WEB_BASE_URL: "",
  VITE_ADMIN_BASE_URL: "",
  VITE_SPACE_BASE_URL: "",
  VITE_LIVE_BASE_URL: "",
  VITE_ADMIN_BASE_PATH: "/god-mode",
};

/**
 * The version the API should claim to be.
 *
 * The build identity dialog only shows release notes when the version the API
 * reports matches the one compiled into the bundle -- that mismatch is the
 * defect this whole suite was written after. So the stack is told the version
 * the bundle actually carries, read from the generated file rather than written
 * down twice, because two copies of a version string is precisely the bug.
 */
function bundledVersion() {
  const notes = readFileSync(path.join(ROOT, "apps/web/ce/components/license/release-notes.generated.ts"), "utf8");
  const match = /version:\s*"([^"]+)"/.exec(notes);
  if (!match) throw new Error("Could not read the version from release-notes.generated.ts.");
  return match[1];
}

const env = { ...process.env, ...SAME_ORIGIN_ENV, APP_VERSION: bundledVersion() };

const run = (cmd, args, opts = {}) => execFileSync(cmd, args, { cwd: ROOT, env, stdio: "inherit", ...opts });

/** Which compose implementation is on this machine. CI has docker; dev here has podman. */
function composeCommand() {
  for (const [cmd, args] of [
    ["docker", ["compose"]],
    ["podman-compose", []],
  ]) {
    try {
      execFileSync(cmd, [...args, "version"], { stdio: "ignore" });
      return [cmd, args];
    } catch {
      // try the next one
    }
  }
  throw new Error("Neither `docker compose` nor `podman-compose` is available.");
}

/**
 * Refuse to run against a bundle built for a different origin.
 *
 * Without this the failure is a wall of ERR_CONNECTION_REFUSED inside a browser
 * nobody is watching, and the visible symptom -- every spec failing on its
 * readiness locator -- points at the specs instead of at the build.
 */
function assertBundleIsSameOrigin() {
  for (const [app, assets] of BUILDS) {
    if (!existsSync(assets)) throw new Error(`No ${app} build at ${assets}.`);

    const offenders = readdirSync(assets)
      .filter((f) => f.endsWith(".js"))
      .filter((f) =>
        /https?:\/\/localhost:(8000|3000|3001|3002|3100)/.test(readFileSync(path.join(assets, f), "utf8"))
      );

    if (offenders.length > 0) {
      throw new Error(
        `The ${app} bundle has an absolute base URL baked in (${offenders.slice(0, 3).join(", ")}).\n` +
          "It was built without this script's environment, or restored from a cache entry\n" +
          "that was, and would talk to a host that does not exist in the VR network.\n" +
          `Run \`pnpm turbo run build --filter=${app} --force\` and re-run \`pnpm vr\`.`
      );
    }
  }
}

const updating = process.argv.includes("--update-snapshots");
// Bring the stack up, correctly, and leave it running for iteration. Driving
// compose by hand instead skips two things that are easy to forget and hard to
// diagnose: the bundles get built without this script's environment (so the app
// talks to localhost:8000 and renders its "didn't start correctly" page), and
// APP_VERSION goes unexpanded (so the API reports a literal "${APP_VERSION}").
// Both have happened. `pnpm vr:stack` is the supported way to iterate.
const stackOnly = process.argv.includes("--stack-only");
const [composeBin, composeArgs] = composeCommand();
const compose = (...rest) => run(composeBin, [...composeArgs, "-f", COMPOSE_FILE, ...rest]);

// Clear the output directories first. Turbo restores its cached output over
// whatever is already there without removing what is not in the cache, so a
// bundle from an earlier build with different environment survives alongside the
// restored one -- and the check below then refuses a build that is, in fact,
// correct. Restoring from cache into an empty directory costs about a second.
rmSync(path.join(ROOT, "apps/web/build"), { recursive: true, force: true });
rmSync(path.join(ROOT, "apps/admin/build"), { recursive: true, force: true });

run("pnpm", ["turbo", "run", "build", "--filter=web", "--filter=admin"]);
assertBundleIsSameOrigin();

const EDGE = process.env.VR_HOST_URL ?? "http://localhost:8100";

/**
 * Wait until the stack is not merely up but warm.
 *
 * Two things go wrong in the first seconds after `up`, and both look like
 * application bugs. Chromium watches netlink for interface changes and aborts
 * every request in flight when it sees one (ERR_NETWORK_CHANGED), so a browser
 * started while compose is still attaching containers fails every navigation at
 * once. And a cold API answers its first requests slowly enough that the app
 * renders partway before a screenshot lands.
 *
 * So this asks for the same routes the suite will, and waits for several
 * consecutive fast answers rather than sleeping a guessed interval.
 */
async function warmUp() {
  const routes = ["/", "/api/instances/", "/api/maintenance/"];
  const deadline = Date.now() + 180_000;
  let consecutiveFast = 0;

  while (Date.now() < deadline) {
    const started = Date.now();
    try {
      // Sequential by design: this is a poll, and the point of each iteration is
      // to learn something the previous one could not have told us.
      // oxlint-disable-next-line eslint/no-await-in-loop
      const responses = await Promise.all(routes.map((r) => fetch(`${EDGE}${r}`)));
      const elapsed = Date.now() - started;
      if (responses.every((r) => r.ok) && elapsed < 1000) {
        if (++consecutiveFast >= 3) break;
      } else {
        consecutiveFast = 0;
      }
    } catch {
      consecutiveFast = 0;
    }
    // oxlint-disable-next-line eslint/no-await-in-loop
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  if (consecutiveFast < 3) {
    throw new Error(`The stack at ${EDGE} never answered quickly and consistently. It is up but not usable.`);
  }

  // Pull the application's own bundle through the edge once.
  //
  // Answering /api/ quickly says nothing about how fast the SPA loads: that is
  // forty-odd chunks read off a bind mount that no one has touched yet, and the
  // first browser to ask pays for all of it. That browser is a test, and it was
  // reliably the one that timed out on an otherwise green cold run.
  const html = await (await fetch(`${EDGE}/`)).text();
  const assets = [...html.matchAll(/["'](\/assets\/[^"']+)["']/g)].map((m) => m[1]);
  await Promise.all([...new Set(assets)].map((a) => fetch(`${EDGE}${a}`).catch(() => {})));
}

if (stackOnly) {
  // Same teardown as the main path: `up` collides on container names otherwise,
  // and a stack carried over from a previous iteration keeps its old seed.
  try {
    compose("down", "-v");
  } catch {
    // Nothing to tear down.
  }
  compose("up", "-d");
  await warmUp();
  console.log(
    `\nStack is up and warm at ${EDGE}. Run specs against it with:\n` +
      "  podman-compose -f docker-compose-visual.yml run --rm --no-deps vr-playwright npx playwright test\n" +
      "and tear it down with `podman-compose -f docker-compose-visual.yml down -v`."
  );
  process.exit(0);
}

try {
  // Clear anything a previous interrupted run left behind. Without this, `up`
  // collides on container names and the stack comes up half-old, which is both
  // confusing and a way to compare against a stale build.
  try {
    compose("down", "-v");
  } catch {
    // Nothing to tear down.
  }

  // No `--wait`: podman-compose does not accept it, and warmUp() is a stricter
  // gate than the healthchecks it would wait on -- healthy only means the port
  // answers, not that the application is warm enough to screenshot.
  compose("up", "-d");
  await warmUp();
  // --no-deps because `up --wait` already started everything. Without it compose
  // recreates the dependencies around a browser that is about to start, and
  // Chromium aborts every request in flight with ERR_NETWORK_CHANGED.
  compose(
    "run",
    "--rm",
    "--no-deps",
    "vr-playwright",
    "npx",
    "playwright",
    "test",
    ...(updating ? ["--update-snapshots"] : [])
  );
} finally {
  // Cleanup must not decide the outcome. podman is prone to a non-zero exit
  // here when a container needs SIGKILL to stop, and a green suite reported as
  // a failure because a volume was slow to go away trains people to ignore it.
  try {
    compose("down", "-v");
  } catch (error) {
    console.warn(`Teardown did not exit cleanly; the stack may need \`down -v\` by hand. (${String(error)})`);
  }
}
