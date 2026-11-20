import { Switch as BaseSwitch } from "@base-ui/react/switch";

import {
  Switch as SwitchElement,
  type SwitchProps as SwitchElementProps,
  type SwitchSize,
  SwitchThumb,
} from "../../elements/switch";

export type { SwitchSize } from "../../elements/switch";

export type SwitchProps = Omit<BaseSwitch.Root.Props, "className" | "style"> & {
  /** The switch size axis. */
  size: SwitchSize;
};

/**
 * The ready-made switch: grafts Base UI's `Switch` behavior onto the styled `Switch` track and
 * `SwitchThumb` knob. The track owns the required `size`; the thumb sizes itself from it. Base UI
 * supplies `role="switch"` and full keyboard/form support. Maps to Figma's "Toggle" component.
 *
 * On/off, `disabled`, and `readOnly` are control state from the primitive, not variants — pass them
 * as props (`checked`/`defaultChecked`, `disabled`, `readOnly`). Only the size axis (`size`) is a
 * visual variant.
 *
 * When `nativeButton` is set, pass a host element via `render` (typically `<button type="button"
 * />`) — `size` still lives on this component and is applied to the styled track that wraps the
 * host, so callers do not re-specify size on `SwitchTrack`.
 */
export function Switch({ size, render, ...props }: SwitchProps) {
  return (
    // Consumer `render` is threaded into the styled track (behavior outer, styled part as the
    // render target, rule 1a) rather than replacing it — that would drop the size axis. The cast
    // bridges Base UI's stateful render-fn type and the element track's host-only render prop.
    <BaseSwitch.Root
      render={<SwitchElement size={size} render={render as SwitchElementProps["render"]} />}
      {...props}
    >
      <BaseSwitch.Thumb render={<SwitchThumb />} />
    </BaseSwitch.Root>
  );
}
