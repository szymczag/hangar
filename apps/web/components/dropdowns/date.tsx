/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork: compatibility shim, removed in phase 9
//
// Upstream v1.5.0 deleted this module; its call sites render `DateSelect` from
// `@plane/blocks/property-select` directly. This keeps the 1.4 `DateDropdown` call shape over that
// block, with the user's week start, as upstream's callers pass it.

import { isValidElement } from "react";
import type { ReactNode } from "react";
import type { Placement } from "@popperjs/core";
import { observer } from "mobx-react";
// plane imports
import { CalendarOutline } from "@makeplane/propel/icons";
import { DateSelect } from "@plane/blocks/property-select";
import { useTranslation } from "@plane/i18n";
import { getDate } from "@plane/utils";
// hooks
import { useUserProfile } from "@/hooks/store/user";
// local imports
import { DropdownCompatFrame, toDropdownPlacement, toSelectVariant, toTriggerClassName } from "./compat";
import type { TButtonVariants } from "./types";

type TIconElement = Parameters<typeof DateSelect>[0]["icon"];

type TDateDropdownProps = {
  buttonClassName?: string;
  buttonContainerClassName?: string;
  buttonVariant: TButtonVariants;
  className?: string;
  /** No effect: clearing is the calendar's "Clear" action. */
  clearIconClassName?: string;
  /** No effect: picking a day closes the calendar. */
  closeOnSelect?: boolean;
  defaultOpen?: boolean;
  disabled?: boolean;
  formatToken?: string;
  hideIcon?: boolean;
  /** The trigger's leading icon; `null` shows none. */
  icon?: ReactNode;
  /** Offers the calendar's "Clear" action once a day is picked. @default true */
  isClearable?: boolean;
  /** No effect: the label takes the trigger's type. */
  labelClassName?: string;
  maxDate?: Date;
  minDate?: Date;
  onChange: (val: Date | null) => void;
  onClose?: () => void;
  /** No effect: the calendar takes the blocks popover. */
  optionsClassName?: string;
  placeholder?: string;
  placement?: Placement;
  /** No effect: the blocks trigger always renders lazily. */
  renderByDefault?: boolean;
  showTooltip?: boolean;
  tabIndex?: number;
  value: Date | string | null;
};

export const DateDropdown = observer(function DateDropdown(props: TDateDropdownProps) {
  const {
    buttonClassName,
    buttonContainerClassName,
    buttonVariant,
    className,
    defaultOpen,
    disabled,
    formatToken,
    hideIcon = false,
    icon,
    isClearable = true,
    maxDate,
    minDate,
    onChange,
    onClose,
    placeholder = "Date",
    placement,
    showTooltip,
    tabIndex,
    value,
  } = props;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { data: userProfile } = useUserProfile();
  // derived values
  const dropdownPlacement = toDropdownPlacement(placement);
  const triggerIcon: TIconElement | undefined = hideIcon ? undefined : icon === undefined ? (
    <CalendarOutline />
  ) : isValidElement(icon) ? (
    (icon as TIconElement)
  ) : undefined;

  return (
    <DropdownCompatFrame className={className}>
      <DateSelect
        value={getDate(value) ?? null}
        onChange={onChange}
        variant={toSelectVariant(buttonVariant)}
        placeholder={placeholder}
        minDate={minDate}
        maxDate={maxDate}
        disabled={disabled}
        clearable={isClearable}
        formatToken={formatToken}
        weekStartsOn={userProfile?.start_of_the_week}
        icon={triggerIcon}
        className={toTriggerClassName(buttonContainerClassName, buttonClassName)}
        showTooltip={showTooltip}
        tooltipHeading={placeholder}
        tooltipEmptyContent={t("common.none")}
        onClose={onClose}
        tabIndex={tabIndex}
        defaultOpen={defaultOpen}
        side={dropdownPlacement?.side}
        align={dropdownPlacement?.align}
      />
    </DropdownCompatFrame>
  );
});
