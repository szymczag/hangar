/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { getSchema } from "@tiptap/core";
import { generateHTML, generateJSON } from "@tiptap/html";
import { describe, expect, it } from "vitest";

import { CoreEditorExtensionsWithoutProps } from "../src/extensions/core-without-props";
import { CustomLinkExtension } from "../src/extensions/custom-link";
import { ALLOWED_LINK_PROTOCOLS, isAllowedLinkHref, isNavigableHref } from "../src/extensions/custom-link/url-security";
import { isValidHttpUrl } from "../src/helpers/common";

/**
 * Link schemes are an allowlist (http, https, mailto, tel) everywhere a link
 * is made or kept: the link inputs and autolink (`isValidHttpUrl`), the link
 * mark's parseHTML and renderHTML, and the click handler. A link the editor
 * saves is one the browser would otherwise open on a middle-click, a
 * modifier-click or from a read-only view, so a scheme off the list is refused
 * rather than saved.
 */

// Schemes that execute nothing in the page but hand the URL to another
// handler: an Android intent, a blob or filesystem URL of another origin, the
// browser's source viewer, an archive, FTP, Windows protocol handlers.
const OFF_LIST_HREFS = [
  "intent://scan/#Intent;scheme=zxing;package=com.example;end",
  "x-javascript:alert(1)",
  "blob:https://example.com/9f3c1d2e",
  "filesystem:https://example.com/temporary/file.txt",
  "view-source:https://example.com",
  "jar:https://example.com/a.jar!/b.class",
  "ftp://example.com/file.txt",
  "ms-settings:display",
  "ms-word:ofe|u|https://example.com/a.docx",
  "search-ms:query=secret&crumb=location:\\\\example.com\\share",
  "file:///etc/passwd",
  "about:blank",
  "chrome://settings",
];

const ON_LIST_HREFS = [
  "https://example.com",
  "http://example.com/path?q=1#top",
  "HTTPS://EXAMPLE.COM",
  "mailto:user@example.com",
  "tel:+48123456789",
  "tel:5551234",
];

describe("ALLOWED_LINK_PROTOCOLS", () => {
  it("is exactly http, https, mailto and tel", () => {
    expect([...ALLOWED_LINK_PROTOCOLS].toSorted()).toEqual(["http:", "https:", "mailto:", "tel:"]);
  });
});

describe("isValidHttpUrl", () => {
  it.each(OFF_LIST_HREFS)("refuses %j", (href) => {
    expect(isValidHttpUrl(href)).toEqual({ isValid: false, url: href });
  });

  it.each(["javascript:alert(1)", "java\tscript:alert(1)", "\u0001javascript:alert(1)", "data:text/html,x"])(
    "still refuses the script scheme %j",
    (href) => {
      expect(isValidHttpUrl(href).isValid).toBe(false);
    }
  );

  it.each(ON_LIST_HREFS)("accepts %j as typed", (href) => {
    expect(isValidHttpUrl(href)).toEqual({ isValid: true, url: href });
  });

  it.each([
    ["example.com", "https://example.com"],
    ["www.example.com/a?b=c", "https://www.example.com/a?b=c"],
    ["localhost:3000", "https://localhost:3000"],
    ["example.com:8080/path", "https://example.com:8080/path"],
  ])("normalises scheme-less %j to %j", (input, url) => {
    expect(isValidHttpUrl(input)).toEqual({ isValid: true, url });
  });

  it("is the link mark's autolink validator", () => {
    const validate = CustomLinkExtension.options.validate!;
    for (const href of OFF_LIST_HREFS) expect(validate(href)).toBe(false);
    for (const href of ON_LIST_HREFS) expect(validate(href)).toBe(true);
  });
});

describe("isAllowedLinkHref", () => {
  it.each(OFF_LIST_HREFS)("refuses %j", (href) => {
    expect(isAllowedLinkHref(href)).toBe(false);
    expect(isNavigableHref(href)).toBe(false);
  });

  it.each(["\tintent://x", " \u0000ftp://example.com", "Intent://x", "VIEW-SOURCE:https://example.com"])(
    "refuses the obfuscated %j",
    (href) => {
      expect(isAllowedLinkHref(href)).toBe(false);
    }
  );

  it.each([...ON_LIST_HREFS, "/relative/path", "#anchor", "page?x=1", ""])("keeps %j", (href) => {
    expect(isAllowedLinkHref(href)).toBe(true);
  });
});

const docWithLink = (href: string) => ({
  type: "doc",
  content: [
    {
      type: "paragraph",
      content: [{ type: "text", text: "link", marks: [{ type: "link", attrs: { href } }] }],
    },
  ],
});

describe("the link mark", () => {
  const schema = getSchema(CoreEditorExtensionsWithoutProps);
  const linkHrefs = (html: string): string[] => {
    const doc = schema.nodeFromJSON(generateJSON(html, CoreEditorExtensionsWithoutProps));
    const hrefs: string[] = [];
    doc.descendants((node) => {
      for (const mark of node.marks) if (mark.type.name === "link") hrefs.push(String(mark.attrs.href));
    });
    return hrefs;
  };

  it.each(OFF_LIST_HREFS)("drops the mark when parsing %j and keeps the text", (href) => {
    const html = `<p><a href="${href.replaceAll("&", "&amp;").replaceAll('"', "&quot;")}">link</a></p>`;
    expect(linkHrefs(html)).toEqual([]);
    expect(JSON.stringify(generateJSON(html, CoreEditorExtensionsWithoutProps))).toContain('"text":"link"');
  });

  it.each(ON_LIST_HREFS)("keeps %j when parsing", (href) => {
    expect(linkHrefs(`<p><a href="${href}">link</a></p>`)).toEqual([href]);
  });

  it.each(OFF_LIST_HREFS)("renders a stored %j mark with a blank href", (href) => {
    const html = generateHTML(docWithLink(href), CoreEditorExtensionsWithoutProps);
    expect(html).toContain('href=""');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer nofollow"');
  });

  it.each(ON_LIST_HREFS)("renders a stored %j mark unchanged", (href) => {
    const html = generateHTML(docWithLink(href), CoreEditorExtensionsWithoutProps);
    expect(html).toContain(`href="${href}"`);
  });
});
