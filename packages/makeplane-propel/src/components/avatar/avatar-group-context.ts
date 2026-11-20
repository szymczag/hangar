import * as React from "react";

import type { AvatarSize } from "../../elements/avatar";

/**
 * Set by the components `AvatarGroup` so every `Avatar` inside it shares one `size` (an avatar's
 * own `size` still wins). Lives in the components tier: a context is cross-tree coordination —
 * composition — not a single-element `elements` concern.
 */
export const AvatarGroupContext = React.createContext<AvatarSize | undefined>(undefined);
