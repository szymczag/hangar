/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

type TWorklogActivityMessage = {
  /** The activity row's verb: "created", "updated" or "deleted". */
  verb: string;
  /** The logged duration before the change, already formatted by the server ("30m"). */
  oldValue: string | null | undefined;
  /** The logged duration after the change, already formatted by the server ("45m"). */
  newValue: string | null | undefined;
};

/**
 * What a worklog activity row says: "logged 45m", "updated logged time from 30m
 * to 45m" or "removed logged time 45m".
 *
 * One wording for every feed that prints worklog rows -- the work item's own
 * activity and a user's profile activity -- so a row does not read differently
 * depending on where it is seen. Whether the row may be seen at all is decided
 * before this renders (S20, `isWorklogHiddenForRole`/`canViewWorklogsForRole`).
 */
export function WorklogActivityMessage({ verb, oldValue, newValue }: TWorklogActivityMessage) {
  if (verb === "created")
    return (
      <>
        logged <span className="font-medium text-primary">{newValue}</span>
      </>
    );
  if (verb === "updated")
    return (
      <>
        updated logged time from <span className="font-medium text-primary">{oldValue}</span> to{" "}
        <span className="font-medium text-primary">{newValue}</span>
      </>
    );
  return (
    <>
      removed logged time <span className="font-medium text-primary">{oldValue}</span>
    </>
  );
}
