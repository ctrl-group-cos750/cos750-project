#!/usr/bin/env bash
# Applies .github/rulesets/*.json to the GitHub repo: creates each ruleset, or updates the one with
# the same name. Needs an organisation plan with rulesets for private repos (GitHub Team, free for
# student organisations through GitHub Education) and a token with repo administration.
#   scripts/apply-branch-rules.sh [owner/repo]
set -euo pipefail
cd "$(dirname "$0")/.."
repo="${1:-ctrl-group-cos750/cos750-project}"

for file in .github/rulesets/*.json; do
  name=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "$file")
  id=$(gh api "repos/$repo/rulesets" --jq ".[] | select(.name == \"$name\") | .id" || true)
  if [[ -n "$id" ]]; then
    gh api -X PUT "repos/$repo/rulesets/$id" --input "$file" --jq '"updated: " + .name'
  else
    gh api -X POST "repos/$repo/rulesets" --input "$file" --jq '"created: " + .name'
  fi
done
