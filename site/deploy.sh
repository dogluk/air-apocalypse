#!/bin/bash
# Build and deploy site/dist/ to the Cloudflare Pages project "airhealth" (airhealth.dev).
# Needs a Cloudflare API token with Pages edit on the account that owns airhealth.dev:
# CLOUDFLARE_API_TOKEN in the environment, or a file at ~/.config/airhealth/cf-token.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
bash "$ROOT/site/build.sh"
if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
  CLOUDFLARE_API_TOKEN=$(tr -d '\n ' < "$HOME/.config/airhealth/cf-token")
fi
export CLOUDFLARE_API_TOKEN
if [ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]; then
  CLOUDFLARE_ACCOUNT_ID=$(curl -s -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
    "https://api.cloudflare.com/client/v4/zones?name=airhealth.dev" |
    python3 -c "import sys,json;print(json.load(sys.stdin)['result'][0]['account']['id'])")
fi
export CLOUDFLARE_ACCOUNT_ID
npx --yes wrangler@3 pages deploy "$ROOT/site/dist" --project-name airhealth --branch main \
  --commit-hash "$(git -C "$ROOT" rev-parse HEAD)" --commit-dirty=true
