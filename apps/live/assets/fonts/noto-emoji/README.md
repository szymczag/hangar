# Noto Emoji (monochrome)

The PDF export draws emoji with this font (`apps/live/src/lib/pdf/emoji.tsx`).
It is read from disk; an export fetches nothing.

| Field    | Value                                                                                                    |
| -------- | -------------------------------------------------------------------------------------------------------- |
| Font     | Noto Emoji, version 3.002, variable weight axis 300–700 (react-pdf draws the default instance, 400)      |
| Designer | Google                                                                                                   |
| Licence  | SIL Open Font License 1.1, in `OFL.txt` next to this file                                                |
| Source   | `ofl/notoemoji/NotoEmoji[wght].ttf` in https://github.com/google/fonts                                   |
| Commit   | `8b0a1d0f5983c89bc2b93f1b5fb55f9e252744b5` (the font file last changed in `b979dba422e4`, 3.002 release) |
| Upstream | https://github.com/googlefonts/emoji-bw                                                                  |
| File     | `NotoEmoji-wght.ttf`, renamed only; the bytes are unchanged                                              |
| Size     | 1,982,596 bytes                                                                                          |
| SHA-256  | `de6c18832938afc99caf132b39d6a30a19bac7f2e812e28db2535b4608d27551`                                       |
| Git blob | `c2c26ab612a88a8610ff9cfbb89299bf2aea6c7a` (matches the blob in google/fonts)                            |

`OFL.txt` is `ofl/notoemoji/OFL.txt` from the same commit (SHA-256
`500bb1ccf43df7bbb522112f9133a52b16e1c35e809632f5d8609b179152de5b`).

The font is monochrome: skin tone modifiers join into the base emoji's glyph,
so `👍🏽` prints as `👍`. `apps/live/tests/lib/pdf/emoji.test.ts` checks the
SHA-256, so replacing the file means updating this table and that test.
