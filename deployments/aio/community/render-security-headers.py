# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Security headers for the all-in-one image's static frontends.

The web and admin images serve their builds with nginx and send the security
headers that @plane/csp generated from each build (packages/csp/bin/
nginx-headers.mjs): the Content-Security-Policy with the build's inline-script
hashes, the Trusted Types measurement policy, X-Frame-Options and the rest. The
all-in-one image copies the same builds but serves them with Caddy, so it also
copies each image's header template and the start-up hook that gives the
template's variables their values, and this script turns them into a Caddy
snippet at start-up. The hashes therefore always come from the build being
served; nothing here repeats them.

    render-security-headers.py storage-origin
    render-security-headers.py render --template T --out SNIPPET --root DIR --pristine DIR

`storage-origin` prints the browser-facing object-storage origins, which the
policy must allow because the all-in-one image has no same-origin proxy for
uploads. `render` must run with the hook's variables exported. It refuses a
template it does not understand, a variable without a value and any value Caddy
would read as syntax or a placeholder, so a mistake stops the container instead
of serving the frontends with a weaker or broken policy.
"""

import argparse
import ipaddress
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit

# Strict-Transport-Security is not sent by the all-in-one image (see its
# README and the release notes): it is often served over plain HTTP or behind a
# proxy that terminates TLS, and the policy covers subdomains for a year.
OMITTED_HEADERS = {"strict-transport-security"}

_ADD_HEADER = re.compile(r'^add_header\s+(\S+)\s+"([^"]*)"\s+always;$')
_SUB_FILTER = re.compile(r"^sub_filter\s+'([^']*)'\s+'([^']*)';$")
_VARIABLE = re.compile(r"\$\{([A-Z0-9_]+)\}")
_HEADER_NAME = re.compile(r"^[A-Za-z0-9-]+$")
# Caddy reads quotes, backslashes and backticks as syntax and braces as
# placeholders, even inside a quoted header value.
_UNSAFE_VALUE = re.compile(r'["\\`{}\x00-\x1f\x7f]')
_DNS_LABEL_BUCKET = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")


class TemplateError(ValueError):
    pass


def substitute(text: str, env) -> str:
    """envsubst for ${NAME}, refusing a name without a value instead of leaving it."""

    def value(match):
        name = match.group(1)
        if name not in env:
            raise TemplateError(f"${{{name}}} has no value; is the start-up hook loaded?")
        return env[name]

    return _VARIABLE.sub(value, text)


def parse_template(text: str, env):
    """The headers and page rewrites an nginx security-header template asks for."""
    headers = []
    rewrites = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or line == "sub_filter_once on;":
            continue
        header = _ADD_HEADER.match(line)
        rewrite = _SUB_FILTER.match(line)
        if header:
            name = substitute(header.group(1), env)
            value = substitute(header.group(2), env).strip()
            if not _HEADER_NAME.match(name):
                raise TemplateError(f"line {number}: unusable header name {name!r}")
            if _UNSAFE_VALUE.search(value):
                raise TemplateError(f"line {number}: {name} has a character Caddy would not keep verbatim")
            # nginx sends no header for an empty value (Trusted Types off).
            if value and name.lower() not in OMITTED_HEADERS:
                headers.append((name, value))
        elif rewrite:
            rewrites.append((substitute(rewrite.group(1), env), substitute(rewrite.group(2), env)))
        else:
            raise TemplateError(f"line {number}: not understood: {line}")
    names = {name.lower() for name, _ in headers}
    for required in ("x-frame-options", "x-content-type-options", "referrer-policy"):
        if required not in names:
            raise TemplateError(f"the template sets no {required}")
    if not names & {"content-security-policy", "content-security-policy-report-only"}:
        raise TemplateError("the template sets no Content-Security-Policy")
    return headers, rewrites


def caddy_snippet(headers, source: str) -> str:
    lines = [
        f"# Rendered at start-up from {source} by render-security-headers.py. Do not edit.",
        "header {",
    ]
    # A field Caddy sets is set once, the last value winning. nginx sends a
    # repeated add_header twice (both policies report-only with
    # HANGAR_CSP_REPORT_ONLY=true), so a repeated field is added ("+") instead.
    counts = {}
    for name, _ in headers:
        counts[name.lower()] = counts.get(name.lower(), 0) + 1
    lines += [f'\t{"+" if counts[name.lower()] > 1 else ""}{name} "{value}"' for name, value in headers]
    lines.append("}")
    return "\n".join(lines) + "\n"


def apply_rewrites(root: Path, pristine: Path, rewrites) -> None:
    """nginx's sub_filter, applied once to the files instead of to each response.

    The first start keeps a copy of every page a rewrite touches outside the
    served directory, and each start rewrites from that copy, so changing the
    mode on a later start replaces the previous value rather than missing it.
    """
    if not rewrites:
        return
    for page in sorted(root.rglob("*.html")):
        relative = page.relative_to(root)
        original = pristine / relative
        if not original.exists():
            text = page.read_text(encoding="utf-8")
            if not any(search in text for search, _ in rewrites):
                continue
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(page, original)
        text = original.read_text(encoding="utf-8")
        for search, replacement in rewrites:
            # sub_filter_once on: the first occurrence only.
            text = text.replace(search, replacement, 1)
        page.write_text(text, encoding="utf-8")


def storage_origins(env) -> str:
    """The origins presigned object-storage URLs point browsers at, space separated.

    The API presigns against AWS_S3_PUBLIC_ENDPOINT_URL, else AWS_S3_ENDPOINT_URL
    (apps/api/plane/settings/storage.py), which the all-in-one image always sets.
    With an endpoint, the image's boto3 (botocore 1.34) presigns path-style
    URLs on the endpoint's origin. A DNS-compatible bucket is also allowed as a
    subdomain of it, the virtual-hosted form boto3 uses without an endpoint and
    the Helm chart's objectStoragePublicOrigin default, so a library update that
    changed the addressing does not break uploads; both name only this bucket's
    storage.
    """
    endpoint = (env.get("AWS_S3_PUBLIC_ENDPOINT_URL") or env.get("AWS_S3_ENDPOINT_URL") or "").strip()
    if not endpoint:
        return ""
    parts = urlsplit(endpoint)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise TemplateError(f"object storage endpoint {endpoint!r} is not an http(s) URL")
    host = parts.netloc.rsplit("@", 1)[-1].lower()
    origins = [f"{parts.scheme}://{host}"]
    bucket = (env.get("AWS_S3_BUCKET_NAME") or "").strip()
    if env.get("USE_MINIO") != "1" and _DNS_LABEL_BUCKET.match(bucket) and not _is_ip(parts.hostname):
        origins.append(f"{parts.scheme}://{bucket}.{host}")
    for origin in origins:
        if _UNSAFE_VALUE.search(origin) or re.search(r"[\s;,']", origin):
            raise TemplateError(f"object storage origin {origin!r} cannot be written into the policy")
    return " ".join(origins)


def _is_ip(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("storage-origin")
    render = commands.add_parser("render")
    render.add_argument("--template", required=True, type=Path)
    render.add_argument("--out", required=True, type=Path)
    render.add_argument("--root", required=True, type=Path)
    render.add_argument("--pristine", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "storage-origin":
            print(storage_origins(os.environ))
            return 0
        headers, rewrites = parse_template(args.template.read_text(encoding="utf-8"), os.environ)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(caddy_snippet(headers, str(args.template)), encoding="utf-8")
        apply_rewrites(args.root, args.pristine, rewrites)
    except (OSError, TemplateError) as error:
        print(f"render-security-headers: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
