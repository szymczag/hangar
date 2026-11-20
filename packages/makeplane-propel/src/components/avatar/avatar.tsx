import { Avatar as BaseAvatar } from "@base-ui/react/avatar";
import * as React from "react";

import {
  Avatar as AvatarElement,
  AvatarFallback,
  AvatarImage,
  type AvatarSize,
  type AvatarProps as AvatarElementProps,
  getAvatarVariant,
  getAvatarVariantSeed,
} from "../../elements/avatar";
import { UserAltOutline } from "../../icons";
import { getAvatarInitials, getFirstAvatarInitial } from "../../internal/avatar-shared";
import { Icon } from "../../internal/icon";
import { Tooltip } from "../tooltip/tooltip";
import { AvatarGroupContext } from "./avatar-group-context";

export type AvatarProps = Omit<AvatarElementProps, "size"> & {
  /**
   * Avatar size. Optional here — resolved from the `AvatarGroup` context, else `md`.
   *
   * @default "md"
   */
  size?: AvatarSize;
  /** Image URL. When omitted, or while it is loading/failing, the fallback shows. */
  src?: string;
  /** Accessible name for the avatar (the person it represents). */
  alt?: string;
  /** Initials shown when there is no image. When omitted too, a person icon shows. */
  fallback?: React.ReactNode;
  /** Milliseconds before the fallback shows, to avoid a flash while `src` loads quickly. */
  delay?: number;
  /**
   * Name shown in a tooltip on hover. Pass `true` to reuse `alt`, or a string for the label (works
   * without `alt`). Omit for no tooltip.
   */
  tooltip?: boolean | string;
};

/**
 * The ready-made avatar: an image that falls back to initials (or an anonymous person icon),
 * composed from the `elements/avatar` parts (`Avatar` root + `AvatarImage` + `AvatarFallback`).
 * Pass `src` for the photo and `fallback` for initials; the initials color is chosen automatically
 * and is not a consumer prop.
 */
export function Avatar({
  size,
  src,
  alt,
  fallback,
  delay,
  tooltip,
  tabIndex,
  ...props
}: AvatarProps) {
  // Base UI shows the fallback whenever the image is absent, loading, or failed, so the
  // colored-initials styling lives on the Fallback element itself. The anonymous person icon
  // renders in the icon slot over the root's neutral backdrop when there are no initials.
  const groupSize = React.useContext(AvatarGroupContext);
  const effectiveSize = size ?? groupSize;
  // Spec: initials are "up to two characters — first letter of the first and last name token;
  // single-token names use the first letter only", uppercased. Deriving them here when `fallback`
  // is omitted makes the spec-correct rendering the default, instead of something every call site
  // reimplements — and stops an omitted `fallback` silently degrading a named avatar to the
  // anonymous icon.
  const derivedInitials = React.useMemo(() => getAvatarInitials(alt), [alt]);
  const resolvedFallback = fallback ?? derivedInitials;
  const displayFallback =
    effectiveSize === "2xs" && typeof resolvedFallback === "string"
      ? getFirstAvatarInitial(resolvedFallback)
      : resolvedFallback;
  const hasInitials = resolvedFallback != null;
  // The anonymous glyph is the shared `Icon` (muted, static — no input-focus brightening), sized by
  // the `--node-size` the root sets per size, so there is no avatar-specific icon part.
  // Variant is always system-chosen (never a consumer prop): seed a stable color from the name, else
  // the initials text, so unnamed avatars vary by initials instead of collapsing onto one color.
  const resolvedVariant = getAvatarVariant(getAvatarVariantSeed(alt, resolvedFallback));
  // Named vs decorative: with an accessible name (`alt`, else a string `tooltip`), expose it for
  // every state (image / initials / icon) via `role="img"`; without one, mark the avatar
  // `aria-hidden` so it is skipped rather than announced as a nameless image (the name lives in
  // adjacent text). This is the only correct pair — a `role="img"` with no name is an axe violation.
  // `true` reuses `alt`; a non-empty string is the label even when `alt` is omitted. Empty string /
  // `true` with no `alt` → no tip. A string tooltip without `alt` also becomes the accessible name
  // so the trigger is not `aria-hidden` while showing a hover-only name.
  const tooltipLabel =
    tooltip === true ? alt : typeof tooltip === "string" ? tooltip || undefined : undefined;
  const accessibleName = alt ?? tooltipLabel;
  const a11y =
    accessibleName != null
      ? { role: "img", "aria-label": accessibleName }
      : { "aria-hidden": true };
  const avatar = (
    // Base UI `Avatar` behavior/context grafts onto the styled `elements/avatar` parts via `render`
    // (behavior part outer). `{...props}` spreads before the hardcoded a11y attrs so a stray
    // same-named prop can never silently override them (matches `components/workspace-avatar`).
    // The avatar is presentational: "it carries no interaction of its own … a presentational avatar
    // is not in the tab order". A tooltip must not silently create a tab stop — an interactive
    // avatar gets its focusability from the wrapper (button/link) the caller provides, which is
    // also where the focus ring belongs so it is not clipped by the circular mask.
    <BaseAvatar.Root
      {...props}
      render={<AvatarElement size={effectiveSize} />}
      {...a11y}
      tabIndex={tabIndex}
    >
      {src ? <BaseAvatar.Image render={<AvatarImage />} src={src} alt="" /> : null}
      {hasInitials ? (
        <BaseAvatar.Fallback delay={delay} render={<AvatarFallback variant={resolvedVariant} />}>
          {displayFallback}
        </BaseAvatar.Fallback>
      ) : (
        <BaseAvatar.Fallback delay={delay} render={<Icon tint="muted" />}>
          <UserAltOutline />
        </BaseAvatar.Fallback>
      )}
    </BaseAvatar.Root>
  );
  return tooltipLabel ? <Tooltip label={tooltipLabel}>{avatar}</Tooltip> : avatar;
}
