/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@plane/propel/button";
import { shiftWeek } from "./capacity-format.utils";

type Props = {
  weekStart: Date;
  weekEnd: Date;
  onChange: (next: (current: Date) => Date) => void;
};

/**
 * Move the window a week at a time, and say which week you are on.
 *
 * Shared rather than duplicated because the ledger and the planner read the same
 * window: two steppers would be two chances to disagree about what "this week"
 * means, and the planner had no way to change the week at all before this.
 *
 * `weekEnd` is exclusive -- the instant the next week begins -- so the label
 * subtracts a millisecond to name the last day that is actually in range, rather
 * than showing a Monday-to-Monday span that reads as eight days.
 */
export function WeekStepper({ weekStart, weekEnd, onChange }: Props) {
  return (
    <div className="flex items-center gap-2">
      <Button
        variant="secondary"
        size="sm"
        aria-label="Previous week"
        onClick={() => onChange((current) => shiftWeek(current, -1))}
      >
        <ChevronLeft className="size-4" />
      </Button>
      <div className="min-w-44 text-center text-body-xs-medium">
        {weekStart.toLocaleDateString(undefined, { day: "numeric", month: "short" })} –{" "}
        {new Date(weekEnd.getTime() - 1).toLocaleDateString(undefined, {
          day: "numeric",
          month: "short",
          year: "numeric",
        })}
      </div>
      <Button
        variant="secondary"
        size="sm"
        aria-label="Next week"
        onClick={() => onChange((current) => shiftWeek(current, 1))}
      >
        <ChevronRight className="size-4" />
      </Button>
    </div>
  );
}
