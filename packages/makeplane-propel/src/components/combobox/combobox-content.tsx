import { ComboboxContentSurface, type ComboboxSurfaceProps } from "./combobox-content.shared";

export type { ComboboxContentSizing } from "./combobox-content.shared";

export type ComboboxContentProps = Omit<
  ComboboxSurfaceProps,
  "side" | "sideOffset" | "align" | "sizing"
> & {
  /** Which side of the input the list opens toward. @default "bottom" */
  side?: ComboboxSurfaceProps["side"];
  /** Distance in px between the input and the list. @default 4 */
  sideOffset?: ComboboxSurfaceProps["sideOffset"];
  /** Alignment of the list relative to the input along `side`. @default "start" */
  align?: ComboboxSurfaceProps["align"];
  /**
   * How the popup takes its width. `anchor` matches the input's width, grows only with its content
   * up to the room beside the input. `auto` is the content's width instead — never narrower than
   * 204px, never wider than 400px or the room beside the input, and held while open so a filtering
   * list does not reflow. `anchor-fixed` keeps the exact anchor width for windowed lists and caps
   * height at 288px so a mid-open available-height settle cannot shrink under the virtualizer.
   * `auto-fixed` is `auto`'s width with the same 288px cap, for a windowed list under a compact
   * trigger.
   *
   * @default "anchor"
   */
  sizing?: ComboboxSurfaceProps["sizing"];
};

/**
 * The combobox list surface: Base UI portal + positioner, with `Combobox.Popup` grafted onto the
 * same elevated `OverlayPanel` `MenuContent` uses. Search/footer therefore live _inside_ the dialog
 * (unlike Menu, where they must sit outside `role="menu"`). The inner `ComboboxPopup` is
 * padding-only; sticky chrome stays pinned outside the scroll area.
 *
 * When the input is in the panel (`ComboboxSearch` in `search`), the overlay is a dialog — name it
 * with `aria-labelledby` on the visible field label, or `aria-label`. Filter-in-field compositions
 * (`ComboboxInputGroup` / `ComboboxChips`) keep `role="presentation"` and need no dialog name.
 */
export function ComboboxContent({
  side = "bottom",
  sideOffset = 4,
  align = "start",
  sizing = "anchor",
  ...props
}: ComboboxContentProps) {
  return (
    <ComboboxContentSurface
      side={side}
      sideOffset={sideOffset}
      align={align}
      sizing={sizing}
      {...props}
    />
  );
}
