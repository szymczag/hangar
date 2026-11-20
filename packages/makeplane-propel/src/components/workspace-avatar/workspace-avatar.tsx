import { Avatar as BaseAvatar } from "@base-ui/react/avatar";
import * as React from "react";

import { getAvatarVariant, getAvatarVariantSeed } from "../../elements/avatar";
import {
  WorkspaceAvatar as WorkspaceAvatarElement,
  WorkspaceAvatarFallback,
  WorkspaceAvatarImage,
  type WorkspaceAvatarProps as WorkspaceAvatarElementProps,
} from "../../elements/workspace-avatar";
import { BuildingOutline } from "../../icons";
import { getAvatarInitials, getFirstAvatarInitial } from "../../internal/avatar-shared";
import { Icon } from "../../internal/icon";
import { Tooltip } from "../tooltip/tooltip";

export type WorkspaceAvatarProps = WorkspaceAvatarElementProps & {
  /** Workspace logo URL. Falls back to the initial when absent/loading/failed. */
  src?: string;
  /** Accessible name for the workspace avatar. */
  alt?: string;
  /**
   * Shown when there is no logo. When omitted, derives up to two initials from `alt`; without a
   * name, shows the anonymous workspace icon.
   */
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
 * The ready-made workspace avatar: a logo that falls back to initials, or an anonymous workspace
 * icon when there are no initials either, composed from the `elements/workspace-avatar` parts
 * (`WorkspaceAvatar` root + `WorkspaceAvatarImage` + `WorkspaceAvatarFallback`). Pass `src` for the
 * logo and `fallback` for initials; the initials color is chosen automatically and is not a
 * consumer prop.
 */
export function WorkspaceAvatar({
  size,
  src,
  alt,
  fallback,
  delay,
  tooltip,
  tabIndex,
  ...props
}: WorkspaceAvatarProps) {
  // Base UI shows the fallback whenever the logo is absent, loading, or failed, so the
  // colored-initials styling lives on the Fallback element itself. The anonymous workspace glyph is
  // the shared `Icon` (muted, static), sized by the `--node-size` the root sets per size — no
  // workspace-specific icon part.
  // Spec: a workspace initial is derived the same way a person's is ("AC" in the Type row), so
  // deriving it here keeps the two families consistent and stops an omitted `fallback` silently
  // degrading a named workspace to the anonymous building glyph.
  const derivedInitials = React.useMemo(() => getAvatarInitials(alt), [alt]);
  const resolvedFallback = fallback ?? derivedInitials;
  const displayFallback =
    size === "2xs" && typeof resolvedFallback === "string"
      ? getFirstAvatarInitial(resolvedFallback)
      : resolvedFallback;
  const hasInitials = resolvedFallback != null;
  // Variant is always system-chosen (never a consumer prop): seed a stable color from the name, else
  // the initials text, so unnamed workspaces vary by initials instead of collapsing onto one color.
  const resolvedVariant = getAvatarVariant(getAvatarVariantSeed(alt, resolvedFallback));
  // Named vs decorative: with an accessible name (`alt`, else a string `tooltip`), expose it for
  // every state (logo / initials) via `role="img"`; without one, mark the avatar `aria-hidden` so it
  // is skipped rather than announced as a nameless image (the name lives in adjacent text). This is
  // the only correct pair — a `role="img"` with no name is an axe violation. (Matches
  // `components/avatar`.) A string tooltip without `alt` also becomes the accessible name so the
  // trigger is not `aria-hidden` while showing a hover-only name.
  const tooltipLabel =
    tooltip === true ? alt : typeof tooltip === "string" ? tooltip || undefined : undefined;
  const accessibleName = alt ?? tooltipLabel;
  const a11y =
    accessibleName != null
      ? { role: "img", "aria-label": accessibleName }
      : { "aria-hidden": true };
  const avatar = (
    // Base UI's `Avatar` behavior grafts onto the styled `elements` parts via `render` (behavior part
    // outer, styled part as the render target). `{...props}` spreads before the hardcoded a11y attrs
    // so a stray same-named prop can never silently override them.
    // Presentation alone does not add a tab stop. Interactive callers own a button/link wrapper.
    <BaseAvatar.Root
      {...props}
      render={<WorkspaceAvatarElement size={size} />}
      {...a11y}
      tabIndex={tabIndex}
    >
      {src ? <BaseAvatar.Image render={<WorkspaceAvatarImage />} src={src} alt="" /> : null}
      {hasInitials ? (
        <BaseAvatar.Fallback
          delay={delay}
          render={<WorkspaceAvatarFallback variant={resolvedVariant} />}
        >
          {displayFallback}
        </BaseAvatar.Fallback>
      ) : (
        <BaseAvatar.Fallback delay={delay} render={<Icon tint="muted" />}>
          <BuildingOutline />
        </BaseAvatar.Fallback>
      )}
    </BaseAvatar.Root>
  );
  return tooltipLabel ? <Tooltip label={tooltipLabel}>{avatar}</Tooltip> : avatar;
}
