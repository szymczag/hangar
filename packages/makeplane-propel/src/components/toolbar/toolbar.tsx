import { Toolbar as BaseToolbar } from "@base-ui/react/toolbar";

import {
  Toolbar as ToolbarElement,
  type ToolbarElevation,
  type ToolbarProps as ToolbarElementProps,
  type ToolbarSize,
} from "../../elements/toolbar";
import { ToolbarSizeContext } from "./toolbar-context";

export type ToolbarProps = Omit<
  BaseToolbar.Root.Props,
  // Horizontal-only chrome (row flex + vertical-rule separators). Base UI's `orientation` would
  // flip arrow-key roam without a matching layout, so it is not part of the ready-made API.
  "className" | "style" | "render" | "orientation"
> & {
  /**
   * Control hit-target scale: `sm` (24px) or `md` (28px). Orthogonal to `elevation`. Shared with
   * the controls inside via context. Figma's `density` maps here — `compact` → `sm`, `comfortable`
   * → `md` (raised floaters use `sm`).
   */
  size: ToolbarSize;
  /** Whether the toolbar draws its own surface (`raised`) or sits flush (`flat`). */
  elevation: ToolbarElevation;
  /** Custom render for the underlying styled toolbar. */
  render?: ToolbarElementProps["render"];
};

/**
 * The ready-made toolbar: grafts Base UI's `Toolbar.Root` behavior (the `toolbar` role + roving
 * focus, plus `disabled` / `loopFocus`) onto the styled horizontal `elements/toolbar` row and
 * shares its `size` with the controls inside via context (so each control packs to match).
 */
export function Toolbar({ size, elevation, render, ...props }: ToolbarProps) {
  return (
    <ToolbarSizeContext.Provider value={size}>
      <BaseToolbar.Root
        {...props}
        render={<ToolbarElement size={size} elevation={elevation} render={render} />}
      />
    </ToolbarSizeContext.Provider>
  );
}
