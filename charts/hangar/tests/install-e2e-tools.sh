#!/usr/bin/env bash

set -euo pipefail

readonly KIND_VERSION="v0.32.0"
readonly KUBECTL_VERSION="v1.35.5"
readonly KIND_SHA256_AMD64="50030de23cf40a18505f20426f6a8506bedf13c6e509244bd1fa9463721b0f54"
readonly KIND_SHA256_ARM64="b92cd615e97585de8ddade28ed5cd7feb4248d717c233eea5b03c37298900f5d"
readonly KUBECTL_SHA256_AMD64="90f75ea6ecc9ea5633262e1c0b83a40560003b30fc94a04cb099404fcef0c224"
readonly KUBECTL_SHA256_ARM64="ac69e06fd6860d69786692f5af1c3a1208ed54f8366a4d97ab15c172e99765ee"

destination="${1:-}"
if [[ -z "$destination" ]]; then
  echo "usage: $0 DESTINATION_DIRECTORY" >&2
  exit 2
fi

case "$(uname -m)" in
  x86_64)
    architecture="amd64"
    kind_sha256="$KIND_SHA256_AMD64"
    kubectl_sha256="$KUBECTL_SHA256_AMD64"
    ;;
  aarch64 | arm64)
    architecture="arm64"
    kind_sha256="$KIND_SHA256_ARM64"
    kubectl_sha256="$KUBECTL_SHA256_ARM64"
    ;;
  *)
    echo "unsupported architecture: $(uname -m)" >&2
    exit 1
    ;;
esac

mkdir -p "$destination"
destination=$(cd "$destination" && pwd)
temporary_directory=$(mktemp -d)
trap 'rm -rf "$temporary_directory"' EXIT

download_and_verify() {
  local url="$1"
  local expected_sha256="$2"
  local output="$3"

  curl --fail --silent --show-error --location "$url" --output "$temporary_directory/$output"
  printf '%s  %s\n' "$expected_sha256" "$temporary_directory/$output" | sha256sum --check --status
  install -m 0755 "$temporary_directory/$output" "$destination/$output"
}

download_and_verify \
  "https://github.com/kubernetes-sigs/kind/releases/download/${KIND_VERSION}/kind-linux-${architecture}" \
  "$kind_sha256" \
  kind
download_and_verify \
  "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${architecture}/kubectl" \
  "$kubectl_sha256" \
  kubectl

"$destination/kind" version
"$destination/kubectl" version --client
