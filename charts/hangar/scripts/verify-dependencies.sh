#!/usr/bin/env bash

set -euo pipefail

chart_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

expected_archive_count=3
archive_count="$(find "$chart_dir/charts" -maxdepth 1 -type f -name '*.tgz' | wc -l | tr -d ' ')"
if [[ "$archive_count" -ne "$expected_archive_count" ]]; then
    echo "expected $expected_archive_count vendored dependency archives, found $archive_count" >&2
    exit 1
fi

(
    cd "$chart_dir"
    sha256sum --check <<'CHECKSUMS'
0403591e1768cffa4d01500bf029cddc0cda6cb944ff1f241981c1670a97e60b  charts/postgres-1.6.4.tgz
46a7b77988e265d1f62b235d975fdb11a976f89760e57d1c694b72ac142da575  charts/rabbitmq-2.3.2.tgz
e768851e8437db0372ce46aaa63e3244373c06d987a67b690915e6b78f360c20  charts/valkey-2.3.1.tgz
CHECKSUMS
)

dependency_list="$(helm dependency list "$chart_dir")"
if awk 'NR > 1 && NF > 0 && $NF != "ok" { exit 1 }' <<<"$dependency_list"; then
    printf '%s\n' "$dependency_list"
else
    printf '%s\n' "$dependency_list" >&2
    echo "Chart.lock and vendored dependencies are inconsistent" >&2
    exit 1
fi

echo "dependency verification passed"
