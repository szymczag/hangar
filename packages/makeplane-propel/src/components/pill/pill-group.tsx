import {
  PillGroup as PillGroupElement,
  type PillGroupProps as PillGroupElementProps,
} from "../../elements/pill";
import { PillGroupContext } from "./pill-group-context";

export type PillGroupProps = PillGroupElementProps;

/**
 * The ready-made connected pill group: a `group`-role frame that shares `size` with every `Pill`
 * and `IconPill` inside it via context (a segment's own `size` still wins). There is no Base UI
 * group primitive — the segments are independent Base UI `Button`s, each free to open its own
 * picker; the frame contributes only the shared chrome, the shared rung, and the role. Name the
 * group for assistive tech via `aria-label`.
 *
 * Built for a compound control whose parts read as one value — a filter condition (`Parent type ·
 * is · Task · ✕`), a property row. For several independent actions that merely share chrome, reach
 * for `ButtonGroup`.
 */
export function PillGroup({ size, ...props }: PillGroupProps) {
  return (
    <PillGroupContext.Provider value={size}>
      <PillGroupElement size={size} role="group" {...props} />
    </PillGroupContext.Provider>
  );
}
