/**
 * Chrome shared verbatim by the Avatar and WorkspaceAvatar families (rule 4a). The two stay
 * discrete `components` — a person vs a workspace — and differ in shape (circle vs squared steps),
 * but the photo treatment and the centered fallback layout are one design.
 */
export const avatarImageClass = "size-full object-cover";
export const avatarFallbackClass = "flex size-full items-center justify-center leading-none";

/**
 * The shared fallback variant map — Avatar and WorkspaceAvatar carry the exact same six label hues
 * (there is no neutral "none" variant: an avatar with no initials shows its icon slot over the
 * root's `layer-1` backdrop instead).
 */
export const avatarVariantClasses = {
  orange: "bg-label-orange-bg-strong text-on-color",
  indigo: "bg-label-indigo-bg-strong text-on-color",
  emerald: "bg-label-emerald-bg-strong text-on-color",
  crimson: "bg-label-crimson-bg-strong text-on-color",
  pink: "bg-label-pink-bg-strong text-on-color",
  purple: "bg-label-purple-bg-strong text-on-color",
} as const;

/**
 * The initials text style per avatar size — one map for Avatar and WorkspaceAvatar, whose Figma
 * sets ("User avatar", "Workspace avatar") share the scale: 9, 9, 11, 12, 13, 16, 20, 24px. Both
 * size cvas build on it, so a Figma change is one line here and the two cannot drift apart.
 */
export const avatarInitialsTextClass = {
  "2xs": "text-caption-2xs-regular",
  xs: "text-caption-2xs-regular",
  sm: "text-caption-sm-regular",
  md: "text-caption-md-regular",
  lg: "text-body-xs-regular",
  xl: "text-h6-regular",
  "2xl": "text-h4-regular",
  "3xl": "text-h3-regular",
} as const;

/**
 * Two-character initials from a display name, per the Figma spec: the first letter of the first and
 * the last name token, uppercased; a single token yields one letter. Returns `undefined` when there
 * is no name to derive from, so the avatar falls through to its anonymous icon.
 *
 * Shared by Avatar and WorkspaceAvatar — the spec's Type row shows two-letter initials for both
 * ("BR" for a person, "AC" for a workspace), so they must not drift apart.
 */
const initialsSegmenter = new Intl.Segmenter(undefined, { granularity: "grapheme" });

export function getAvatarInitials(name: string | undefined): string | undefined {
  const tokens = name?.trim().split(/\s+/).filter(Boolean);
  if (!tokens?.length) return undefined;
  const firstGrapheme = (token: string) =>
    initialsSegmenter.segment(token)[Symbol.iterator]().next().value?.segment ?? "";
  const first = firstGrapheme(tokens[0]!);
  const last = tokens.length > 1 ? firstGrapheme(tokens[tokens.length - 1]!) : "";
  return Array.from(
    initialsSegmenter.segment(`${first}${last}`.toUpperCase()),
    ({ segment }) => segment,
  )
    .slice(0, 2)
    .join("");
}

/** Preserve a complete Unicode grapheme when compact avatar text is limited to one initial. */
export function getFirstAvatarInitial(text: string): string {
  return initialsSegmenter.segment(text.trim())[Symbol.iterator]().next().value?.segment ?? "";
}
