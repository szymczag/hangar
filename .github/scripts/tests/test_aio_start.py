# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The all-in-one image's entrypoint must start with the volumes it documents.

A host directory mounted at /app/logs hides the log directories baked into the
image, and supervisord refuses to start when a log file's directory is missing,
so start.sh recreates them on every boot (upstream makeplane/plane#9818).
"""

import re
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
AIO = REPOSITORY_ROOT / "deployments" / "aio" / "community"
START = AIO / "start.sh"
SUPERVISOR = AIO / "supervisor.conf"


def _shell_function(source: str, name: str) -> str:
    match = re.search(rf"^{name}\(\)\s*\{{.*?^}}$", source, re.DOTALL | re.MULTILINE)
    if match is None:
        raise AssertionError(f"start.sh has no {name}()")
    return match.group(0)


class LogDirectoryTests(unittest.TestCase):
    def test_every_supervisor_log_directory_is_created_before_supervisord(self):
        directories = {
            str(Path(path).parent)
            for path in re.findall(r"^std(?:out|err)_logfile=(\S+)$", SUPERVISOR.read_text(), re.MULTILINE)
        }
        self.assertTrue(directories)
        main = _shell_function(START.read_text(), "main")
        before_supervisord = main.split("/usr/local/bin/supervisord", 1)[0]
        created = set()
        for line in re.findall(r"^\s*mkdir -p (.+)$", before_supervisord, re.MULTILINE):
            created.update(line.split())
        self.assertEqual(directories - created, set())


if __name__ == "__main__":
    unittest.main()
