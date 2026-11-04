# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from zxcvbn import zxcvbn


PASSWORD_MIN_LENGTH = 15
PASSWORD_MIN_SCORE = 3

# Score at most this many characters from each end of the password, so the cost of
# scoring stays bounded. The password is strong if either window is strong.
ZXCVBN_MAX_LENGTH = 128


def is_password_strong(password: str) -> bool:
    """Return whether a password meets the length and guessability policy."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return False
    windows = {password[:ZXCVBN_MAX_LENGTH], password[-ZXCVBN_MAX_LENGTH:]}
    return any(zxcvbn(window)["score"] >= PASSWORD_MIN_SCORE for window in windows)
