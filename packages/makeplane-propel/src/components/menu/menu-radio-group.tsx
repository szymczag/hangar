import { Menu as BaseMenu } from "@base-ui/react/menu";

import { MenuRadioMarkerContext, type MenuRadioMarker } from "../../internal/menu-radio-marker";

export type MenuRadioGroupProps = Omit<BaseMenu.RadioGroup.Props, "className" | "style"> & {
  /**
   * How the group marks its current row. Defaults to `check` — the trailing tick every other
   * single-select row uses. Pass `radio` only when this group shares a popup with a multi-select
   * (checkbox) group and the two need telling apart.
   *
   * @default "check"
   */
  marker?: MenuRadioMarker;
};

/** Wraps `MenuRadioItem`s sharing one `value` — Base UI's radio-group state, no element chrome. */
export function MenuRadioGroup({ marker = "check", ...props }: MenuRadioGroupProps) {
  return (
    <MenuRadioMarkerContext.Provider value={marker}>
      <BaseMenu.RadioGroup {...props} />
    </MenuRadioMarkerContext.Provider>
  );
}
