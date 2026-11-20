import { Progress as BaseProgress } from "@base-ui/react/progress";

import {
  CircularProgress as CircularProgressElement,
  CircularProgressIndicator,
  type CircularProgressIndicatorProps,
  type CircularProgressProps as CircularProgressElementProps,
  CircularProgressSvg,
  CircularProgressTrack,
} from "../../elements/circular-progress";

export type CircularProgressSize = NonNullable<CircularProgressElementProps["size"]>;
export type CircularProgressVariant = NonNullable<CircularProgressIndicatorProps["variant"]>;

// Circle geometry per size (Figma 5736-3457/3460): a 16px (sm) / 20px (md) box holding a
// 2px-stroke ring; centerline radius = (diameter - stroke) / 2 -> 6 (sm) / 8 (md).
const RING_GEOMETRY: Record<CircularProgressSize, { box: number; radius: number }> = {
  sm: { box: 16, radius: 6 },
  md: { box: 20, radius: 8 },
};
const RING_STROKE = 2;

export type CircularProgressProps = Omit<
  BaseProgress.Root.Props,
  "className" | "style" | "value" | "render"
> & {
  /** Completion from 0 to `max` (default 100). Ignored while `indeterminate`. */
  value: number;
  /** Diameter: `sm` 16px / `md` 20px. */
  size: CircularProgressSize;
  /** Arc color: `brand` accent, `success`/`warning`/`danger` outcome. */
  variant: CircularProgressVariant;
  /** Accessible name (required). */
  "aria-label": string;
  /** Spin a fixed quarter arc; `value` is ignored and `aria-valuenow` unset. @default false */
  indeterminate?: boolean;
};

/**
 * A small progress ring (no label — too small). Drive it with `value` (0–`max`); the arc and
 * `aria-valuenow` follow. Pass `indeterminate` to ignore `value` and spin a fixed quarter arc
 * instead. For a bar with an optional label, use `LinearProgress`. Composes the
 * `elements/circular-progress` primitives on Base UI `Progress`.
 */
export function CircularProgress({
  value,
  size,
  variant,
  indeterminate = false,
  ...props
}: CircularProgressProps) {
  const { box, radius } = RING_GEOMETRY[size];
  const circumference = 2 * Math.PI * radius;
  const max = props.max ?? 100;
  const min = props.min ?? 0;
  const span = max - min;
  // Clamp once so the arc and `aria-valuenow` never disagree for out-of-range input, and derive the
  // fraction from both bounds so a non-zero `min` maps correctly. While indeterminate a fixed
  // quarter arc shows; the svg part spins it off `data-indeterminate`. Base UI's own indeterminate
  // signal is `value === null` — `indeterminate` is our boolean-capability wrapper over that
  // (AGENTS rule 6c: a capability is a boolean, not a magic value).
  const clampedValue = indeterminate ? null : Math.min(Math.max(value, min), max);
  const fraction = clampedValue == null ? 0.25 : span > 0 ? (clampedValue - min) / span : 0;
  const dashOffset = circumference * (1 - fraction);
  const center = box / 2;
  return (
    <BaseProgress.Root
      value={clampedValue}
      {...props}
      render={<CircularProgressElement size={size} />}
    >
      <CircularProgressSvg viewBox={`0 0 ${box} ${box}`}>
        <CircularProgressTrack cx={center} cy={center} r={radius} strokeWidth={RING_STROKE} />
        <CircularProgressIndicator
          variant={variant}
          cx={center}
          cy={center}
          r={radius}
          strokeWidth={RING_STROKE}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
        />
      </CircularProgressSvg>
    </BaseProgress.Root>
  );
}
