#!/usr/bin/env bash
set -euo pipefail
workflow=$1
export GITHUB_OUTPUT
GITHUB_OUTPUT=$(mktemp)
trap 'rm -f "$GITHUB_OUTPUT"' EXIT

step() {
  awk -v title="$1" '
    index($0, "- name: " title) { found = 1 }
    found && /^        run: \|/ { body = 1; next }
    body && /^          / { print substr($0, 11); next }
    body && /^$/ { print; next }
    body { exit }
  ' "$workflow"
}

tag_check=$(step 'Require a release tag')
AUTH_ONLY=false REF_TYPE=tag TAG_NAME=v1.2.3 bash -eu -o pipefail -c "$tag_check"
AUTH_ONLY=true REF_TYPE=branch TAG_NAME=main bash -eu -o pipefail -c "$tag_check"
if AUTH_ONLY=false REF_TYPE=branch TAG_NAME=main bash -eu -o pipefail -c "$tag_check"; then exit 1; fi
if AUTH_ONLY=false REF_TYPE=tag TAG_NAME=v1.2 bash -eu -o pipefail -c "$tag_check"; then exit 1; fi

cargo() {
  printf '%s\n' '{"packages":[{"name":"example","version":"1.2.3","manifest_path":"/work/Cargo.toml"}]}'
}
export -f cargo
version_check=$(step 'Verify package version')
GITHUB_WORKSPACE=/work TAG_NAME=v1.2.3 bash -eu -o pipefail -c "$version_check"
if GITHUB_WORKSPACE=/work TAG_NAME=v1.2.4 bash -eu -o pipefail -c "$version_check"; then exit 1; fi

curl() { printf '%s' "$HTTP_STATUS"; return "${CURL_EXIT:-0}"; }
export -f curl
registry_check=$(step 'Check whether the version is already published')
export PACKAGE_NAME=example PACKAGE_VERSION=1.2.3
HTTP_STATUS=200 bash -eu -o pipefail -c "$registry_check"
grep -qx 'published=true' "$GITHUB_OUTPUT"
HTTP_STATUS=404 bash -eu -o pipefail -c "$registry_check"
grep -qx 'published=false' "$GITHUB_OUTPUT"
if HTTP_STATUS=500 bash -eu -o pipefail -c "$registry_check"; then exit 1; fi
if HTTP_STATUS=000 CURL_EXIT=6 bash -eu -o pipefail -c "$registry_check"; then exit 1; fi
echo 'Publish guard checks passed.'
