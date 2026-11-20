import { ComboboxContentSurface, type ComboboxSurfaceProps } from "./combobox-content.shared";
import { useComboboxSubmenuContext } from "./combobox-submenu-context";

export type ComboboxSubmenuContentProps = Omit<
  ComboboxSurfaceProps,
  "side" | "sideOffset" | "align" | "sizing" | "anchor"
> & {
  /** Which side of the parent row the nested list opens toward. @default "right" */
  side?: ComboboxSurfaceProps["side"];
  /** Distance in px between the parent row and the nested list. @default 4 */
  sideOffset?: ComboboxSurfaceProps["sideOffset"];
  /** Alignment of the nested list relative to the parent row along `side`. @default "start" */
  align?: ComboboxSurfaceProps["align"];
  /**
   * How the nested popup takes its width. `auto` is the content's width — never narrower than
   * 204px, never wider than 400px or the room beside the row, and held while open so a filtering
   * list does not reflow. `anchor` matches the parent row's width instead, which is rarely what a
   * nested list wants. `anchor-fixed` and `auto-fixed` are not accepted here; they are
   * `ComboboxContent`-only.
   *
   * @default "auto"
   */
  sizing?: Exclude<ComboboxSurfaceProps["sizing"], "anchor-fixed" | "auto-fixed">;
};

/**
 * The floating surface for a nested combobox — the same elevated, scrollable panel as
 * `ComboboxContent`, but anchored beside its parent row instead of below the field. Place it inside
 * a `ComboboxSubmenu`, which supplies both the row it anchors to and the nested root it belongs
 * to.
 *
 * It has no `anchor` prop: the parent row is the anchor, and overriding it would leave the row
 * highlighted next to a panel somewhere else.
 *
 * Same naming contract as `ComboboxContent`: a nested list with its own `ComboboxSearch` is a
 * `role="dialog"` and must be named — pass `aria-label` (the parent row's label reads well) or
 * `aria-labelledby`. Name its `ComboboxList` too, since that list, not the row, is what a screen
 * reader lands in when the nested combobox opens.
 */
export function ComboboxSubmenuContent({
  side = "right",
  sideOffset = 4,
  align = "start",
  sizing = "auto",
  onPointerEnter,
  onPointerLeave,
  onKeyDown,
  ...props
}: ComboboxSubmenuContentProps) {
  const submenu = useComboboxSubmenuContext("ComboboxSubmenuContent");
  return (
    <ComboboxContentSurface
      side={side}
      sideOffset={sideOffset}
      align={align}
      sizing={sizing}
      anchor={submenu.triggerRef}
      onPointerEnter={(event) => {
        onPointerEnter?.(event);
        // The pointer made it across the gap between the row and this panel — drop the close the
        // row armed when the pointer left it.
        submenu.cancelScheduled();
      }}
      onPointerLeave={(event) => {
        onPointerLeave?.(event);
        submenu.scheduleClose();
      }}
      onKeyDown={(event) => {
        onKeyDown?.(event);
        // Both roots see this keydown: the nested popup portals to `<body>`, but it stays a
        // React-tree descendant of the parent popup, so React bubbles the event up to the parent's
        // own dismiss handler — which has no floating tree to tell it a child is handling the key
        // (Base UI ships no combobox submenu, so neither root joins one). Without this, one Escape
        // would close the whole stack; `closeParentOnEsc` is what Menu calls that choice, and it
        // defaults to stepping back out to the parent list instead. Base UI's handler on THIS
        // element still runs either way — `stopPropagation` does not cancel sibling handlers on the
        // same node — so the nested list always closes.
        if (event.key === "Escape" && !submenu.closeParentOnEsc) event.stopPropagation();
      }}
      {...props}
    />
  );
}
