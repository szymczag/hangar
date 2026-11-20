import type * as React from "react";

/**
 * Default overflow copy shared by `ComboboxField` and `ComboboxChips`: `+N more` when some chips or
 * preview labels remain visible, otherwise `N selected` (the `maxVisible={0}` summary).
 */
export function defaultComboboxOverflowLabel(
  hiddenCount: number,
  { visibleCount }: { visibleCount: number },
): React.ReactNode {
  return visibleCount > 0 ? `+${hiddenCount} more` : `${hiddenCount} selected`;
}
