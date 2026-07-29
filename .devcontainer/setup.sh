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

# The forwarded hostnames change with every codespace, so these are rewritten
# on each run even when .env was kept.
if [ -n "${CODESPACE_NAME:-}" ]; then
  domain="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
  web="https://${CODESPACE_NAME}-3000.${domain}"
  api="https://${CODESPACE_NAME}-8000.${domain}"

  sed -i "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=${api}|" .env
  sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=${web}|" .env
  echo "→ Codespace URLs written to .env"
  echo "     web  ${web}"
  echo "     api  ${api}"

  # The web app calls the API from the browser, so that port must be reachable
  # without the codespace's own auth cookie.
  if command -v gh >/dev/null 2>&1; then
    if gh codespace ports visibility 8000:public -c "$CODESPACE_NAME" >/dev/null 2>&1; then
      echo "→ Port 8000 set to public"
    else
      echo "→ Could not set port 8000 public automatically."
      echo "  Do it in the Ports tab: right-click port 8000 → Port Visibility → Public."
    fi
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
