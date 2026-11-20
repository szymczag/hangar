import type * as React from "react";

import {
  SplitButton as SplitButtonElement,
  type SplitButtonProps as SplitButtonElementProps,
} from "../../elements/split-button";
import { ChevronDownOutline } from "../../icons";
import { Icon } from "../icon";
import { IconButton } from "../icon-button";
import { MenuTrigger } from "../menu";

export type IconSplitButtonProps = Omit<SplitButtonElementProps, "children"> & {
  /** The main segment's icon element, usually `<Icon icon={...} />`. */
  icon: React.ReactNode;
  /** Required: the main segment is icon-only, so it has no visible text to name it. */
  "aria-label": string;
  /** Click handler of the main action segment. */
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
  /**
   * Shows a spinner on the main segment and makes both segments non-interactive (the main segment
   * stays focusable, IconButton's soft-disabled loading state).
   */
  loading?: boolean;
  /** Disables both segments. */
  disabled?: boolean;
  /**
   * The main segment's form behavior.
   *
   * @default "button"
   */
  type?: "submit" | "reset" | "button";
  /**
   * Accessible name of the menu-opening segment.
   *
   * @default "More options"
   */
  menuLabel?: string;
};

/**
 * The icon-only split button (Figma "Icon Split button", 9441:1252): two square `IconButton`s in
 * the shared `SplitButton` frame — a main action segment plus a chevron segment grafted as the
 * surrounding menu's `MenuTrigger`. Both segments are the same square box at every rung (Figma
 * measures 24+24, 28+28, 32+32; primary adds the frame's 1px gap, secondary runs them flush), so
 * neither takes a width override. Neutral only, like `SplitButton` — no danger/error variant.
 *
 * Use it over `SplitButton` only where a glyph alone names the action unambiguously (a toolbar `+`,
 * say). An icon-only main segment gives no way to tell what a plain click will do without hovering;
 * anywhere that matters, keep the text label and use `SplitButton`.
 *
 * It ships no menu of its own — render it as a `Menu`'s child, with the surface as a sibling
 * `MenuContent`:
 *
 * ```tsx
 * <Menu>
 *   <IconSplitButton
 *     variant="primary"
 *     size="md"
 *     icon={<Icon icon={Plus} />}
 *     aria-label="Create"
 *   />
 *   <MenuContent align="end">
 *     <MenuItem label="Create from template" />
 *   </MenuContent>
 * </Menu>;
 * ```
 */
export function IconSplitButton({
  variant,
  size,
  icon,
  onClick,
  loading = false,
  disabled,
  type = "button",
  menuLabel = "More options",
  // Pulled out of the rest: it names the main segment's button, not the frame `<div>` a
  // `{...props}` spread would land it on.
  "aria-label": ariaLabel,
  ...props
}: IconSplitButtonProps) {
  return (
    <SplitButtonElement variant={variant} size={size} {...props}>
      <IconButton
        variant={variant}
        size={size}
        icon={icon}
        aria-label={ariaLabel}
        onClick={onClick}
        loading={loading}
        disabled={disabled}
        type={type}
      />
      <MenuTrigger
        disabled={disabled || loading}
        render={
          <IconButton
            variant={variant}
            size={size}
            icon={<Icon icon={ChevronDownOutline} />}
            aria-label={menuLabel}
          />
        }
      />
    </SplitButtonElement>
  );
}
