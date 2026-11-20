import { Progress as BaseProgress } from "@base-ui/react/progress";

import {
  LinearProgress as LinearProgressElement,
  LinearProgressIndicator,
  type LinearProgressIndicatorProps,
  LinearProgressLabel,
  LinearProgressTrack,
  type LinearProgressTrackProps,
  LinearProgressValue,
} from "../../elements/linear-progress";

export type LinearProgressSize = NonNullable<LinearProgressTrackProps["size"]>;
export type LinearProgressVariant = NonNullable<LinearProgressIndicatorProps["variant"]>;

type LinearProgressOwnProps = Omit<
  BaseProgress.Root.Props,
  "className" | "style" | "value" | "render" | "aria-label"
> & {
  /** Completion from 0 to `max` (default 100). Ignored while `indeterminate`. */
  value: number;
  /** Track thickness: `sm` 5px / `md` 8px. */
  size: LinearProgressSize;
  /** Fill color: `brand` accent, `success`/`warning`/`danger` outcome. */
  variant: LinearProgressVariant;
  /**
   * Show the trailing percentage label. Defaults to `true` when determinate, `false` when
   * `indeterminate` (the `%` would be empty otherwise).
   */
  showValue?: boolean;
  /** Animated fill; `value` is ignored and `aria-valuenow` unset. @default false */
  indeterminate?: boolean;
};

/**
 * The bar always has an accessible name: pass a visible `label` (names it via Base UI's
 * `Progress.Label`) or an `aria-label` — the union makes omitting both a type error rather than a
 * silently unnamed progressbar.
 */
export type LinearProgressProps = LinearProgressOwnProps &
  (
    | {
        /** Visible text label before the track — Base UI's `Progress.Label` (also names the bar). */
        label: string;
        /** Accessible name. Optional when `label` is set — the visible label already names the bar. */
        "aria-label"?: string;
      }
    | {
        label?: undefined;
        /** Accessible name (required when there is no visible `label`). */
        "aria-label": string;
      }
  );

/**
 * A horizontal progress bar with an optional trailing `%` label. Drive it with `value` (0–`max`);
 * the fill and `aria-valuenow` follow. Pass `indeterminate` to ignore `value` and show an animated
 * fill instead (the trailing `%` hides by default in that mode). For a ring, use
 * `CircularProgress`. Grafts Base UI `Progress` (which owns `progressbar`) onto the
 * `elements/linear-progress` styled parts.
 */
export function LinearProgress({
  value,
  size,
  variant,
  showValue,
  indeterminate = false,
  label,
  ...props
}: LinearProgressProps) {
  const max = props.max ?? 100;
  const min = props.min ?? 0;
  // Clamp out-of-range input to `[min, max]` before Base UI derives the fill, `aria-valuenow`, and
  // the `%` label, so they never disagree (e.g. `value={150}` reads 100%, not a 150% overflow).
  // Base UI's own indeterminate signal is `value === null` — `indeterminate` is our boolean-capability
  // wrapper over that (AGENTS rule 6c: a capability is a boolean, not a magic value).
  const clampedValue = indeterminate ? null : Math.min(Math.max(value, min), max);
  // Empty `%` while indeterminate — hide the trailing value unless the caller opts back in.
  const showTrailingValue = showValue ?? !indeterminate;
  return (
    <BaseProgress.Root value={clampedValue} {...props} render={<LinearProgressElement />}>
      {label != null ? (
        <BaseProgress.Label render={<LinearProgressLabel />}>{label}</BaseProgress.Label>
      ) : null}
      <BaseProgress.Track render={<LinearProgressTrack size={size} />}>
        <BaseProgress.Indicator render={<LinearProgressIndicator variant={variant} />} />
      </BaseProgress.Track>
      {showTrailingValue ? (
        <BaseProgress.Value render={<LinearProgressValue />}>
          {(_, currentValue) => (currentValue == null ? "" : `${Math.round(currentValue)}%`)}
        </BaseProgress.Value>
      ) : null}
    </BaseProgress.Root>
  );
}
