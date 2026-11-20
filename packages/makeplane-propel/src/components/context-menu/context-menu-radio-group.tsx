import { ContextMenu as BaseContextMenu } from "@base-ui/react/context-menu";

import { MenuRadioMarkerContext, type MenuRadioMarker } from "../../internal/menu-radio-marker";

export type ContextMenuRadioGroupProps = Omit<
  BaseContextMenu.RadioGroup.Props,
  "className" | "style"
> & {
  /**
   * How the group marks its current row. Defaults to `check` — the trailing tick every other
   * single-select row uses. Pass `radio` only when this group shares a popup with a multi-select
   * (checkbox) group and the two need telling apart.
   *
   * @default "check"
   */
  marker?: MenuRadioMarker;
};

/** Wraps `ContextMenuRadioItem`s sharing one `value` — Base UI's radio-group state, no chrome. */
export function ContextMenuRadioGroup({ marker = "check", ...props }: ContextMenuRadioGroupProps) {
  return (
    <MenuRadioMarkerContext.Provider value={marker}>
      <BaseContextMenu.RadioGroup {...props} />
    </MenuRadioMarkerContext.Provider>
  );
}
