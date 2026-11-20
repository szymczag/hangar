import { cva, cx, type VariantProps } from "class-variance-authority";

import { controlGroupClass, controlSize } from "../../internal/control-group";
import { controlInputClass } from "../../internal/control-input";
import { listboxEmptyClass } from "../../internal/listbox-empty";
import { type StrictVariantProps } from "../../internal/variant-props";

export const autocompleteInputGroupVariants = cva(
  cx(
    // Wraps a separate focusable input → the shared `focus: within` group chrome.
    controlGroupClass,
    "w-full items-center",
    // A trailing control (clear/trigger renders a `<button>`; the leading icon is a `<span>`) sits
    // flush inside the field, not in its own oversized button well: tighten the group's right
    // padding so the chevron/clear glyph reads as part of the input, optically balanced with the
    // text. The `:has()` selectors outweigh the per-size padding below, so they only apply when
    // present. `trigger` renders straight in (always mounted) so `has-[button]` alone covers it;
    // `clear` sits in its reserved slot (`data-slot="clear"`) with Base UI's Clear grafted
    // `keepMounted` — the button stays in the tree and only turns invisible at an empty value, so
    // the padding (and the slot's width) never shift with visibility.
    "has-[[data-slot=clear]]:pe-1 has-[button]:pe-1",
  ),
  {
    variants: {
      // Height / icon-size per step, matching the Search box spec (Figma 28/32/36/40px). No
      // explicit vertical padding: Figma's box height already assumes its own (tighter,
      // leading-less) text-layer sizing, which an HTML line-height doesn't share — adding real
      // `py-*` here stacks on top of the input's actual line-height and overshoots every height.
      // `controlSize`'s `min-h-*` + the group's own `items-center` center the content inside the
      // floor instead, which is what actually lands on the target height. `--node-size` sizes the
      // leading icon slot (and any bare node-slot child).
      // Pad, gap and radius ride the rung tokens: side padding = (h − 8) / 2, the gap follows the
      // glyph, and the corner steps 6 → 8px at the 36px rung — matching the input frames at every
      // rung (the flat `rounded-lg` this replaces used to give a 32px autocomplete a different
      // corner than the 32px input beside it).
      size: {
        md: cx(
          controlSize.md,
          "gap-(--control-gap-md) rounded-(--control-radius-md) px-(--control-padding-x-md)",
        ),
        lg: cx(
          controlSize.lg,
          "gap-(--control-gap-lg) rounded-(--control-radius-lg) px-(--control-padding-x-lg)",
        ),
        xl: cx(
          controlSize.xl,
          "gap-(--control-gap-xl) rounded-(--control-radius-xl) px-(--control-padding-x-xl)",
        ),
        "2xl": cx(
          controlSize["2xl"],
          "gap-(--control-gap-2xl) rounded-(--control-radius-2xl) px-(--control-padding-x-2xl)",
        ),
      },
    },
  },
);

type AutocompleteInputGroupVariantConfig = VariantProps<typeof autocompleteInputGroupVariants>;
export type AutocompleteSize = NonNullable<AutocompleteInputGroupVariantConfig["size"]>;
export type AutocompleteInputGroupVariantProps = StrictVariantProps<
  typeof autocompleteInputGroupVariants
>;

// Reserves the clear control's own footprint, whatever size it actually is: Base UI's `Clear` is
// grafted with `keepMounted` (never unmounted) and only turns invisible at an empty value, so this
// slot's width always tracks the real rendered child instead of a guessed size step — no fixed
// `size-*` needed, and no gutter mismatch when a consumer passes a differently-sized control.
export const autocompleteInputGroupClearVariants = cva(
  "shrink-0 [&>*:not([data-visible])]:invisible",
);
export type AutocompleteInputGroupClearVariantProps = StrictVariantProps<
  typeof autocompleteInputGroupClearVariants
>;

// No size axis: the group's `controlSize` step already sets the composite text token on the
// frame, and the browser's `font: inherit` on form controls carries it into the input — the
// per-input axis re-declared the same tokens for no effect. Mirrors `comboboxInputVariants`.
export const autocompleteInputVariants = cva(cx(controlInputClass, "flex-1"));
export const autocompleteEmptyVariants = cva(listboxEmptyClass);
