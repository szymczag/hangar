/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork: compatibility shim, removed in phase 9
//
// Upstream v1.5.0 deleted this module; its call sites render `DateRangeSelect` from
// `@plane/blocks/property-select` directly. This keeps the 1.4 `DateRangeDropdown` call shape over that
// block. One behaviour follows the block: `onSelect` fires once the range is complete (both days
// picked) or cleared, not on the first click of a range.

import type { ReactNode } from "react";
import type { Placement } from "@popperjs/core";
import { observer } from "mobx-react";
// plane imports
import { CalendarOutline } from "@makeplane/propel/icons";
import { DateRangeSelect } from "@plane/blocks/property-select";
import { useTranslation } from "@plane/i18n";
import type { DateRange } from "@plane/propel/calendar";
// hooks
import { useUserProfile } from "@/hooks/store/user";
// local imports
import { toDropdownPlacement, toSelectVariant, toTriggerClassName } from "./compat";
import { DropdownCompatFrame } from "./compat-frame";
import type { TButtonVariants } from "./types";

type TDateRangeDropdownProps = {
  /** No effect: the range commits on the second click. */
  applyButtonText?: string;
  /** No effect: the range commits only once both days are picked. */
  bothRequired?: boolean;
  buttonClassName?: string;
  buttonContainerClassName?: string;
  /** No effect: the trigger shows the range as one label. */
  buttonFromDateClassName?: string;
  /** No effect, see `buttonFromDateClassName`. */
  buttonToDateClassName?: string;
  buttonVariant: TButtonVariants;
  /** No effect: the range commits on the second click. */
  cancelButtonText?: string;
  className?: string;
  /** No effect: clearing is the calendar's "Clear" action. */
  clearIconClassName?: string;
  /** Text tooltip value; a non-text node keeps the formatted range. */
  customTooltipContent?: ReactNode;
  customTooltipHeading?: string;
  defaultOpen?: boolean;
  disabled?: boolean;
  /** The trigger shows a leading calendar icon unless `from` is hidden. @default both hidden */
  hideIcon?: {
    from?: boolean;
    to?: boolean;
  };
  isClearable?: boolean;
  maxDate?: Date;
  mergeDates?: boolean;
  minDate?: Date;
  onSelect?: (range: DateRange | undefined) => void;
  /** One label in the new trigger: the two placeholders joined, or the one that is set. */
  placeholder?: {
    from?: string;
    to?: string;
  };
  placement?: Placement;
  /** No effect: the popup always renders in a portal. */
  renderInPortal?: boolean;
  /** No effect: the blocks trigger always renders lazily. */
  renderByDefault?: boolean;
  renderPlaceholder?: boolean;
  /** No effect: the 1.4 dropdown did not read it either. */
  required?: boolean;
  showTooltip?: boolean;
  tabIndex?: number;
  value: {
    from: Date | undefined;
    to: Date | undefined;
  };
};

export const DateRangeDropdown = observer(function DateRangeDropdown(props: TDateRangeDropdownProps) {
  const { t } = useTranslation();
  const {
    buttonClassName,
    buttonContainerClassName,
    buttonVariant,
    className,
    customTooltipContent,
    customTooltipHeading,
    defaultOpen,
    disabled,
    hideIcon = { from: true, to: true },
    isClearable = false,
    maxDate,
    mergeDates,
    minDate,
    onSelect,
    placeholder = { from: t("project_cycles.add_date"), to: t("project_cycles.add_date") },
    placement,
    renderPlaceholder = true,
    showTooltip,
    tabIndex,
    value,
  } = props;
  // store hooks
  const { data: userProfile } = useUserProfile();
  // derived values
  const dropdownPlacement = toDropdownPlacement(placement);
  const placeholderText = !renderPlaceholder
    ? ""
    : placeholder.from && placeholder.to && placeholder.from !== placeholder.to
      ? `${placeholder.from} - ${placeholder.to}`
      : (placeholder.from ?? placeholder.to ?? "");

  return (
    <DropdownCompatFrame className={className}>
      <DateRangeSelect
        value={{ from: value.from ?? null, to: value.to ?? null }}
        onChange={(range) => onSelect?.({ from: range.from ?? undefined, to: range.to ?? undefined })}
        variant={toSelectVariant(buttonVariant)}
        placeholder={placeholderText}
        minDate={minDate}
        maxDate={maxDate}
        disabled={disabled}
        clearable={isClearable}
        mergeDates={mergeDates}
        weekStartsOn={userProfile?.start_of_the_week}
        icon={hideIcon.from ? undefined : <CalendarOutline />}
        className={toTriggerClassName(buttonContainerClassName, buttonClassName)}
        showTooltip={showTooltip}
        tooltipHeading={customTooltipHeading ?? t("project_cycles.date_range")}
        tooltipContent={typeof customTooltipContent === "string" ? customTooltipContent : undefined}
        tabIndex={tabIndex}
        defaultOpen={defaultOpen}
        side={dropdownPlacement?.side}
        align={dropdownPlacement?.align}
      />
    </DropdownCompatFrame>
  );
});
