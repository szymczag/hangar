# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import logging.handlers as handlers
import time


class SizedTimedRotatingFileHandler(handlers.TimedRotatingFileHandler):
    """
    Handler for logging to a set of files, which switches from one file
    to the next when the current file reaches a certain size, or at certain
    timed intervals
    """

    def __init__(
        self,
        filename,
        maxBytes=0,
        backupCount=0,
        encoding=None,
        delay=0,
        when="h",
        interval=1,
        utc=False,
    ):
        handlers.TimedRotatingFileHandler.__init__(self, filename, when, interval, backupCount, encoding, delay, utc)
        self.maxBytes = maxBytes

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        Basically, see if the supplied record would cause the file to exceed
        the size limit we have.
        """
        if self.stream is None:  # delay was set...
            self.stream = self._open()
        if self.maxBytes > 0:  # are we rolling over?
            msg = "%s\n" % self.format(record)
            # due to non-posix-compliant Windows feature
            self.stream.seek(0, 2)
            if self.stream.tell() + len(msg) >= self.maxBytes:
                return 1
        t = int(time.time())
        if t >= self.rolloverAt:
            return 1
        return 0


class RedactTaskArgumentsFilter(logging.Filter):
    """Keep Celery task arguments out of the worker's JSON log.

    Celery hands the context of its "received", "succeeded" and failure lines to
    handlers as ``extra={"data": {...}}``, and a JSON formatter writes every
    extra field. That context carries the task's ``args`` and ``kwargs``: for
    ``forgot_password``, ``magic_link``, ``send_email_update_magic_code`` and the
    invitation tasks those are a password-reset token, a sign-in code, an
    e-mail-change code or a join token, at INFO, readable by anyone with access
    to the container logs. The task name and id stay, so a line can still be
    traced; the arguments never reach the record that is formatted.
    """

    REDACTED = "[redacted]"
    FIELDS = ("args", "kwargs")

    def filter(self, record):
        data = getattr(record, "data", None)
        if isinstance(data, dict) and any(field in data for field in self.FIELDS):
            record.data = {key: (self.REDACTED if key in self.FIELDS else value) for key, value in data.items()}
        # The same dict is also the %-format mapping of these lines.
        if isinstance(record.args, dict) and any(field in record.args for field in self.FIELDS):
            record.args = {
                key: (self.REDACTED if key in self.FIELDS else value) for key, value in record.args.items()
            }
        return True
