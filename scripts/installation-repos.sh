#!/usr/bin/env bash
# Writes the non-archived repositories the GitHub App installation token in GH_TOKEN can
# access to the file $1, one owner/name per line, and masks each name. This repository's
# Actions logs are public and some of the repositories are private. Run it directly in a
# step, never inside $(...): the mask commands must reach the runner on stdout.
set -euo pipefail

gh api --paginate /installation/repositories \
  --jq '.repositories[] | select(.archived | not) | .full_name' > "$1"
while read -r repo; do
  if [[ -n "$repo" ]]; then echo "::add-mask::$repo"; fi
done < "$1"
