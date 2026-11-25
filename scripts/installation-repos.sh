#!/usr/bin/env bash
# Prints the non-archived repositories the GitHub App installation token in GH_TOKEN can
# access, one owner/name per line. Each name is masked first: this repository's Actions
# logs are public and some of the repositories are private.
set -euo pipefail

repos="$(gh api --paginate /installation/repositories \
  --jq '.repositories[] | select(.archived | not) | .full_name')"
while read -r repo; do
  if [[ -n "$repo" ]]; then echo "::add-mask::$repo"; fi
done <<< "$repos"
printf '%s\n' "$repos"
