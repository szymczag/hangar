/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork: compatibility shim, removed in phase 9
//
// The 1.4 `ProjectDropdown` call shape over upstream's `ProjectSelect` (project/project-select.tsx).
// Both list the projects the user has joined; `renderCondition` keeps narrowing that list (the work
// item modal offers only the projects the user may create work items in).

import { useCallback } from "react";
import type { Placement } from "@popperjs/core";
// local imports
import { toSelectTooltip, toSelectVariant, toTriggerClassName } from "../compat";
import { DropdownCompatFrame } from "../compat-frame";
import type { TButtonVariants } from "../types";
import { ProjectSelect } from "./project-select";

type TProjectDropdownProps = {
  buttonClassName?: string;
  buttonContainerClassName?: string;
  buttonVariant: TButtonVariants;
  className?: string;
  /** Hidden from the options, as in 1.4. */
  currentProjectId?: string;
  disabled?: boolean;
  /** No effect: the trigger chrome draws its own chevron where the variant has one. */
  dropdownArrow?: boolean;
  /** No effect, see `dropdownArrow`. */
  dropdownArrowClassName?: string;
  /** No effect: the project logo is part of the trigger. */
  hideIcon?: boolean;
  onClose?: () => void;
  placeholder?: string;
  placement?: Placement;
  /** No effect: the blocks trigger always renders lazily. */
  renderByDefault?: boolean;
  /** Only the projects it accepts are offered. */
  renderCondition?: (projectId: string) => boolean;
  showTooltip?: boolean;
  tabIndex?: number;
} & (
  | {
      multiple: false;
      onChange: (val: string) => void;
      value: string | null;
    }
  | {
      multiple: true;
      onChange: (val: string[]) => void;
      value: string[];
    }
);

export function ProjectDropdown(props: TProjectDropdownProps) {
  const {
    buttonClassName,
    buttonContainerClassName,
    buttonVariant,
    className,
    currentProjectId,
    disabled,
    onClose,
    placeholder,
    placement,
    renderCondition,
    showTooltip,
    tabIndex,
  } = props;
  const filterOption = useCallback(
    (projectId: string) => !renderCondition || renderCondition(projectId),
    [renderCondition]
  );
  const common = {
    variant: toSelectVariant(buttonVariant),
    disabled,
    placeholder,
    onClose,
    className: toTriggerClassName(buttonContainerClassName, buttonClassName),
    tooltip: toSelectTooltip(showTooltip),
    filterOption: renderCondition ? filterOption : undefined,
    excludeProjectId: currentProjectId,
    tabIndex,
  };

  return (
    <DropdownCompatFrame className={className} placement={placement}>
      {props.multiple ? (
        <ProjectSelect {...common} multiple value={props.value} onChange={props.onChange} />
      ) : (
        <ProjectSelect
          {...common}
          value={props.value}
          // the 1.4 single select had no way to clear, so it only ever emitted an id
          onChange={(projectId) => {
            if (projectId) props.onChange(projectId);
          }}
        />
      )}
    </DropdownCompatFrame>
  );
}
