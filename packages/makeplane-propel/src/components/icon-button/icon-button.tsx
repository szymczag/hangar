import { Button as BaseButton } from "@base-ui/react/button";
import type * as React from "react";

import {
  IconButton as IconButtonElement,
  type IconButtonProps as IconButtonElementProps,
} from "../../elements/icon-button";
import { LoadingOutline } from "../../icons";
import { Spinner } from "../../internal/spinner";
import { Tooltip } from "../tooltip";

export type IconButtonProps = Omit<IconButtonElementProps, "children"> & {
  /**
   * Set `false` when `render` swaps the underlying tag away from `<button>` (e.g. an `<a>`): Base
   * UI then adds `role`, tab focus, and Enter/Space activation as appropriate.
   */
  nativeButton?: boolean;
  /**
   * The single icon element to render, usually `<Icon icon={...} />`. The accessible name comes
   * from `aria-label`.
   */
  icon: React.ReactNode;
  /** Required: icon-only buttons have no visible text, so they must be labeled. */
  "aria-label": string;
  /**
   * Show the accessible label in a tooltip on hover (after `Tooltip`'s 300ms) or focus
   * (immediately). Set false when a caller supplies its own tooltip, including one with different
   * timing.
   *
   * @default true
   */
  showTooltip?: boolean;
  /** Shows a spinner in place of the icon, sets `aria-busy`, and makes the button non-interactive. */
  loading?: boolean;
  /** Hard, non-focusable native disabled state (`loading` stays focusable instead). */
  disabled?: boolean;
  /**
   * The button's form behavior.
   *
   * @default "button"
   */
  type?: "submit" | "reset" | "button";
};

/**
 * The ready-made icon-only button: grafts Base UI's `Button` behavior onto the square `IconButton`
 * box, filling it with the provided icon element and swapping in a spinner while `loading`. It can
 * render as `<a>` via `nativeButton={false}` + `render={<a href=… />}` when needed. An `aria-label`
 * is REQUIRED for the accessible name and appears in a tooltip by default.
 */
export function IconButton({
  render,
  nativeButton,
  "aria-label": ariaLabel,
  showTooltip = true,
  icon,
  loading = false,
  disabled,
  type = "button",
  variant,
  size,
  ...props
}: IconButtonProps) {
  // `loading` mirrors Button: Base UI suppresses activation while keeping the button focusable
  // through `focusableWhenDisabled`; `disabled` remains hard-disabled.
  const button = (
    <BaseButton
      {...props}
      aria-label={ariaLabel}
      type={type}
      nativeButton={nativeButton}
      render={
        <IconButtonElement
          variant={variant}
          size={size}
          // The consumer's render swaps the underlying element; the styled part stays the
          // className owner (behavior part outer, styled part as the render target, rule 1a).
          render={render}
        />
      }
      disabled={disabled || loading}
      focusableWhenDisabled={loading ? true : undefined}
      aria-busy={loading ? true : undefined}
    >
      {loading ? (
        <Spinner>
          <LoadingOutline />
        </Spinner>
      ) : (
        icon
      )}
    </BaseButton>
  );

  return (
    <Tooltip
      label={ariaLabel}
      disabled={!showTooltip}
      onOpenChange={(_, details) => {
        // Escape dismisses the tooltip and must still reach a containing dialog or menu.
        if (details.reason === "escape-key") details.allowPropagation();
      }}
    >
      {button}
    </Tooltip>
  );
}
