import type { SVGProps } from "react";

import { WorkItemBacklog } from "../icons/work-item-states/work-item-backlog";
import { WorkItemCancelled } from "../icons/work-item-states/work-item-cancelled";
import { WorkItemDone } from "../icons/work-item-states/work-item-done";

export type StateGroup = "backlog" | "unstarted" | "started" | "completed" | "cancelled";
export type StateIconSize = "xs" | "sm" | "md" | "lg" | "xl";

export type StateProgressIconProps = SVGProps<SVGSVGElement> & {
  /** Progress as a fraction (0–1) or percentage (above 1–100). Defaults to 100%. */
  percentage?: number;
};

export type StateGroupIconProps = Omit<StateProgressIconProps, "width" | "height"> & {
  /** Workflow group; started and unstarted render continuous progress. */
  stateGroup: StateGroup;
  /** Plane EE icon size: xs=10, sm=12, md=14, lg=16, xl=18px. @default "sm" */
  size?: StateIconSize;
};

const dimensions: Record<StateIconSize, number> = { xs: 10, sm: 12, md: 14, lg: 16, xl: 18 };
const staticGroups = {
  backlog: WorkItemBacklog,
  completed: WorkItemDone,
  cancelled: WorkItemCancelled,
};

/** Convert the Plane EE percentage convention to a bounded fraction. */
function progressFraction(percentage: number = 100): number {
  if (!Number.isFinite(percentage)) return 1;
  return Math.max(0, Math.min(1, percentage <= 1 ? percentage : percentage / 100));
}

// Continuous geometry renders arbitrary percentages rather than fixed quarter steps.
// Fifteen round radial ticks disappear clockwise as the solid outer ring advances from twelve.
function ProgressGlyph({
  percentage,
  started,
  color,
  width = "1em",
  height = "1em",
  className,
  ...props
}: StateProgressIconProps & { started: boolean }) {
  const fraction = progressFraction(percentage);
  const circumference = 12 * Math.PI;
  const remainingTicks = Array.from({ length: 15 }, (_, index) => index).filter(
    (index) => index / 15 >= fraction,
  );

  return (
    <svg
      viewBox="0 0 16 16"
      width={width}
      height={height}
      fill="none"
      aria-hidden="true"
      color={color ?? `var(--txt-icon-states-${started ? "started" : "unstarted"}, currentColor)`}
      className={className ? `shrink-0 ${className}` : "shrink-0"}
      {...props}
    >
      {remainingTicks.map((index) => (
        <line
          key={index}
          x1="8"
          y1="1.5"
          x2="8"
          y2="2.25"
          stroke="currentColor"
          strokeWidth="1.21"
          strokeLinecap="round"
          transform={`rotate(${index * 24} 8 8)`}
        />
      ))}
      {started && <circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.5" />}
      {fraction > 0 && (
        <circle
          cx="8"
          cy="8"
          r="6"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - fraction)}
          transform="rotate(-90 8 8)"
        />
      )}
    </svg>
  );
}

/** Todo glyph with continuous progress and the unstarted semantic color. */
export function UnstartedGroupIcon(props: StateProgressIconProps) {
  return <ProgressGlyph {...props} started={false} />;
}

/** In-progress glyph with an inner ring and continuous outer progress. */
export function StartedGroupIcon(props: StateProgressIconProps) {
  return <ProgressGlyph {...props} started />;
}

/** Select a workflow glyph using Plane EE group names, sizing, and percentage conventions. */
export function StateGroupIcon({
  stateGroup,
  size = "sm",
  percentage,
  ...props
}: StateGroupIconProps) {
  const dimension = dimensions[size];
  if (stateGroup === "started" || stateGroup === "unstarted") {
    const Glyph = stateGroup === "started" ? StartedGroupIcon : UnstartedGroupIcon;
    return <Glyph width={dimension} height={dimension} percentage={percentage} {...props} />;
  }
  const Glyph = staticGroups[stateGroup] ?? UnstartedGroupIcon;
  return <Glyph width={dimension} height={dimension} {...props} />;
}
