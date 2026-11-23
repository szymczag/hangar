/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork: compatibility shim, removed in phase 9
//
// The 1.4 `IntakeStateDropdown` call shape over upstream's `IntakeStateSelect`
// (intake-state/intake-state-select.tsx). An empty value shows the project's intake state, as before.

import type { Placement } from "@popperjs/core";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// local imports
import { DropdownCompatFrame, toSelectVariant, toTriggerClassName } from "../compat";
import type { TButtonVariants } from "../types";
import { IntakeStateSelect } from "./intake-state-select";

type TIntakeStateDropdownProps = {
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
  /** No effect: the intake trigger has no tooltip. */
  showTooltip?: boolean;
  tabIndex?: number;
  value: string | undefined | null;
};

export const IntakeStateDropdown = observer(function IntakeStateDropdown(props: TIntakeStateDropdownProps) {
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
    tabIndex,
    value,
  } = props;
  // router params
  const { workspaceSlug } = useParams();

  return (
    <DropdownCompatFrame className={className} placement={placement}>
      <IntakeStateSelect
        workspaceSlug={workspaceSlug?.toString() ?? ""}
        projectId={projectId ?? ""}
        value={value}
        onChange={onChange}
        variant={toSelectVariant(buttonVariant)}
        disabled={disabled}
        placeholder={placeholder}
        onClose={onClose}
        className={toTriggerClassName(buttonContainerClassName, buttonClassName)}
        tabIndex={tabIndex}
      />
    </DropdownCompatFrame>
  );
});
