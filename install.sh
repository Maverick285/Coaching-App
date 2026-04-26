#!/usr/bin/env bash
# Buddy — one-shot installer for a fresh Hetzner / DigitalOcean / any
# Ubuntu 24.04 VPS.
#
# Usage on a fresh VPS as root:
#
#   curl -fsSL https://raw.githubusercontent.com/Maverick285/Coaching-App/claude/initial-setup-18KJY/install.sh -o install.sh
#   bash install.sh
#
# The script will prompt for your Anthropic key. Everything else has a
# sensible default. End result: a public HTTPS URL + bearer token you
# paste into the Android app's Settings, and Buddy is live.
#
# Re-running this script is safe; it won't overwrite an existing .env
# (it'll back it up to .env.bak first) and Docker pulls will dedupe.

set -euo pipefail

# --- pretty output --------------------------------------------------------

BOLD=$'\033[1m'
DIM=$'\033[2m'
RED=$'\033[31m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
CYAN=$'\033[36m'
RESET=$'\033[0m'

step() { printf "\n${BOLD}${CYAN}==> %s${RESET}\n" "$1"; }
ok()   { printf "  ${GREEN}✓${RESET} %s\n" "$1"; }
warn() { printf "  ${YELLOW}!${RESET} %s\n" "$1"; }
err()  { printf "  ${RED}✗${RESET} %s\n" "$1" >&2; }
die()  { err "$1"; exit 1; }

trap 'err "installer failed at line $LINENO"' ERR

# --- pre-flight -----------------------------------------------------------

step "Pre-flight checks"

if [[ $EUID -ne 0 ]]; then
  die "This script wants to be run as root on a fresh VPS. Try: sudo bash install.sh"
fi

if ! grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
  warn "This script is tested on Ubuntu 24.04. Other distros may need tweaks."
fi

if ! command -v curl >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq curl
fi
ok "running as root, curl available"

# --- gather inputs --------------------------------------------------------

step "Configuration"

# Anthropic key — required. Read from env if set, else prompt (silent).
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  printf "  ${BOLD}Anthropic API key${RESET} (sk-ant-…, input hidden): "
  read -rs ANTHROPIC_API_KEY
  printf "\n"
fi
[[ -n "$ANTHROPIC_API_KEY" ]] || die "Anthropic key is required."
[[ "$ANTHROPIC_API_KEY" == sk-ant-* ]] || warn "Key doesn't start with 'sk-ant-' — continuing anyway."
ok "Anthropic key captured (${#ANTHROPIC_API_KEY} chars)"

# OpenAI key — optional (used only for embeddings; BM25 falls back if absent).
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  printf "  ${BOLD}OpenAI API key${RESET} (optional, press Enter to skip): "
  read -rs OPENAI_API_KEY
  printf "\n"
fi
if [[ -n "$OPENAI_API_KEY" ]]; then
  ok "OpenAI key captured (vector search will be enabled)"
else
  ok "no OpenAI key — vector search disabled, BM25 still works"
fi

# Names — defaults that the in-app intake will refine.
USER_NAME="${BUDDY_USER_NAME:-Maverick}"
PERSONA_NAME="${BUDDY_PERSONA_NAME:-Coach}"
TIMEZONE="${BUDDY_TIMEZONE:-America/Chicago}"

# Branch to clone.
BUDDY_BRANCH="${BUDDY_BRANCH:-claude/initial-setup-18KJY}"
BUDDY_REPO="${BUDDY_REPO:-https://github.com/Maverick285/Coaching-App.git}"

# Public hostname. If unset, we derive a free nip.io hostname from the
# server's public IPv4. nip.io resolves *.nip.io subdomains to the
# IP encoded in the name, so Let's Encrypt can issue a cert for it
# without you owning a domain.
if [[ -z "${BUDDY_PUBLIC_HOST:-}" ]]; then
  PUBLIC_IP="$(curl -fsSL --max-time 5 https://api.ipify.org || true)"
  if [[ -z "$PUBLIC_IP" ]]; then
    die "Could not detect public IP. Set BUDDY_PUBLIC_HOST manually and re-run."
  fi
  DASHED_IP="${PUBLIC_IP//./-}"
  BUDDY_PUBLIC_HOST="${DASHED_IP}.nip.io"
  ok "auto-detected public hostname: ${BOLD}${BUDDY_PUBLIC_HOST}${RESET} (resolves to ${PUBLIC_IP})"
else
  ok "using configured hostname: ${BUDDY_PUBLIC_HOST}"
fi

# Bearer token — if a previous install left one, re-use it.
BUDDY_AUTH_TOKEN=""
if [[ -f /opt/buddy/Coaching-App/.env ]]; then
  BUDDY_AUTH_TOKEN="$(grep -E '^BUDDY_AUTH_TOKEN=' /opt/buddy/Coaching-App/.env | head -1 | cut -d= -f2- || true)"
fi
if [[ -z "$BUDDY_AUTH_TOKEN" ]]; then
  BUDDY_AUTH_TOKEN="$(head -c 48 /dev/urandom | base64 | tr -d '+/=' | head -c 48)"
  ok "generated fresh bearer token"
else
  ok "re-using existing bearer token from previous install"
fi

# --- install Docker -------------------------------------------------------

step "Installing Docker (idempotent)"

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sh /tmp/get-docker.sh >/dev/null
  rm -f /tmp/get-docker.sh
  systemctl enable --now docker
  ok "Docker installed"
else
  ok "Docker already present ($(docker --version))"
fi

if ! docker compose version >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq docker-compose-plugin
fi
ok "docker compose available"

# --- install git + clone repo --------------------------------------------

step "Fetching the Buddy repo"

if ! command -v git >/dev/null 2>&1; then
  apt-get install -y -qq git
fi

mkdir -p /opt/buddy
cd /opt/buddy
if [[ -d Coaching-App/.git ]]; then
  ok "repo already cloned, pulling latest from ${BUDDY_BRANCH}"
  cd Coaching-App
  git fetch --quiet origin "$BUDDY_BRANCH"
  git checkout --quiet "$BUDDY_BRANCH"
  git pull --quiet --ff-only origin "$BUDDY_BRANCH"
else
  git clone --quiet --branch "$BUDDY_BRANCH" "$BUDDY_REPO" Coaching-App
  cd Coaching-App
  ok "cloned"
fi

# --- write .env ----------------------------------------------------------

step "Writing .env"

if [[ -f .env ]]; then
  cp .env .env.bak.$(date +%s)
  ok "backed up existing .env"
fi

cat > .env <<EOF
# Generated by install.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
# Edit by hand any time; restart with: docker compose restart backend
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
OPENAI_API_KEY=${OPENAI_API_KEY:-}
BUDDY_AUTH_TOKEN=${BUDDY_AUTH_TOKEN}
BUDDY_DB_PATH=/data/buddy.db
BUDDY_MEMORY_PATH=/data/memory
BUDDY_USER_NAME=${USER_NAME}
BUDDY_PERSONA_NAME=${PERSONA_NAME}
BUDDY_LOG_LEVEL=INFO
BUDDY_TIMEZONE=${TIMEZONE}
BUDDY_CONSOLIDATION_HOUR=3
BUDDY_MORNING_HOUR=7
BUDDY_MORNING_MINUTE=0
BUDDY_EOD_HOUR=21
BUDDY_EOD_MINUTE=0
BUDDY_BUDGET_SOFT_USD=50
BUDDY_BUDGET_HARD_USD=100
BUDDY_GIT_REMOTE=
BUDDY_DREAMS_NOTIFICATION_EMAIL=
EOF
chmod 600 .env
ok ".env written (chmod 600)"

# --- write Caddyfile pointed at the public hostname ----------------------

step "Configuring Caddy (auto-HTTPS via Let's Encrypt)"

cat > Caddyfile <<EOF
${BUDDY_PUBLIC_HOST} {
  encode gzip
  reverse_proxy backend:8000
}
EOF
ok "Caddyfile points at ${BUDDY_PUBLIC_HOST}"

# --- firewall ------------------------------------------------------------

step "Opening firewall ports 80 + 443 (UFW, idempotent)"

if command -v ufw >/dev/null 2>&1; then
  ufw allow 22/tcp   >/dev/null 2>&1 || true
  ufw allow 80/tcp   >/dev/null 2>&1 || true
  ufw allow 443/tcp  >/dev/null 2>&1 || true
  if ! ufw status | grep -q "Status: active"; then
    yes | ufw enable >/dev/null 2>&1 || true
  fi
  ok "UFW open: 22, 80, 443"
else
  warn "ufw not installed — skipping firewall config (your VPS may have its own)"
fi

# --- bring it up ---------------------------------------------------------

step "Building + starting containers (this takes a few minutes the first time)"

docker compose pull --quiet 2>/dev/null || true
docker compose up -d --build 2>&1 | grep -Ei 'error|warn|started|created' | head -20 || true
ok "containers up"

# --- wait for the backend to become healthy ------------------------------

step "Waiting for backend to come up + Caddy to fetch a TLS cert"

ATTEMPTS=0
MAX_ATTEMPTS=60   # 60 * 2s = 2 minutes
HEALTH_URL="https://${BUDDY_PUBLIC_HOST}/health"
while (( ATTEMPTS < MAX_ATTEMPTS )); do
  if curl -fsSL --max-time 4 "$HEALTH_URL" >/dev/null 2>&1; then
    break
  fi
  ATTEMPTS=$((ATTEMPTS + 1))
  sleep 2
done

if (( ATTEMPTS >= MAX_ATTEMPTS )); then
  warn "Backend didn't respond on HTTPS within 2 min."
  warn "Common causes:"
  warn "  - DNS for ${BUDDY_PUBLIC_HOST} hasn't propagated yet (try 'dig ${BUDDY_PUBLIC_HOST}')"
  warn "  - Let's Encrypt rate-limited (check 'docker compose logs caddy')"
  warn "  - Your VPS firewall blocks 80/443 (Hetzner Cloud has a separate firewall in the web console)"
  warn "Run 'docker compose logs -f' to investigate. Backend may still be reachable on http://${BUDDY_PUBLIC_HOST}/health"
else
  ok "/health returned 200 — Buddy is live"
fi

# --- final summary -------------------------------------------------------

cat <<EOF

${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}
${BOLD}${GREEN}  Buddy is installed.${RESET}
${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}

In the Android app, open Settings and paste:

  ${BOLD}Backend URL:${RESET}  https://${BUDDY_PUBLIC_HOST}
  ${BOLD}Auth token:${RESET}   ${BUDDY_AUTH_TOKEN}

Tap ${BOLD}Test connection${RESET}; expect a green confirmation with the model
names. Then go through the in-app onboarding (it'll run automatically
on first launch).

${BOLD}Useful from this server:${RESET}
  cd /opt/buddy/Coaching-App
  docker compose logs -f                # live backend logs
  docker compose restart backend        # restart after editing .env
  docker compose down                   # stop everything
  docker compose up -d                  # start again
  nano .env                             # edit settings
  cd /opt/buddy/Coaching-App && git pull && docker compose up -d --build
                                        # update to a new release

${DIM}Your data lives in /data inside the buddy_data Docker volume.
The Anthropic key + bearer token are in /opt/buddy/Coaching-App/.env
(chmod 600). Back that file up if you care about not regenerating
the bearer token after a server rebuild.${RESET}

EOF
