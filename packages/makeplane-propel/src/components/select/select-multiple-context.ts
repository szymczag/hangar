import * as React from "react";

/**
 * Set by the components `Select` from its `multiple` prop so each `SelectItem` can draw the right
 * selection marker — a leading checkbox box for a multi-select, the trailing check otherwise.
 *
 * Base UI keeps `multiple` in its private root context, and items are consumer-rendered (often from
 * an `items` map), so the root cannot hand it down as a prop. Context is a composition concern, so
 * it lives here rather than in `elements` (rule 7).
 */
export const SelectMultipleContext = React.createContext(false);
