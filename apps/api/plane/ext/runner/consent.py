# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from dataclasses import dataclass
from hashlib import sha256


RUNNER_CONSENT_TEXT = (
    "Hangar Runner security consent\n"
    "\n"
    "By activating Hangar Runner, a workspace administrator acknowledges that:\n"
    "- approved scripts may read and modify workspace data within their granted capabilities;\n"
    "- secrets bound to scripts may be disclosed to explicitly approved external destinations;\n"
    "- scripts are untrusted code and must execute only in the supported isolated runtime; and\n"
    "- the workspace administrator is responsible for reviewing scripts, permissions, and destinations.\n"
)
RUNNER_CONSENT_V1_DIGEST = "6713ce3d0b6f6e37853b7d4892484264c790a9bda76decf76fc3a1dc3aaa9fcf"


@dataclass(frozen=True, slots=True)
class RunnerConsentContract:
    version: int
    document_id: str
    digest: str
    text: str


def consent_digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


if consent_digest(RUNNER_CONSENT_TEXT) != RUNNER_CONSENT_V1_DIGEST:
    raise RuntimeError("Runner consent text changed without a versioned digest update.")


CURRENT_RUNNER_CONSENT = RunnerConsentContract(
    version=1,
    document_id="hangar-runner-security-consent-v1",
    digest=RUNNER_CONSENT_V1_DIGEST,
    text=RUNNER_CONSENT_TEXT,
)
