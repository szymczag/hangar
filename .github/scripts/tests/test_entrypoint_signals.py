# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Long-running API containers must hand their PID to the process they start.

The entrypoint scripts run as PID 1. Bash as PID 1 does not act on SIGTERM
unless it traps it, so a script that starts its server as a child leaves the
server running until the runtime gives up and sends SIGKILL: `podman stop`
after 10 seconds, Kubernetes after the termination grace period. Under
supervisord, where the script is not PID 1, the script dies and the server
keeps running as an orphan. Each script therefore ends by replacing itself
with the server through `exec`.

The migrator is left out on purpose: it is a one-shot job, and it is better
that a stop does not interrupt a migration half-way.
"""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BIN = REPOSITORY_ROOT / "apps" / "api" / "bin"
LONG_RUNNING = (
    "docker-entrypoint-api.sh",
    "docker-entrypoint-api-local.sh",
    "docker-entrypoint-worker.sh",
    "docker-entrypoint-beat.sh",
)


def _commands(script: Path) -> list[str]:
    """Top-level commands of a script, with continuation lines joined."""
    commands, current = [], ""
    for line in script.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        current = f"{current} {stripped}".strip()
        if current.endswith("\\"):
            current = current[:-1]
            continue
        commands.append(current)
        current = ""
    return commands


class EntrypointExecTests(unittest.TestCase):
    def test_every_server_start_replaces_the_script(self):
        for name in LONG_RUNNING:
            commands = _commands(BIN / name)
            starts = [c for c in commands if c.removeprefix("exec ").split()[0] in {"celery", "gunicorn"} or "runserver" in c]
            self.assertTrue(starts, name)
            for command in starts:
                self.assertTrue(command.startswith("exec "), f"{name}: {command}")
            self.assertTrue(commands[-1].startswith("exec "), f"{name}: {commands[-1]}")

    def test_beat_receives_the_stop_signal_itself(self):
        with tempfile.TemporaryDirectory() as scratch:
            stubs = Path(scratch)
            (stubs / "python").write_text("#!/bin/sh\nexit 0\n")
            # The stand-in for celery stays up until it is signalled.
            (stubs / "celery").write_text("#!/bin/sh\nwhile :; do sleep 0.1; done\n")
            for stub in ("python", "celery"):
                (stubs / stub).chmod(0o755)

            process = subprocess.Popen(
                ["bash", str(BIN / "docker-entrypoint-beat.sh")],
                cwd=REPOSITORY_ROOT / "apps" / "api",
                env={"PATH": f"{stubs}:/usr/bin:/bin"},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            try:
                cmdline = Path(f"/proc/{process.pid}/cmdline")
                deadline = time.monotonic() + 10
                started = ""
                while time.monotonic() < deadline and process.poll() is None:
                    started = cmdline.read_bytes().replace(b"\0", b" ").decode()
                    if str(stubs / "celery") in started:
                        break
                    time.sleep(0.05)
                self.assertIn(
                    str(stubs / "celery"),
                    started,
                    "the script's own process never became celery, so a stop signal reaches only the shell",
                )

                process.send_signal(signal.SIGTERM)
                self.assertEqual(process.wait(timeout=5), -signal.SIGTERM)
            finally:
                # Without exec the stand-in outlives the shell; stop the whole group.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()


if __name__ == "__main__":
    unittest.main()
