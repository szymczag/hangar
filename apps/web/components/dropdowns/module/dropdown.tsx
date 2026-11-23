/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork: compatibility shim, removed in phase 9
//
// The 1.4 `ModuleDropdown` call shape over upstream's `ModuleSelect` (module/module-select.tsx).

import type { Placement } from "@popperjs/core";
import type { SelectVariant } from "@plane/blocks/select";
// local imports
import { toSelectTooltip, toSelectVariant, toTriggerClassName } from "../compat";
import { DropdownCompatFrame } from "../compat-frame";
import type { TButtonVariants } from "../types";
import { ModuleSelect } from "./module-select";

type TModuleDropdownProps = {
  buttonClassName?: string;
  buttonContainerClassName?: string;
  buttonVariant: TButtonVariants;
  className?: string;
  disabled?: boolean;
  /** No effect: the trigger chrome draws its own chevron where the variant has one. */
  dropdownArrow?: boolean;
  /** No effect, see `dropdownArrow`. */
  dropdownArrowClassName?: string;
  /** No effect: the module glyph is part of the trigger. */
  hideIcon?: boolean;
  /** No effect: the option rows take the blocks layout. */
  itemClassName?: string;
  onClose?: () => void;
  placeholder?: string;
  placement?: Placement;
  projectId: string | undefined;
  /** No effect: the blocks trigger always renders lazily. */
  renderByDefault?: boolean;
  /** No effect: the multi-select trigger summarises the selection itself. */
  showCount?: boolean;
  showTooltip?: boolean;
  tabIndex?: number;
} & (
  | {
      multiple: false;
      onChange: (val: string | null) => void;
      value: string | null;
    }
  | {
      multiple: true;
      onChange: (val: string[]) => void;
      value: string[] | null;
    }
);

export function ModuleDropdown(props: TModuleDropdownProps) {
  const {
    buttonClassName,
    buttonContainerClassName,
    buttonVariant,
    className,
    disabled,
    onClose,
    placeholder,
    placement,
    projectId,
    showTooltip,
    tabIndex,
  } = props;
  const common = {
    projectId,
    disabled,
    placeholder,
    onClose,
    className: toTriggerClassName(buttonContainerClassName, buttonClassName),
    tooltip: toSelectTooltip(showTooltip),
    tabIndex,
  };
  const variant = toSelectVariant(buttonVariant);

  return (
    <DropdownCompatFrame className={className} placement={placement}>
      {props.multiple ? (
        <ModuleSelect
          {...common}
          multiple
          value={props.value ?? []}
          onChange={props.onChange}
          // `toSelectVariant` never yields the breadcrumb chrome
          variant={variant as Exclude<SelectVariant, "breadcrumb">}
        />
      ) : (
        <ModuleSelect {...common} value={props.value} onChange={props.onChange} variant={variant} />
      )}
    </DropdownCompatFrame>
  );
}
