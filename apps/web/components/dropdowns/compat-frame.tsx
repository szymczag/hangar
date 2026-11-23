/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork: compatibility shim, removed in phase 9

import { useMemo } from "react";
import type { ReactNode } from "react";
import type { Placement } from "@popperjs/core";
import { SelectDropdownPlacementContext } from "@plane/blocks/select";
import { cn } from "@plane/utils";
// local imports
import { toDropdownPlacement } from "./compat";

type TDropdownCompatFrameProps = {
  children: ReactNode;
  className?: string;
  placement?: Placement;
};

/**
 * The 1.4 dropdowns rendered inside `<div className={cn("h-full", className)}>` (Headless UI's
 * `ComboDropDown`), and callers size and group-hover through that wrapper, so it stays. `placement`
 * reaches the Base UI popup through the blocks placement context.
 */
export function DropdownCompatFrame(props: TDropdownCompatFrameProps) {
  const { children, className, placement } = props;
  const dropdownPlacement = useMemo(() => toDropdownPlacement(placement), [placement]);
  const content = <div className={cn("h-full", className)}>{children}</div>;
  if (!dropdownPlacement) return content;
  return (
    <SelectDropdownPlacementContext.Provider value={dropdownPlacement}>
      {content}
    </SelectDropdownPlacementContext.Provider>
  );
}
