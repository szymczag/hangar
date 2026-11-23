/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork: compatibility shim, removed in phase 9
//
// Shared prop adapters for the 1.4 dropdown module paths (`state/dropdown`, `priority`, `date`, ...).
// Upstream v1.5.0 replaced those modules with the `*-select.tsx` bindings over `@plane/blocks`; the
// old paths now render the new components so that the screens still on the 1.4 call shape (work
// items, cycles, modules, views, pages, ...) need no change until their own phase moves them.

import type { Placement } from "@popperjs/core";
import type { MemberSelectVariant } from "@plane/blocks/property-select";
import type { SelectDropdownPlacement, SelectTooltip, SelectVariant } from "@plane/blocks/select";
import { cn } from "@plane/utils";
// local imports
import type { TButtonVariants } from "./types";

/** Whether the 1.4 button variant printed the selected value's text. */
export const isTextButtonVariant = (buttonVariant: TButtonVariants): boolean => buttonVariant.endsWith("-with-text");

/**
 * Maps a 1.4 button variant onto the blocks trigger chrome, following the choices upstream made when
 * it moved the same call sites: bordered buttons become pills, background buttons the filled
 * select, transparent buttons the ghost select, and the "without text" variants the icon-only
 * trigger.
 */
export function toSelectVariant(buttonVariant: TButtonVariants): SelectVariant {
  switch (buttonVariant) {
    case "border-with-text":
      return "pill-md";
    case "background-with-text":
      return "select-md";
    case "transparent-with-text":
      return "select-ghost-md";
    default:
      return "icon-md";
  }
}

/**
 * Member triggers: a "without text" variant with people selected showed their avatars only, which is
 * the avatar group; with nobody selected it showed the icon.
 */
export function toMemberSelectVariant(buttonVariant: TButtonVariants, hasValue: boolean): MemberSelectVariant {
  if (isTextButtonVariant(buttonVariant)) return toSelectVariant(buttonVariant);
  return hasValue ? "avatar-group-md" : "icon-md";
}

/** `showTooltip` plus an optional heading/empty text becomes the blocks `tooltip` prop. */
export function toSelectTooltip(
  showTooltip: boolean | undefined,
  heading?: string,
  emptyContent?: string
): SelectTooltip {
  if (!showTooltip) return false;
  if (heading === undefined && emptyContent === undefined) return true;
  return { heading, emptyContent };
}

/** Popper's `placement` ("bottom-start", "top", ...) as a Base UI side and alignment. */
export function toDropdownPlacement(placement: Placement | undefined): SelectDropdownPlacement | null {
  if (!placement || placement.startsWith("auto")) return null;
  const [side, alignment] = placement.split("-") as [SelectDropdownPlacement["side"], "start" | "end" | undefined];
  return { side, align: alignment ?? "center" };
}

/** The old button container and button classes both land on the single blocks trigger. */
export const toTriggerClassName = (buttonContainerClassName?: string, buttonClassName?: string): string | undefined =>
  cn(buttonContainerClassName, buttonClassName) || undefined;
