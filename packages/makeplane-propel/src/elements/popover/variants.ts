import { cva, cx, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

// Popover is a trigger-anchored content panel (a modal-like surface that sits next to a point,
// not a menu). The popup owns the full chrome — fill, border, shadow, radius, padding — rather
// than sitting inside the shared menu `OverlayPanel`, because the design binds a distinct raised
// card (`layer-2` / `border-subtle-1` / `shadow-overlay-200`) that preview-card and tooltip already
// use standalone. Title keeps its own recipe instead of the shared `internal/overlay-title` "md"
// step (`semibold`): the text panel binds `body-sm-medium`. Description is the shared
// `internal/overlay-description` at `md` (grafted in `components`).

const popoverPopupDefaultVariants = { variant: "rich" } as const;

export const popoverPopupVariants = cva(
  cx(
    // Height cap only — do not scroll on this node. Overflow here clips the field-control
    // focus ring (`focus-within:ring-2`). Tall content goes in `PopoverBody`.
    "flex max-h-(--available-height) flex-col border-sm border-subtle-1 bg-layer-2 shadow-overlay-200 outline-none",
    "origin-(--transform-origin) transition-[opacity,transform] duration-150 motion-reduce:transition-none",
    "data-starting-style:scale-95 data-starting-style:opacity-0",
    "data-ending-style:scale-95 data-ending-style:opacity-0",
  ),
  {
    variants: {
      variant: {
        // Padded content panel for forms and arbitrary children. Floor 320px so `w-full`
        // controls (InputGroup) resolve; `w-max` still grows for wider content.
        rich: "w-max max-w-[calc(100vw-2rem)] min-w-80 gap-2 rounded-xl p-4",
        // Compact 296px title + description card.
        text: "w-74 gap-1 rounded-lg px-3 py-2 break-words",
      },
    },
    defaultVariants: popoverPopupDefaultVariants,
  },
);

type PopoverPopupVariantConfig = VariantProps<typeof popoverPopupVariants>;
export type PopoverPopupVariant = NonNullable<PopoverPopupVariantConfig["variant"]>;
export type PopoverPopupVariantProps = StrictVariantProps<
  typeof popoverPopupVariants,
  keyof typeof popoverPopupDefaultVariants
>;

// Scrollable slot inside the height-capped popup (DialogBody pattern). `min-h-0` lets it shrink
// when the popup hits `--available-height`. `overflow-x-clip` keeps overflow-x from computing to
// `auto`; the inner `ScrollportXClip` keeps focus from growing scrollWidth. `p-0.5 -m-0.5` keeps
// field `ring-2` focus chrome inside the scrollport (same bleed as DialogBody). Overflow stays
// here so the popup chrome does not clip those rings either.
export const popoverBodyVariants = cva(
  "-m-0.5 min-h-0 min-w-0 flex-1 overflow-x-clip overflow-y-auto overscroll-contain p-0.5",
);

// Compact panel heading. Wraps with word-break (the text card is 296px and copy can overflow);
// diverges from `internal/overlay-title` "md" (`semibold`) — this family binds `medium`.
export const popoverTitleVariants = cva("w-full text-body-sm-medium break-words text-primary");
