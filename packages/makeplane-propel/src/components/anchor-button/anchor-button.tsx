import type * as React from "react";

import {
  AnchorButton as AnchorButtonElement,
  AnchorButtonLabel,
  type AnchorButtonProps as AnchorButtonElementProps,
} from "../../elements/anchor-button";
import { NewTabArrowOutline } from "../../icons";
import { resolveExternalAnchorProps } from "../../internal/external-anchor";
import { Icon } from "../icon";

export type { AnchorButtonSize, AnchorButtonVariant } from "../../elements/anchor-button";

type AnchorButtonRender = NonNullable<AnchorButtonElementProps["render"]>;

type AnchorButtonDestinationProps =
  | { href: string; render?: AnchorButtonRender }
  | { href?: never; render: AnchorButtonRender };

export type AnchorButtonProps = Omit<AnchorButtonElementProps, "children" | "href" | "render"> &
  AnchorButtonDestinationProps & {
    /** Icon rendered beside the label (inline-start by default), e.g. `<Icon icon={Plus} />`. */
    icon?: React.ReactNode;
    /**
     * Which side of the label the icon sits on.
     *
     * @default "start"
     */
    iconPosition?: "start" | "end";
    /** Visible action/link label. */
    label: string;
    /**
     * Opens the destination in a new tab with a trailing arrow and `rel="noreferrer noopener"`.
     * Explicit `target`, `rel`, or `icon` values override these defaults. This flag does not infer
     * whether an `href` is external.
     *
     * @default false
     */
    external?: boolean;
    /**
     * Removes the destination and custom renderer, blocks interaction, and leaves an inert anchor.
     * Toggling this with a custom renderer changes the element type and remounts it.
     */
    disabled?: boolean;
  };

function runNavigationHandler<Event extends React.SyntheticEvent>(
  disabled: boolean | undefined,
  handler: ((event: Event) => void) | undefined,
  event: Event,
) {
  if (disabled) {
    event.preventDefault();
    event.stopPropagation();
    return;
  }
  handler?.(event);
}

function runInteractionHandler<Event extends React.SyntheticEvent>(
  disabled: boolean | undefined,
  handler: ((event: Event) => void) | undefined,
  event: Event,
) {
  if (disabled) return;
  handler?.(event);
}

/**
 * A semantic link with inline text-link chrome. It renders a native `<a>` by default and lays out
 * an optional `icon` beside the label (`iconPosition`). Pass `href`, or use `render` to project the
 * anchor props onto a router or framework link. For lightweight text-only actions, use
 * `TextButton`; for actions with button chrome, use `Button`; for a navigation link with button
 * chrome, use `Button`'s render path.
 */
export function AnchorButton({
  variant,
  size,
  icon,
  iconPosition = "start",
  disabled,
  external = false,
  label,
  href,
  render,
  target,
  rel,
  onAuxClick,
  onClick,
  onKeyDown,
  onKeyUp,
  onMouseDown,
  onPointerDown,
  tabIndex,
  "aria-disabled": ariaDisabled,
  ...props
}: AnchorButtonProps) {
  const externalAnchorProps = resolveExternalAnchorProps({ external, target, rel });
  const resolvedIcon = icon ?? (external ? <Icon icon={NewTabArrowOutline} /> : undefined);
  const resolvedIconPosition = icon == null && external ? "end" : iconPosition;
  const handleAuxClick: React.MouseEventHandler<HTMLAnchorElement> = (event) =>
    runNavigationHandler(disabled, onAuxClick, event);
  const handleClick: React.MouseEventHandler<HTMLAnchorElement> = (event) =>
    runNavigationHandler(disabled, onClick, event);
  const handleKeyDown: React.KeyboardEventHandler<HTMLAnchorElement> = (event) =>
    runInteractionHandler(disabled, onKeyDown, event);
  const handleKeyUp: React.KeyboardEventHandler<HTMLAnchorElement> = (event) =>
    runInteractionHandler(disabled, onKeyUp, event);
  const handleMouseDown: React.MouseEventHandler<HTMLAnchorElement> = (event) =>
    runInteractionHandler(disabled, onMouseDown, event);
  const handlePointerDown: React.PointerEventHandler<HTMLAnchorElement> = (event) =>
    runInteractionHandler(disabled, onPointerDown, event);
  return (
    <AnchorButtonElement
      {...props}
      variant={variant}
      size={size}
      {...externalAnchorProps}
      href={disabled ? undefined : href}
      render={disabled ? undefined : render}
      onAuxClick={handleAuxClick}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      onKeyUp={handleKeyUp}
      onMouseDown={handleMouseDown}
      onPointerDown={handlePointerDown}
      tabIndex={disabled ? -1 : tabIndex}
      aria-disabled={disabled ? true : ariaDisabled}
    >
      {resolvedIconPosition === "start" ? resolvedIcon : null}
      <AnchorButtonLabel>{label}</AnchorButtonLabel>
      {resolvedIconPosition === "end" ? resolvedIcon : null}
    </AnchorButtonElement>
  );
}
