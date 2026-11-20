import { cx } from "class-variance-authority";
import type * as React from "react";

/**
 * Width-constrained clipper for inside a vertical scrollport.
 *
 * Pairing `overflow-x-clip` with `overflow-y-auto` on the SAME node makes CSS compute `clip` to
 * `hidden`. `hidden` still allows focus-driven `scrollLeft` when wide children grow `scrollWidth`
 * (verified in Chromium). This non-scrolling clipper keeps those children out of the scrollport's
 * scrollable overflow so `scrollWidth === clientWidth` and `scrollLeft` stays 0.
 *
 * The scrollport should still set `overflow-x-clip` itself so `overflow-x` does not compute to
 * `auto` (trackpad sideways pan when a horizontal range exists).
 *
 * `px-0.5 -mx-0.5` is horizontal ring bleed: field `ring-2` chrome would otherwise be masked by
 * this node's x-clip (top/bottom stay protected by the scrollport's own `p-0.5 -m-0.5`, or by
 * layout padding such as Alert Dialog body's `px-5`). Extra `className` is merged on top — it must
 * not replace this base, or callers that pass layout-only classes lose the bleed.
 */
export const scrollportXClipClass = "min-w-0 w-full -mx-0.5 overflow-x-clip px-0.5";

export function ScrollportXClip({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cx(scrollportXClipClass, className)}>{children}</div>;
}
