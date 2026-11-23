/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork: compatibility shim, removed in phase 9
//
// The 1.4 `CycleDropdown` call shape over upstream's `CycleSelect` (cycle/cycle-select.tsx).

import { useMemo } from "react";
import type { Placement } from "@popperjs/core";
// local imports
import { toSelectTooltip, toSelectVariant, toTriggerClassName } from "../compat";
import { DropdownCompatFrame } from "../compat-frame";
import type { TButtonVariants } from "../types";
import { CycleSelect } from "./cycle-select";

type TCycleDropdownProps = {
  buttonClassName?: string;
  buttonContainerClassName?: string;
  buttonVariant: TButtonVariants;
  /** Offers the "No cycle" row. @default true */
  canRemoveCycle?: boolean;
  className?: string;
  /** Hidden from the options, as in 1.4. */
  currentCycleId?: string;
  disabled?: boolean;
  /** No effect: the trigger chrome draws its own chevron where the variant has one. */
  dropdownArrow?: boolean;
  /** No effect, see `dropdownArrow`. */
  dropdownArrowClassName?: string;
  /** No effect: the cycle glyph is part of the trigger. */
  hideIcon?: boolean;
  onChange: (val: string | null) => void;
  onClose?: () => void;
  placeholder?: string;
  placement?: Placement;
  projectId: string | undefined;
  /** No effect: the blocks trigger always renders lazily. */
  renderByDefault?: boolean;
  showTooltip?: boolean;
  tabIndex?: number;
  value: string | null;
};

export function CycleDropdown(props: TCycleDropdownProps) {
  const {
    buttonClassName,
    buttonContainerClassName,
    buttonVariant,
    canRemoveCycle = true,
    className,
    currentCycleId,
    disabled,
    onChange,
    onClose,
    placeholder,
    placement,
    projectId,
    showTooltip,
    tabIndex,
    value,
  } = props;
  // derived values
  const excludeIds = useMemo(() => (currentCycleId ? [currentCycleId] : undefined), [currentCycleId]);

  return (
    <DropdownCompatFrame className={className} placement={placement}>
      <CycleSelect
        projectId={projectId}
        value={value}
        onChange={onChange}
        variant={toSelectVariant(buttonVariant)}
        clearable={canRemoveCycle}
        excludeIds={excludeIds}
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
