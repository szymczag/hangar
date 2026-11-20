import { cva, cx, type VariantProps } from "class-variance-authority";

import { controlGroupClass } from "../../internal/control-group";
import { type StrictVariantProps } from "../../internal/variant-props";

const textAreaGroupDefaultVariants = { resize: "vertical" } as const;

// The bordered frame around the textarea leaf. Per the Figma "Text area" spec the border
// style/width, radius, and the focus/error border treatments are "always the same", so they are
// static chrome. Padding lives on the `TextArea` leaf (not the frame) so the native resize handle
// sits flush with the border on all sides. Composes the shared field-box chrome so the input and
// textarea frames stay in lockstep; danger isn't a prop — the surface recolors its border off the
// wrapped control's `data-invalid`.
//
// `resize` lives on the frame (not the leaf): the frame owns the border, so the native drag
// handle grows the chrome with the content. A leaf with `min-w-full` inside a flex frame cannot
// keep a horizontal resize — the browser's inline width is shrunk back to the 100% floor.
export const textAreaGroupVariants = cva(
  cx(controlGroupClass, "w-full items-stretch gap-1.5 rounded-lg"),
  {
    variants: {
      /** Controls whether the user can resize the framed textarea. */
      resize: {
        none: "resize-none",
        // CSS `resize` only applies when overflow is not `visible`. Restrict `overflow-hidden` to
        // the handle-bearing steps so a locked frame keeps default overflow; the focus ring is a
        // box-shadow on this same node and is not clipped by the element's own overflow.
        vertical: "resize-y overflow-hidden",
        both: "resize overflow-hidden",
      },
    },
    defaultVariants: textAreaGroupDefaultVariants,
  },
);

export type TextAreaGroupVariantProps = StrictVariantProps<
  typeof textAreaGroupVariants,
  keyof typeof textAreaGroupDefaultVariants
>;

type TextAreaGroupVariantConfig = VariantProps<typeof textAreaGroupVariants>;
export type TextAreaResize = NonNullable<TextAreaGroupVariantConfig["resize"]>;

const textAreaDefaultVariants = { autoResize: false } as const;

export const textAreaVariants = cva(
  cx(
    // The leaf never owns the resize handle — `TextAreaGroup` does — so it stays `resize-none`.
    "scrollbar-sm resize-none overflow-y-auto bg-transparent text-primary outline-none",
    "placeholder:text-placeholder",
    "disabled:cursor-not-allowed disabled:text-disabled",
  ),
  {
    variants: {
      size: {
        md: "text-caption-md-regular",
        lg: "text-body-xs-regular",
        xl: "text-body-sm-regular",
        "2xl": "text-body-md-regular",
      },
      surface: {
        // `field` fills the bordered `TextAreaGroup` frame (`w-full`) so growing the frame's
        // native resize handle carries the leaf with it (`h-full` is the non-autoResize compound
        // below). `embedded` owns its full-width composer chrome alone; `inline` sits beside
        // sibling controls and needs `min-w-0 flex-1` to shrink instead. Each surface owns its
        // width utilities outright.
        field: "w-full min-w-full px-3 py-2",
        // These `leading-*` deliberately override the size composite's 1.54/1.2 line-height:
        // prose in a comment box (`embedded`) and inline editing read tighter than a bordered
        // form field. The override is deterministic, not order-dependent — a `leading-*` utility
        // sets `--tw-leading`, which the composite's `line-height: var(--tw-leading, …)` reads
        // first, and Tailwind also emits `leading-*` after the `text-*` utilities.
        embedded: "w-full min-w-full p-3 leading-snug",
        inline: "min-w-0 flex-1 leading-tight",
      },
      /**
       * Visual state only — this leaf does not grow itself. Pair with the `components` `TextArea`/
       * `TextAreaField`, which syncs an explicit pixel height in JS on every input (no CSS
       * `field-sizing` path — an inline `height` always wins over it, so a CSS-only class would be
       * dead weight) and grows the control with its content above the size `min-height`.
       */
      autoResize: {
        false: "",
        true: "",
      },
    },
    // Min-heights are whole multiples of each size's own rendered line box (12px×1.2 = 14.4,
    // 13px×1.54 ≈ 20, 14px×1.54 ≈ 21.6, 16px×1.54 ≈ 24.6) — 3/3/4/3 visible lines — plus the
    // leaf's own `py-2` (16px, border-box). The old values (40/66/84/84) cut a partial line at the
    // bottom edge of every size, and lg/xl shared 84px despite different line boxes. One family's
    // floor, so the numbers live here rather than in the shared token sheet; `text-area.tsx`'s
    // `TEXT_AREA_DEFAULT_MIN_HEIGHT_REM` mirrors them for the auto-resize math.
    compoundVariants: [
      { surface: "field", size: "md", class: "min-h-[3.75rem]" }, // 60px
      { surface: "field", size: "lg", class: "min-h-[4.75rem]" }, // 76px
      { surface: "field", size: "xl", class: "min-h-[6.375rem]" }, // 102px
      { surface: "field", size: "2xl", class: "min-h-[5.625rem]" }, // 90px
      // The native resize handle on `TextAreaGroup` sets an explicit height on the frame; `h-full`
      // lets the leaf fill that. Auto-resize sizes the leaf from its content instead, so the frame
      // wraps it (`h-auto`) while the size `min-height` compounds above stay the floor.
      { surface: "field", autoResize: false, class: "h-full" },
      { surface: "field", autoResize: true, class: "h-auto" },
    ],
    defaultVariants: textAreaDefaultVariants,
  },
);

type TextAreaVariantConfig = VariantProps<typeof textAreaVariants>;

export type TextAreaSize = NonNullable<TextAreaVariantConfig["size"]>;
export type TextAreaSurface = NonNullable<TextAreaVariantConfig["surface"]>;
export type TextAreaVariantProps = StrictVariantProps<
  typeof textAreaVariants,
  keyof typeof textAreaDefaultVariants
>;
