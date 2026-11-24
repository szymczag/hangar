/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork: compatibility shim, removed in phase 9
//
// The 1.4 `EstimateDropdown` call shape over upstream's `EstimateSelect` (estimate/estimate-select.tsx).

import type { Placement } from "@popperjs/core";
// local imports
import { toSelectTooltip, toSelectVariant, toTriggerClassName } from "./compat";
import { DropdownCompatFrame } from "./compat-frame";
import { EstimateSelect } from "./estimate/estimate-select";
import type { TButtonVariants } from "./types";

type TEstimateDropdownProps = {
  buttonClassName?: string;
  buttonContainerClassName?: string;
  buttonVariant: TButtonVariants;
  className?: string;
  disabled?: boolean;
  /** No effect: the trigger chrome draws its own chevron where the variant has one. */
  dropdownArrow?: boolean;
  /** No effect, see `dropdownArrow`. */
  dropdownArrowClassName?: string;
  /** No effect: the estimate glyph is part of the trigger. */
  hideIcon?: boolean;
  /**
   * Receives `null` for "No estimate", as upstream's `EstimateSelect` emits it. The callers send it
   * as `estimate_point`, and only `null` clears the field: `undefined` is dropped from the JSON
   * payload, so the server kept the old estimate.
   */
  onChange: (val: string | null) => void;
  onClose?: () => void;
  placeholder?: string;
  placement?: Placement;
  projectId: string | undefined;
  /** No effect: the blocks trigger always renders lazily. */
  renderByDefault?: boolean;
  showTooltip?: boolean;
  tabIndex?: number;
  value: string | undefined | null;
};

export function EstimateDropdown(props: TEstimateDropdownProps) {
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
    projectId,
    showTooltip,
    tabIndex,
    value,
  } = props;

  return (
    <DropdownCompatFrame className={className} placement={placement}>
      <EstimateSelect
        value={value}
        onChange={onChange}
        projectId={projectId}
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
