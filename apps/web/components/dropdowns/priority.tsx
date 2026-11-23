/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork: compatibility shim, removed in phase 9
//
// The 1.4 `PriorityDropdown` call shape over upstream's `PrioritySelect` (priority/priority-select.tsx).

import type { Placement } from "@popperjs/core";
// plane imports
import type { TIssuePriorities } from "@plane/types";
// local imports
import { toSelectTooltip, toSelectVariant, toTriggerClassName } from "./compat";
import { DropdownCompatFrame } from "./compat-frame";
import { PrioritySelect } from "./priority/priority-select";
import type { TButtonVariants } from "./types";

type TPriorityDropdownProps = {
  buttonClassName?: string;
  buttonContainerClassName?: string;
  buttonVariant: TButtonVariants;
  className?: string;
  disabled?: boolean;
  /** No effect: the trigger chrome draws its own chevron where the variant has one. */
  dropdownArrow?: boolean;
  /** No effect, see `dropdownArrow`. */
  dropdownArrowClassName?: string;
  /** No effect: the priority glyph is part of the option. */
  hideIcon?: boolean;
  /** No effect: the blocks trigger has no separate urgent highlight. */
  highlightUrgent?: boolean;
  onChange: (val: TIssuePriorities) => void;
  onClose?: () => void;
  placeholder?: string;
  placement?: Placement;
  /** No effect: the blocks trigger always renders lazily. */
  renderByDefault?: boolean;
  showTooltip?: boolean;
  tabIndex?: number;
  value: TIssuePriorities | undefined | null;
};

export function PriorityDropdown(props: TPriorityDropdownProps) {
  const {
    buttonClassName,
    buttonContainerClassName,
    buttonVariant,
    className,
    disabled,
    onChange,
    onClose,
    placeholder,
    placement,
    showTooltip,
    tabIndex,
    value,
  } = props;

  return (
    <DropdownCompatFrame className={className} placement={placement}>
      <PrioritySelect
        // an omitted value read as "none" in the 1.4 dropdown
        value={value === undefined ? "none" : value}
        onChange={onChange}
        variant={toSelectVariant(buttonVariant)}
        disabled={disabled}
        placeholder={placeholder}
        onClose={onClose}
        className={toTriggerClassName(buttonContainerClassName, buttonClassName)}
        tooltip={toSelectTooltip(showTooltip)}
        tabIndex={tabIndex}
      />
    </DropdownCompatFrame>
  );
}
