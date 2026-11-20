/**
 * The menu's shrink-before-flip side decision, as arithmetic.
 *
 * Base UI's flip default jumps to the other side of the trigger whenever the popup's wanted height
 * does not fit and the other side merely has more room — even when the preferred side held a
 * perfectly usable menu. `resolveFitSide` replaces that preference with a floor: stay on the
 * preferred side while its usable space clears the floor; flip only when it does not and the
 * opposite side does; when neither clears it, take the bigger side, because a floor decides — it
 * cannot conjure space. The full argument, drawn and measured, is the "Height" section of the kato
 * lab's /propel/geometry page.
 *
 * Pure over rects so the decision is unit-testable without layout; `MenuContent` measures the live
 * elements and calls this with numbers.
 */

/**
 * The height below which a shrunken menu stops being a list you scan and becomes a truncation you
 * fight: six menu rows (6 × 32px) plus the panel's own chrome (2 × 4px padding + 2 × 1px border).
 * Derived, not asserted — change the row and the floor moves with it.
 */
export const MENU_FIT_FLOOR_PX = 6 * 32 + 2 * 4 + 2 * 1;

export type FitSide = "top" | "bottom";

export type ResolveFitSideArgs = {
  /** The trigger's rect, viewport coordinates. */
  trigger: { top: number; bottom: number };
  /** The collision boundary's rect, viewport coordinates. */
  boundary: { top: number; bottom: number };
  /** The side the consumer asked for. */
  preferred: FitSide;
  /** Gap between trigger and panel (`sideOffset`). */
  sideOffset: number;
  /** Gap kept from the boundary edge (`collisionPadding`). */
  collisionPadding: number;
  /** Usable-height floor under which the preferred side is abandoned. */
  floor: number;
};

/** Usable space on each vertical side of the trigger, after the offset and the gutter. */
export function usableSpace(
  args: Pick<ResolveFitSideArgs, "trigger" | "boundary" | "sideOffset" | "collisionPadding">,
): { top: number; bottom: number } {
  const chrome = args.sideOffset + args.collisionPadding;
  return {
    top: args.trigger.top - args.boundary.top - chrome,
    bottom: args.boundary.bottom - args.trigger.bottom - chrome,
  };
}

export function resolveFitSide(args: ResolveFitSideArgs): FitSide {
  const space = usableSpace(args);
  const opposite: FitSide = args.preferred === "bottom" ? "top" : "bottom";
  if (space[args.preferred] >= args.floor) return args.preferred;
  if (space[opposite] >= args.floor) return opposite;
  return space[opposite] > space[args.preferred] ? opposite : args.preferred;
}
