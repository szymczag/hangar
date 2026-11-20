import { cva, cx } from "class-variance-authority";

/**
 * The radio CIRCLE look: a 16px ring that holds the inner dot, stroked with `currentColor` so the
 * ring and the dot recolor together (`text-icon-tertiary` resting → `text-icon-accent-primary`
 * selected). Unlike the check, the ring is drawn whether or not the option is selected — an
 * unselected radio reads as an empty ring the way an unselected checkbox reads as an empty box,
 * which is what makes a set of them scannable as one group.
 *
 * Shared chrome — the `Radio` control (`elements/radio`) and the menu / context-menu radio
 * indicators (via `menuRadioItemIndicatorClass` in `internal/menu-row-parts`) all render it, so it
 * lives in `internal/` (rule 4a: no cross-component cva coupling). Reacts to the standard Base UI
 * state attributes (`data-checked` / `data-disabled`), so any host that sets them gets the look —
 * `Radio.Root` sets them on the control, and `Menu.RadioItemIndicator` sets them on the indicator
 * itself, which is why one class serves both.
 *
 * The error look isn't a prop: it rests at the neutral stroke and recolors to `danger` off
 * `data-invalid`, which Base UI's `Field.Root` propagates from field validity (same contract as
 * `internal/checkbox-box.ts`). Scoped to `not-data-checked` so only the still-unanswered options
 * read as wrong, not the one the user already picked. A menu radio row never receives
 * `data-invalid`, so the rule is simply inert there.
 */
export const radioCircleVariants = cva(
  cx(
    // Transparent border = 1px gutter around a 14px padding box, and the resting stroke is an
    // INSET shadow rather than a real border — the identical treatment `internal/checkbox-box.ts`
    // uses, and for the identical reason: a real border sits on the 16px outer edge and reads
    // optically larger than the 14px checkbox box sitting next to it in the same control column.
    // `currentColor` keeps the stroke recoloring off `text-*` exactly as `border-current` did.
    //
    // No resting FILL here, matching `checkbox-box`: a menu row's highlight is a translucent wash,
    // and an opaque disc inside the ring blocks it while the checkbox box beside it lets it
    // through, so the two markers behaved differently under the pointer. The standalone `Radio`
    // adds its own `bg-layer-1` in `elements/radio`, where it sits on a form surface and wants one.
    "flex size-4 shrink-0 items-center justify-center rounded-full border-sm border-transparent bg-clip-padding",
    "shadow-[inset_0_0_0_1px_currentColor]",
    // `duration-100`, matching Checkbox/Switch: one snappy fill speed across every small toggle
    // control.
    "text-icon-tertiary transition-[color,background-color,box-shadow] duration-100 outline-none",
    "data-checked:text-icon-accent-primary",
    "data-invalid:not-data-checked:text-icon-danger-primary",
    "focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:ring-offset-2",
    "data-disabled:cursor-not-allowed data-disabled:text-icon-disabled data-disabled:opacity-60",
    // Same-property tie against `data-checked:text-icon-accent-primary` above: without this
    // compound selector, which color wins a checked+disabled ring depends on Tailwind's internal
    // variant-emission order rather than source order (Checkbox hardens the identical collision
    // in `internal/checkbox-box.ts` the same way).
    "data-disabled:data-checked:text-icon-disabled",
  ),
);

/**
 * The inner dot that fills the circle: 8px, painted with the ring's `currentColor` so the two never
 * drift apart. `Radio` mounts it only while checked (Base UI mounts `Radio.Indicator` on demand); a
 * menu radio row keeps it mounted and hides it off `data-unchecked`, so the ring holds its size.
 */
export const radioDotClass = "size-2 rounded-full bg-current";
