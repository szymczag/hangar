# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from zxcvbn import zxcvbn


PASSWORD_MIN_LENGTH = 15
PASSWORD_MIN_SCORE = 3


def is_password_strong(password: str) -> bool:
    """Return whether a password meets the length and guessability policy."""
    return len(password) >= PASSWORD_MIN_LENGTH and zxcvbn(password)["score"] >= PASSWORD_MIN_SCORE
