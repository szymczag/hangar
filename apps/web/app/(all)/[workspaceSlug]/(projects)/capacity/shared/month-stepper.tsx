/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { ChevronLeftOutline, ChevronRightOutline } from "@makeplane/propel/icons";
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
      <IconButton
        variant="secondary"
        size="md"
        icon={<Icon icon={ChevronLeftOutline} />}
        aria-label="Previous month"
        onClick={() => onChange((current) => shiftMonth(current, -1))}
      />
      <div className="min-w-40 text-center text-body-xs-medium">
        {monthStart.toLocaleDateString(undefined, { month: "long", year: "numeric" })}
      </div>
      <IconButton
        variant="secondary"
        size="md"
        icon={<Icon icon={ChevronRightOutline} />}
        aria-label="Next month"
        onClick={() => onChange((current) => shiftMonth(current, 1))}
      />
    </div>
  );
}
