import * as React from "react";

import { type AvatarSize } from "../../elements/avatar";
import {
  AvatarGroup as AvatarGroupElement,
  type AvatarGroupProps as AvatarGroupElementProps,
} from "../../elements/avatar-group/avatar-group";
import { AvatarGroupCounter } from "../../elements/avatar-group/avatar-group-counter";
import { AvatarGroupOverflow } from "../../elements/avatar-group/avatar-group-overflow";
import { AvatarGroupContext } from "../avatar/avatar-group-context";
import { Tooltip } from "../tooltip/tooltip";
import { TooltipProvider } from "../tooltip/tooltip-provider";

// Figma's "Avatar Groups" component only defines three sizes (Small/Base/Large = 16/20/24px), so
// groups are limited to the matching sizes — narrower than a standalone Avatar's full scale.
export type AvatarGroupSize = Extract<AvatarSize, "2xs" | "xs" | "sm">;

export type AvatarGroupProps = AvatarGroupElementProps & {
  /** Shared size for every avatar in the group; an avatar's own `size` overrides it. */
  size: AvatarGroupSize;
  children?: React.ReactNode;
  /**
   * How many avatars to show before collapsing the rest into the "+N" counter. Pass `Infinity` for
   * no cap.
   *
   * Following the Figma rule, at `total === max + 1` the extra avatar is cheaper than a "+1", so
   * all supplied faces show. If that extra face is not supplied, the counter still counts it.
   * Finite values are floored and clamped to zero; non-finite values mean no cap.
   *
   * @default 2
   */
  max?: number;
  /**
   * The true member count, when the caller renders only the visible avatars. Lets a large set keep
   * an accurate "+N" without materialising — or fetching — every member. Defaults to the number of
   * children. Finite values are floored and clamped to zero. If smaller than the supplied child
   * count, extra children are omitted; non-finite values use the child count.
   */
  total?: number;
  /**
   * Accessible name for the whole stack, e.g. "Ada Lovelace, Grace Hopper and 4 others". The spec
   * asks for a list or a single labelled summary rather than a run of unrelated images.
   */
  label?: string;
  /**
   * The visible counter caps at +9 for every size; the accessible name retains the full hidden
   * count. Accessible name for the counter. Defaults to "N more"; prefer naming who is hidden.
   */
  overflowLabel?: string;
  /**
   * Hidden-member names shown on hover or focus of the counter's wrapper. Omit for a presentational
   * counter. Uses the shared multiline Tooltip; localize this text separately from `overflowLabel`.
   * This non-actionable image wrapper is the explicit exception to presentational avatars staying
   * out of the tab order: focus makes the hidden names keyboard-accessible.
   */
  overflowTooltip?: string;
};

// Flatten fragments without rendering custom components. Composite keys include every fragment
// boundary so identical member keys in separate fragments do not collide.
function flattenAvatarChildren(children: React.ReactNode, parentKey = ""): React.ReactNode[] {
  return React.Children.toArray(children).flatMap((child, index) => {
    if (!React.isValidElement(child)) return [child];
    const key = JSON.stringify([parentKey, child.key ?? index]);
    if (child.type === React.Fragment) {
      return flattenAvatarChildren((child.props as { children?: React.ReactNode }).children, key);
    }
    return [React.cloneElement(child, { key })];
  });
}

function getMemberCounts(childCount: number, max?: number, total?: number) {
  const memberCount =
    total != null && Number.isFinite(total) ? Math.max(0, Math.floor(total)) : childCount;
  const cap = max != null && Number.isFinite(max) ? Math.max(0, Math.floor(max)) : undefined;
  // Keep the max + 1 rule, but count only faces actually supplied by a paginated consumer.
  const visibleCount = Math.min(
    childCount,
    memberCount,
    cap == null || memberCount <= cap + 1 ? memberCount : cap,
  );
  const hiddenCount = memberCount - visibleCount;
  return { visibleCount, hiddenCount };
}

/**
 * The ready-made overlapping avatar stack: shares `size` with every `Avatar` inside via context (an
 * avatar's own `size` still wins), composed around the styled `elements/avatar-group` container.
 * Members retain their standalone ring inside the group. A `TooltipProvider` wraps the stack so
 * member `tooltip`s share open/close timing when sweeping across faces.
 */
export function AvatarGroup({
  size,
  max = 2,
  total,
  label,
  "aria-label": ariaLabel,
  overflowLabel,
  overflowTooltip,
  children,
  ...props
}: AvatarGroupProps) {
  const summaryLabel = label ?? ariaLabel;
  const items = flattenAvatarChildren(children);
  const { visibleCount, hiddenCount } = getMemberCounts(items.length, max, total);
  const hasOverflowTooltip = hiddenCount > 0 && !!overflowTooltip?.trim();
  const counterLabel = overflowLabel ?? `${hiddenCount} more`;
  const faces = items.slice(0, visibleCount);
  const counter =
    hiddenCount > 0 ? (
      <AvatarGroupCounter
        size={size}
        role={hasOverflowTooltip || summaryLabel ? undefined : "img"}
        aria-label={hasOverflowTooltip || summaryLabel ? undefined : counterLabel}
        aria-hidden={hasOverflowTooltip || !!summaryLabel || undefined}
      >
        +{Math.min(hiddenCount, 9)}
      </AvatarGroupCounter>
    ) : null;
  return (
    <AvatarGroupContext.Provider value={size}>
      <TooltipProvider>
        <AvatarGroupElement
          role={summaryLabel ? (hasOverflowTooltip ? "group" : "img") : undefined}
          aria-label={summaryLabel}
          {...props}
        >
          {summaryLabel && hasOverflowTooltip ? (
            // A named summary hides decorative faces, but keeps the focusable counter outside the
            // hidden subtree. An img role on the outer group would hide its tooltip trigger.
            <AvatarGroupElement render={<span />} aria-hidden="true">
              {faces}
            </AvatarGroupElement>
          ) : (
            faces
          )}
          {hasOverflowTooltip ? (
            <Tooltip label={overflowTooltip ?? ""} layout="stacked">
              <AvatarGroupOverflow role="img" tabIndex={0} aria-label={counterLabel}>
                {counter}
              </AvatarGroupOverflow>
            </Tooltip>
          ) : (
            counter
          )}
        </AvatarGroupElement>
      </TooltipProvider>
    </AvatarGroupContext.Provider>
  );
}
