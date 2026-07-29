#!/usr/bin/env bash
# Prepares .env for a dev container. In a Codespace the browser reaches the
# services on forwarded HTTPS hostnames rather than on localhost, so the API
# base URL and the CORS allow-list have to be derived from the codespace name.
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -f .env ]; then
  echo "→ .env already exists; keeping your values."
else
  cp .env.example .env
  echo "→ Created .env from .env.example"
  # Never leave the placeholder signing key in a running app.
  if command -v openssl >/dev/null 2>&1; then
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|" .env
    echo "→ Generated a SECRET_KEY"
  fi
fi

# The browser only ever talks to the web app, which forwards /api itself, so
# the single forwarded port is all that has to be allowed. The hostname changes
# with every codespace, so it is rewritten on each run even when .env was kept.
if [ -n "${CODESPACE_NAME:-}" ]; then
  domain="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
  web="https://${CODESPACE_NAME}-3000.${domain}"

  sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=${web}|" .env
  echo "→ Codespace detected; the app will be at ${web}"

  # An earlier version of this script pointed the browser straight at the
  # forwarded API port. That address survives in .env across a git pull, and
  # docker compose bakes it into the frontend image as a build argument, so the
  # web app would go cross-origin again and be blocked by CORS. Clear it.
  if grep -q "^NEXT_PUBLIC_API_URL=https\?://.*\.${domain}" .env; then
    sed -i "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=|" .env
    echo "→ Removed a stale forwarded API URL from .env; rebuild with:"
    echo "     docker compose up --build -d"
  fi
fi

cat <<'EOF'

────────────────────────────────────────────────────────────
Next:
  1. Open .env and fill in ANTHROPIC_API_KEY and TAVILY_API_KEY
  2. docker compose up --build -d
  3. Open the forwarded port 3000 from the Ports tab

Without provider keys the stack still runs, but every analysis
reports insufficient evidence instead of inventing numbers.
────────────────────────────────────────────────────────────
EOF
