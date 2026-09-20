/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@plane/propel/button";
import { shiftMonth } from "./capacity-format.utils";

type Props = {
  monthStart: Date;
  onChange: (next: (current: Date) => Date) => void;
};

/**
 * Move the report a month at a time, and say which month you are on.
 *
 * The week stepper names both ends of its range because a Monday-to-Monday span
 * reads as eight days. A month needs no such care: naming it is unambiguous, so
 * this shows the month rather than a pair of dates.
 */
export function MonthStepper({ monthStart, onChange }: Props) {
  return (
    <div className="flex items-center gap-2">
      <Button
        variant="secondary"
        size="sm"
        aria-label="Previous month"
        onClick={() => onChange((current) => shiftMonth(current, -1))}
      >
        <ChevronLeft className="size-4" />
      </Button>
      <div className="min-w-40 text-center text-body-xs-medium">
        {monthStart.toLocaleDateString(undefined, { month: "long", year: "numeric" })}
      </div>
      <Button
        variant="secondary"
        size="sm"
        aria-label="Next month"
        onClick={() => onChange((current) => shiftMonth(current, 1))}
      >
        <ChevronRight className="size-4" />
      </Button>
    </div>
  );
}
