/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork: compatibility shim, removed in phase 9
//
// The 1.4 `MemberDropdown` call shape over upstream's `MemberSelect` (member/member-select.tsx). The
// roster is the same as before: the project's members without guests when `projectId` is set, the
// workspace members otherwise, or the caller's `memberIds`.

import type { Placement } from "@popperjs/core";
import type { LucideIcon } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
// local imports
import { DropdownCompatFrame, toMemberSelectVariant, toSelectTooltip, toTriggerClassName } from "../compat";
import type { TButtonVariants } from "../types";
import { MemberSelect } from "./member-select";

type TMemberDropdownProps = {
  buttonClassName?: string;
  buttonContainerClassName?: string;
  buttonVariant: TButtonVariants;
  className?: string;
  disabled?: boolean;
  /** No effect: the trigger chrome draws its own chevron where the variant has one. */
  dropdownArrow?: boolean;
  /** No effect, see `dropdownArrow`. */
  dropdownArrowClassName?: string;
  /** No effect: the avatars are part of the trigger. */
  hideIcon?: boolean;
  /** No effect: the empty trigger shows the blocks member glyph. */
  icon?: LucideIcon;
  memberIds?: string[];
  onClose?: () => void;
  /** No effect: the panel takes the blocks width. */
  optionsClassName?: string;
  placeholder?: string;
  placement?: Placement;
  projectId?: string;
  /** No effect: the blocks trigger always renders lazily. */
  renderByDefault?: boolean;
  /** No effect: the trigger names a single member and counts several. */
  showUserDetails?: boolean;
  showTooltip?: boolean;
  tabIndex?: number;
  /** The tooltip's text while nobody is selected. */
  tooltipContent?: string;
} & (
  | {
      multiple: false;
      onChange: (val: string | null) => void;
      value: string | null;
    }
  | {
      multiple: true;
      onChange: (val: string[]) => void;
      value: string[];
    }
);

export function MemberDropdown(props: TMemberDropdownProps) {
  const {
    buttonClassName,
    buttonContainerClassName,
    buttonVariant,
    className,
    disabled,
    memberIds,
    onClose,
    placeholder,
    placement,
    projectId,
    showTooltip,
    tabIndex,
    tooltipContent,
  } = props;
  // plane hooks
  const { t } = useTranslation();
  // derived values
  const resolvedPlaceholder = placeholder ?? t("members");
  const hasValue = Array.isArray(props.value) ? props.value.length > 0 : !!props.value;
  const common = {
    projectId,
    memberIds,
    variant: toMemberSelectVariant(buttonVariant, hasValue),
    disabled,
    placeholder: resolvedPlaceholder,
    onClose,
    className: toTriggerClassName(buttonContainerClassName, buttonClassName),
    tooltip: toSelectTooltip(showTooltip, resolvedPlaceholder, tooltipContent),
    tabIndex,
  };

  return (
    <DropdownCompatFrame className={className} placement={placement}>
      {props.multiple ? (
        <MemberSelect {...common} multiple value={props.value ?? []} onChange={props.onChange} />
      ) : (
        <MemberSelect {...common} value={props.value} onChange={props.onChange} />
      )}
    </DropdownCompatFrame>
  );
}
