import { Button as BaseButton } from "@base-ui/react/button";
import type * as React from "react";

import {
  type PillVariant,
  Pill as PillElement,
  type PillProps as PillElementProps,
  PillLabel,
  type PillSize,
} from "../../elements/pill";
import { LoadingOutline } from "../../icons";
import { Spinner } from "../../internal/spinner";
import { usePillSize } from "./pill-group-context";

export type { PillVariant };

type PillOwnProps = Omit<
  PillElementProps,
  "children" | "variant" | "placeholder" | "aria-label" | "size"
> & {
  /**
   * Scale. Required, except inside a `PillGroup` — the group shares its own `size` with every
   * segment, so a segment omits it. Omitting it outside a group throws rather than guessing a
   * rung.
   */
  size?: PillSize;
  /**
   * Fill treatment. `outline` (≈ Button secondary) is the bordered chip; `soft` (≈ Button tertiary)
   * is borderless on a filled layer; `ghost` is borderless and transparent at rest, for a trigger
   * whose content is its own box (an avatar stack).
   *
   * @default "outline"
   */
  variant?: PillVariant;
  /**
   * Marks a trigger with no value yet: dims the label and any inherited-tint glyph to the
   * placeholder colour until a value is chosen (still dim while the picker is open).
   *
   * @default false
   */
  placeholder?: boolean;
  /**
   * Element rendered before the label (inline-start), e.g. `<Icon icon={Tag} />` or `<Swatch
   * fill="…" />`.
   */
  startIcon?: React.ReactNode;
  /** Element rendered after the label (inline-end), e.g. `<Icon icon={X} />`. */
  endIcon?: React.ReactNode;
  /** Busy state: hides start/end icons, shows a spinner after the label, and blocks clicks. */
  loading?: boolean;
  /**
   * Set `false` when `render` swaps the underlying tag away from `<button>` (an `<a href>`, a
   * `<div>`): Base UI then adds `role="button"`, tab focus, and Enter/Space activation, and the
   * element's `type="button"` default is withheld — it is valid on nothing but a button.
   */
  nativeButton?: boolean;
};

/**
 * Either a labeled pill or one whose content is a start/end node alone (an avatar stack, an icon) —
 * and the accessible name is required either way. A labeled pill is named by its visible text
 * (`aria-label` optional); a label-less one MUST be named by `aria-label`, so the union makes
 * omitting both a type error rather than a silently unnamed button.
 */
export type PillProps = PillOwnProps &
  ({ label: string; "aria-label"?: string } | { label?: undefined; "aria-label": string });

/**
 * The ready-made pill button: grafts Base UI's `Button` behavior onto the styled `Pill` container
 * (behavior outer, the styled button as the render target), with an optional leading node, the
 * `PillLabel`, an optional trailing node, and a trailing spinner while `loading`. `loading`
 * disables the button while keeping it focusable (`aria-busy`). With no `label` the label part is
 * skipped entirely (an empty flex child would still consume the pill's gap). A consumer `render` —
 * `render={<MenuTrigger />}` to make the pill open a picker — is threaded onto the styled element
 * so the trigger behavior and its `data-popup-open` land on the real `<button>`; the reverse graft
 * (`<MenuTrigger render={<Pill … />}>`) works as well. `nativeButton` rides along the way it does
 * on `Button`, for a `render` that is not a button.
 */
export function Pill({
  size,
  variant = "outline",
  placeholder,
  startIcon,
  endIcon,
  loading = false,
  disabled,
  label,
  render,
  nativeButton,
  ...props
}: PillProps) {
  const resolvedSize = usePillSize(size);
  return (
    <BaseButton
      {...props}
      nativeButton={nativeButton}
      render={
        <PillElement
          size={resolvedSize}
          variant={variant}
          placeholder={placeholder}
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
      {!loading ? startIcon : null}
      {label != null ? <PillLabel>{label}</PillLabel> : null}
      {/* With an end icon the spinner swaps it in place; without one it stays rendered so it
          animates out when `loading` turns false instead of snapping the width. */}
      {endIcon != null && loading ? (
        <Spinner>
          <LoadingOutline />
        </Spinner>
      ) : (
        (endIcon ?? (
          <Spinner active={loading}>
            <LoadingOutline />
          </Spinner>
        ))
      )}
    </BaseButton>
  );
}
