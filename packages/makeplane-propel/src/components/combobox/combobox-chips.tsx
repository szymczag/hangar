import { Combobox as BaseCombobox } from "@base-ui/react/combobox";
import type * as React from "react";

import {
  type ComboboxChipSize,
  type ComboboxSize,
  type ComboboxVariant,
  ComboboxChipOverflow as ComboboxChipOverflowElement,
  ComboboxChips as ComboboxChipsElement,
  ComboboxInput as ComboboxInputElement,
} from "../../elements/combobox";
import { ChevronDownOutline } from "../../icons";
import { defaultComboboxOverflowLabel } from "../../internal/combobox-overflow-label";
import { Icon } from "../../internal/icon";
import { ComboboxChipSizeContext } from "./combobox-chip-size-context";

// The chip rung inside each frame rung: a 28/32/36/40px frame seats a 20/24/28/32px chip — always
// exactly one ladder rung down. The overflow "+N more" count is chip-scale text, so it takes the
// same mapped value.
const CHIP_SIZE: Record<ComboboxSize, ComboboxChipSize> = {
  md: "xs",
  lg: "sm",
  xl: "md",
  "2xl": "lg",
};

export type ComboboxChipsProps<Value = string> = {
  /**
   * Frame look. `secondary` is the bordered field surface; `ghost` is borderless.
   *
   * @default "secondary"
   */
  variant?: ComboboxVariant;
  /** Visual size of the chips frame: height, text, and glyph sizing. Required. */
  size: ComboboxSize;
  /** Input placeholder shown while typing to add another value. */
  placeholder?: string;
  /**
   * Cap on how many chips render, followed by an overflow count — set it when selections can grow
   * large. Hidden values stay selected and are managed from the popup, but Backspace and arrow keys
   * only reach rendered chips. A nonnegative integer; zero shows only the count.
   *
   * @default Infinity
   */
  maxVisible?: number;
  /**
   * Copy for the overflow count when `maxVisible` hides selected chips. Called with how many values
   * are hidden and how many chips remain visible. Override to localize.
   *
   * @default (hiddenCount, { visibleCount }) => visibleCount > 0 ? `+${hiddenCount} more` : `${hiddenCount} selected`
   */
  overflowLabel?: (hiddenCount: number, details: { visibleCount: number }) => React.ReactNode;
  /**
   * The popup-trigger control (e.g. an `IconButton`), grafted onto Base UI's `Trigger` behavior. It
   * carries its own — localizable — `aria-label`. Omit it to show a decorative chevron (the Figma
   * end node) — the input still opens the list.
   */
  trigger?: React.ReactElement;
  /**
   * Renders one selected value as a `ComboboxChip` — the `ComboboxChips` counterpart of
   * `ComboboxList`'s item template. Set your own `key`, exactly like `ComboboxList`'s function
   * child, e.g. `(value) => <ComboboxChip key={value} label={value} remove={<... />} />`.
   */
  children: (value: Value) => React.ReactNode;
};

/**
 * The ready-made multiselect input frame — it replaces `ComboboxInputGroup` in the `multiple`
 * anatomy. Grafts Base UI's `Chips` behavior onto the styled `elements/combobox` frame, owning only
 * the frame, the selected-values loop, and `maxVisible` overflow ahead of the inline input — each
 * chip's template is the consumer's `children`, mirroring `ComboboxList`. Chips wrap onto new rows
 * so the input stays usable. With `maxVisible`, the first N chips render followed by an overflow
 * count (`+N more`, or `N selected` when `maxVisible={0}`; pass `overflowLabel` to localize). Arrow
 * keys navigate rendered chips; Backspace removes the last rendered chip, or the last selected
 * value when none are rendered.
 */
export function ComboboxChips<Value = string>({
  size,
  variant,
  placeholder,
  maxVisible = Infinity,
  overflowLabel = defaultComboboxOverflowLabel,
  trigger,
  children,
}: ComboboxChipsProps<Value>) {
  return (
    // Chips are rendered by the caller's `children`, so the frame publishes the CHIP rung
    // (one ladder step below its own) through context — see `combobox-chip-size-context`.
    <ComboboxChipSizeContext.Provider value={CHIP_SIZE[size]}>
      <BaseCombobox.Chips
        render={<ComboboxChipsElement size={size} variant={variant} layout="wrap" />}
      >
        <BaseCombobox.Value>
          {(values: Value[]) => {
            const visible = values.slice(0, Math.max(0, maxVisible));
            const hiddenCount = values.length - visible.length;
            return (
              <>
                {visible.map(children)}
                {hiddenCount > 0 ? (
                  <ComboboxChipOverflowElement size={CHIP_SIZE[size]}>
                    {overflowLabel(hiddenCount, { visibleCount: visible.length })}
                  </ComboboxChipOverflowElement>
                ) : null}
                <BaseCombobox.Input render={<ComboboxInputElement />} placeholder={placeholder} />
              </>
            );
          }}
        </BaseCombobox.Value>
        {trigger != null ? (
          <BaseCombobox.Trigger render={trigger} />
        ) : (
          <Icon tint="secondary">
            <ChevronDownOutline aria-hidden />
          </Icon>
        )}
      </BaseCombobox.Chips>
    </ComboboxChipSizeContext.Provider>
  );
}
