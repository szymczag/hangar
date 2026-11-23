/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork: compatibility shim, removed in phase 9
//
// The 1.4 `StateDropdown` call shape over upstream's `StateSelect` (state/state-select.tsx).

import type { Placement } from "@popperjs/core";
import { observer } from "mobx-react";
// hooks
import { useProjectState } from "@/hooks/store/use-project-state";
// local imports
import { DropdownCompatFrame, toSelectTooltip, toSelectVariant, toTriggerClassName } from "../compat";
import type { TButtonVariants } from "../types";
import { StateSelect } from "./state-select";

type TStateDropdownProps = {
  buttonClassName?: string;
  buttonContainerClassName?: string;
  buttonVariant: TButtonVariants;
  className?: string;
  disabled?: boolean;
  /** No effect: the trigger chrome draws its own chevron where the variant has one. */
  dropdownArrow?: boolean;
  /** No effect, see `dropdownArrow`. */
  dropdownArrowClassName?: string;
  /** No effect: the state glyph is part of the option. */
  hideIcon?: boolean;
  /** No effect: the glyph takes the trigger's size. */
  iconSize?: string;
  /** No effect in Hangar: no workflow gates the state list. */
  isForWorkItemCreation?: boolean;
  onChange: (val: string) => void;
  onClose?: () => void;
  placeholder?: string;
  placement?: Placement;
  projectId: string | undefined;
  /** No effect: the blocks trigger always renders lazily. */
  renderByDefault?: boolean;
  /** An empty value shows the project's default state, as the 1.4 dropdown did. @default true */
  showDefaultState?: boolean;
  showTooltip?: boolean;
  tabIndex?: number;
  value: string | undefined | null;
};

export const StateDropdown = observer(function StateDropdown(props: TStateDropdownProps) {
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
    showDefaultState = true,
    showTooltip,
    tabIndex,
    value,
  } = props;
  // store hooks
  const { getProjectDefaultStateId } = useProjectState();
  // derived values
  const stateValue = value || (showDefaultState ? getProjectDefaultStateId(projectId) : undefined);

  return (
    <DropdownCompatFrame className={className} placement={placement}>
      <StateSelect
        projectId={projectId}
        value={stateValue}
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
});
