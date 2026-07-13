#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "usage: $0 CHART_DIRECTORY VERSION" >&2
    exit 64
fi

chart_dir="$1"
release_version="$2"
chart_version="${release_version#v}"

if [[ ! "$release_version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?$ ]]; then
    echo "VERSION must be a v-prefixed semantic version" >&2
    exit 64
fi

for component in web admin space live api; do
    variable_name="${component^^}_DIGEST"
    digest="${!variable_name:-}"
    if [[ ! "$digest" =~ ^sha256:[a-f0-9]{64}$ ]]; then
        echo "$variable_name must contain a sha256 image digest" >&2
        exit 64
    fi

    sed -i \
        "/repository: ghcr.io\/szymczag\/hangar-${component}$/{n;s|^    tag:.*|    tag: ${release_version}|;n;s|^    digest:.*|    digest: ${digest}|;}" \
        "$chart_dir/values.yaml"
done

sed -i "s/^version:.*/version: ${chart_version}/" "$chart_dir/Chart.yaml"
sed -i "s/^appVersion:.*/appVersion: ${release_version}/" "$chart_dir/Chart.yaml"

if grep -q 'sha256:0000000000000000000000000000000000000000000000000000000000000000' "$chart_dir/values.yaml"; then
    echo "release chart still contains placeholder image digests" >&2
    exit 1
fi

echo "Prepared Hangar chart ${chart_version} for ${release_version}"
