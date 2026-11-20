import { Button as BaseButton } from "@base-ui/react/button";
import type * as React from "react";

import {
  IconPill as IconPillElement,
  type IconPillProps as IconPillElementProps,
  type IconPillSize,
} from "../../elements/pill";
import { LoadingOutline } from "../../icons";
import { Spinner } from "../../internal/spinner";
import { useIconPillSize } from "./pill-group-context";

export type IconPillProps = Omit<IconPillElementProps, "children" | "size"> & {
  /**
   * Scale. Required, except inside a `PillGroup` — the group shares its own `size` with every
   * segment, so a segment omits it. Omitting it outside a group throws rather than guessing a
   * rung.
   */
  size?: IconPillSize;
  /** The icon element, usually `<Icon icon={...} />`. */
  icon: React.ReactNode;
  /** Required: icon-only pills have no visible text, so they must be labeled. */
  "aria-label": string;
  /** Busy state: swaps the icon for a spinner and blocks clicks. */
  loading?: boolean;
  /**
   * Set `false` when `render` swaps the underlying tag away from `<button>` (an `<a href>`, a
   * `<span>`): Base UI then adds `role="button"`, tab focus, and Enter/Space activation, and the
   * element's `type="button"` default is withheld — it is valid on nothing but a button.
   */
  nativeButton?: boolean;
};

/**
 * The ready-made icon-only pill: grafts Base UI's `Button` behavior onto the square `IconPill`
 * container (behavior outer, the styled button as the render target), filling it with the icon (or
 * a spinner while `loading`). `loading` disables the button while keeping it focusable
 * (`aria-busy`). An `aria-label` is required for the accessible name. A consumer `render`
 * (`render={<MenuTrigger />}`) is threaded onto the styled element, so the trigger behavior and its
 * `data-popup-open` land on the real `<button>` and the pill wears its open look.
 */
export function IconPill({
  size,
  loading = false,
  disabled,
  icon,
  render,
  nativeButton,
  ...props
}: IconPillProps) {
  const resolvedSize = useIconPillSize(size);
  return (
    <BaseButton
      {...props}
      nativeButton={nativeButton}
      render={
        <IconPillElement
          size={resolvedSize}
          // The consumer's render swaps the underlying element; the styled part stays the
          // className owner (behavior part outer, styled part as the render target, rule 1a).
          render={render}
          // A non-button target must not carry the element's `type="button"` default; an explicit
          // `undefined` wins the merge (`mergeProps` assigns it) and the attribute is not emitted.
          {...(nativeButton === false ? { type: undefined } : undefined)}
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
}
