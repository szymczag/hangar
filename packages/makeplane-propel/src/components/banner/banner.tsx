import type * as React from "react";

import {
  Banner as BannerElement,
  BannerActions,
  BannerBody,
  BannerDescription,
  BannerIcon,
  type BannerProps as BannerElementProps,
  type BannerVariant,
  BannerTitle,
} from "../../elements/banner";
import {
  CloseOutline,
  InfoOutline,
  WarningCircleOutline,
  WarningTriangleOutline,
} from "../../icons";
import { Icon } from "../icon";
import { IconButton } from "../icon-button";

export type { BannerVariant, BannerPlacement, BannerSize } from "../../elements/banner";

// The leading icon the system picks per variant when none is supplied. Treated as
// content (overridable via `icon`), not a style placement.
const variantIcon: Record<BannerVariant, typeof InfoOutline> = {
  neutral: InfoOutline,
  info: InfoOutline,
  accent: InfoOutline,
  warning: WarningTriangleOutline,
  danger: WarningCircleOutline,
};

export type BannerProps = Omit<BannerElementProps, "children" | "title"> & {
  /** Banner scale, independent of placement. @default "md" */
  size?: BannerElementProps["size"];
  /** Accessible name for the dismiss control; localize at the call site. @default "Dismiss" */
  dismissLabel?: string;
  /**
   * Node rendered before the message (inline-start). Defaults to a variant-appropriate Plane icon;
   * pass `null` to hide it. Sized to the banner's node size. Decorative, kept out of the name.
   */
  icon?: React.ReactNode;
  /** The banner's headline. Rendered as its own block above any description body. */
  title?: React.ReactNode;
  /** Body text rendered under the title. */
  description?: React.ReactNode;
  /**
   * Trailing CTA buttons, placed after the message. Per Figma the banner carries up to three CTAs
   * (primary / secondary / tertiary). The dismiss control is a separate slot — pass `onDismiss`
   * rather than appending a dismiss button here.
   *
   * Actions move below the message when space is constrained and wrap within the banner. Long
   * button labels can truncate visually while retaining their full accessible name.
   */
  actions?: React.ReactNode;
  /**
   * When set, renders the dedicated dismiss control — a ghost, icon-only `IconButton` fixed at the
   * banner's trailing edge (after `actions`), matching Figma's always-last "Close" anatomy node.
   * Consumers own visibility: the handler fires on click; the banner does not hide itself.
   */
  onDismiss?: () => void;
};

/**
 * The ready-made banner: composes the atomic banner parts — the variant icon, the message body
 * (`title` + `description`), trailing `actions`, and an optional trailing `onDismiss` control — so
 * consumers pass content, not layout. Drop down to `@makeplane/propel/elements/banner` to assemble
 * the parts directly.
 */
export function Banner({
  placement,
  size = "md",
  variant,
  icon,
  title,
  description,
  actions,
  onDismiss,
  dismissLabel = "Dismiss",
  ...props
}: BannerProps) {
  const DefaultIcon = variantIcon[variant];
  // `undefined` → variant default; `null` → hidden; any node → custom. Resolve once so a single
  // `BannerIcon` wrapper renders whatever survives.
  const resolvedIcon = icon === undefined ? <DefaultIcon /> : icon;
  return (
    <BannerElement size={size} placement={placement} variant={variant} {...props}>
      {resolvedIcon ? (
        <BannerIcon placement={placement} variant={variant} size={size}>
          {resolvedIcon}
        </BannerIcon>
      ) : null}
      <BannerBody size={size} placement={placement} variant={variant}>
        {title ? (
          <BannerTitle size={size} placement={placement}>
            {title}
          </BannerTitle>
        ) : null}
        {description ? <BannerDescription size={size}>{description}</BannerDescription> : null}
      </BannerBody>
      {actions || onDismiss ? (
        <BannerActions>
          {actions}
          {onDismiss ? (
            <IconButton
              variant="ghost"
              size="xs"
              aria-label={dismissLabel}
              onClick={onDismiss}
              icon={<Icon icon={CloseOutline} />}
            />
          ) : null}
        </BannerActions>
      ) : null}
    </BannerElement>
  );
}
