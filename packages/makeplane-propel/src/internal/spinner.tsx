import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva, cx } from "class-variance-authority";
import * as React from "react";

import { nodeSlotClass } from "./node-slot";

/**
 * The shared pending-state glyph slot (rule 4a): an `aria-hidden` `<span>` sizing its single svg
 * child (pass a `LoadingOutline`) to the inherited `--node-size`. Replaces the byte-identical
 * Button/IconButton/Pill spinner parts.
 *
 * The migration uses Propel's radial `LoadingOutline`, which matches the Figma spinner. This
 * replaces the July 2026 choice of Lucide's open-arc `LoaderCircle` for loading controls.
 *
 * Two animations run on mount: the `--animate-spinner-reveal` one-shot grows the slot from zero
 * width and fades it in (so a control entering its loading state widens smoothly instead of
 * snapping), while the perpetual `spin` rotates the glyph. They live on separate elements because
 * an element has a single `animation` slot: the reveal owns the span, the spin owns the svg child.
 * `overflow-hidden` clips the glyph while the slot is still expanding.
 *
 * Exit mirrors it: render the spinner unconditionally with `active={loading}` and, when `active`
 * turns false, it stays mounted playing `--animate-spinner-conceal` (narrowing back to zero width)
 * and unmounts on that animation's end — so the control settles back smoothly instead of snapping.
 * Controls whose box doesn't resize with the spinner (icon-only) just mount it conditionally.
 *
 * The unmount has a timeout fallback so the spinner can never get stuck occupying width: if the
 * conceal animation never reports back (interrupted/cancelled, `prefers-reduced-motion`, disabled
 * animations, or test environments without CSS animations, where `animationend` never fires), the
 * spinner unmounts once the conceal duration has elapsed.
 */
export const spinnerVariants = cva(cx(nodeSlotClass, "overflow-hidden [&>svg]:animate-spin"));

// Conceal duration in `animations.css` (0.2s) plus a buffer for the unmount fallback.
const SPINNER_CONCEAL_TIMEOUT_MS = 250;

export type SpinnerProps = Omit<useRender.ComponentProps<"span">, "className" | "style"> & {
  /**
   * Whether the spinner shows. Turning it false plays the conceal animation before unmounting.
   *
   * @default true
   */
  active?: boolean;
};

export function Spinner({ active = true, render, ...props }: SpinnerProps) {
  const [mounted, setMounted] = React.useState(active);
  // Render-phase remount (the sanctioned derived-state pattern): re-activating mid-exit — or from
  // unmounted — must render the spinner in the same commit, with no one-frame `null` flash. An
  // effect would unmount-then-remount visibly; this keeps the exit seamless.
  if (active && !mounted) setMounted(true);
  // Fallback so the exit can never strand the spinner: if the conceal animation never reports
  // back (cancelled, `prefers-reduced-motion`, animations disabled, no CSS engine in tests),
  // unmount anyway once its duration has elapsed. Cleared on re-activation or unmount; the
  // `animationend` path wins the race when the animation does run.
  React.useEffect(() => {
    if (active || !mounted) return;
    const id = window.setTimeout(() => setMounted(false), SPINNER_CONCEAL_TIMEOUT_MS);
    return () => window.clearTimeout(id);
  }, [active, mounted]);
  const finishExit = (event: React.AnimationEvent<HTMLSpanElement>) => {
    // Ignore bubbling from the svg child; only the slot's own conceal ends the exit.
    if (!active && event.target === event.currentTarget) setMounted(false);
  };
  const defaultProps: useRender.ElementProps<"span"> = {
    "aria-hidden": true,
    // Exactly one slot animation at a time — reveal while active, conceal while exiting — so the
    // exit never depends on `data-ending-style:` specificity beating the reveal class in the
    // cascade. `motion-reduce:animate-none` makes both instant; the timeout above still unmounts.
    className: cx(
      spinnerVariants(),
      active
        ? "animate-spinner-reveal motion-reduce:animate-none"
        : "animate-spinner-conceal motion-reduce:animate-none",
    ),
    ...(active ? undefined : { "data-ending-style": "" }),
    onAnimationEnd: finishExit,
  };
  const element = useRender({
    defaultTagName: "span",
    render,
    props: mergeProps(defaultProps, props),
  });
  return mounted ? element : null;
}
