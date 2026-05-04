#!/usr/bin/env bash
# ShortStack one-shot installer.
#
# Detects the OS, installs missing prerequisites (Docker, uv, Node 22, pnpm),
# boots the local stack, applies migrations, seeds the first niche, and runs
# the test suite. Idempotent — safe to re-run.
#
# Tested on:
#   - macOS (Apple Silicon + Intel) with Homebrew + Docker Desktop or Colima
#   - Ubuntu 22.04 / 24.04 LTS Desktop
#   - Debian 12 (bookworm)
#
# Usage:
#   bash scripts/setup.sh
#   make setup            # equivalent

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# --- helpers ---------------------------------------------------------------

info()  { printf "\033[34m[info]\033[0m  %s\n" "$*"; }
step()  { printf "\n\033[36m[step]\033[0m  %s\n" "$*"; }
warn()  { printf "\033[33m[warn]\033[0m  %s\n" "$*" >&2; }
err()   { printf "\033[31m[error]\033[0m %s\n" "$*" >&2; exit 1; }
ok()    { printf "\033[32m[ ok ]\033[0m  %s\n" "$*"; }
have_cmd() { command -v "$1" >/dev/null 2>&1; }

if [ "$(id -u)" -eq 0 ]; then
    err "do not run this script as root. it will sudo where it needs to."
fi

# --- detect OS / package manager -------------------------------------------

case "$(uname -s)" in
    Darwin)  OS=mac ;;
    Linux)   OS=linux ;;
    *)       err "unsupported OS: $(uname -s). Run on macOS or Linux." ;;
esac

if [ "$OS" = linux ]; then
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        case "${ID:-}" in
            ubuntu|debian)  PKG_MGR=apt ;;
            *)
                warn "Linux distro '${ID:-unknown}' is untested. Proceeding assuming apt-compatible."
                PKG_MGR=apt
                ;;
        esac
    else
        err "cannot detect Linux distro (no /etc/os-release)"
    fi
fi

ok "detected OS=$OS$([ "$OS" = linux ] && echo " pkg=$PKG_MGR" || true)"

# --- 1. macOS: ensure Homebrew --------------------------------------------

if [ "$OS" = mac ] && ! have_cmd brew; then
    step "installing Homebrew"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for this session (Apple Silicon defaults to /opt/homebrew).
    if [ -x /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
fi

# --- 2. Docker -------------------------------------------------------------

step "checking Docker"

if ! have_cmd docker; then
    if [ "$OS" = mac ]; then
        warn "Docker isn't installed. Pick one and re-run this script:"
        warn "  Docker Desktop (recommended): brew install --cask docker && open -a Docker"
        warn "  Colima (lighter):             brew install colima docker docker-compose && colima start"
        err "re-run scripts/setup.sh after Docker is installed and its daemon is up"
    else
        info "installing Docker via the official convenience script"
        curl -fsSL https://get.docker.com | sudo sh
        if ! id -nG "$USER" | grep -qw docker; then
            sudo usermod -aG docker "$USER"
            warn "you've been added to the 'docker' group — log out + in (or run 'newgrp docker') and re-run this script"
            exit 0
        fi
    fi
fi

if ! docker info >/dev/null 2>&1; then
    if [ "$OS" = mac ]; then
        err "Docker is installed but the daemon isn't running. Open Docker Desktop, or 'colima start', then re-run."
    else
        err "Docker daemon isn't running. Try 'sudo systemctl start docker' (or 'newgrp docker' if you just installed)."
    fi
fi

ok "docker $(docker --version | awk '{print $3}' | tr -d ',')"

# --- 3. uv (Python toolchain) ---------------------------------------------

step "checking uv"

if ! have_cmd uv; then
    info "installing uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # uv installs to ~/.local/bin (or $UV_INSTALL_DIR). Add to PATH for this session.
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! have_cmd uv; then
        err "uv installed but not on PATH. Add ~/.local/bin to your shell rc and re-run."
    fi
fi
ok "uv $(uv --version | awk '{print $2}')"

# --- 4. Node 22 LTS --------------------------------------------------------

step "checking Node 22"

node_major() {
    node --version 2>/dev/null | sed 's/^v//' | cut -d. -f1
}

NODE_OK=0
if have_cmd node && [ "$(node_major)" -ge 22 ] 2>/dev/null; then
    NODE_OK=1
fi

if [ "$NODE_OK" -eq 0 ]; then
    info "installing Node 22"
    if [ "$OS" = mac ]; then
        brew install node@22
        brew link --overwrite --force node@22 || true
    else
        curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
        sudo apt-get install -y nodejs
    fi
    if [ "$(node_major)" -lt 22 ] 2>/dev/null; then
        err "node $(node --version) is still <22; check your PATH and re-run"
    fi
fi
ok "node $(node --version)"

# --- 5. pnpm (via Corepack, bundled with Node 22) -------------------------

step "checking pnpm"

if ! have_cmd pnpm; then
    info "enabling pnpm through Corepack"
    if [ "$OS" = mac ]; then
        corepack enable
    else
        sudo corepack enable
    fi
    corepack prepare pnpm@latest --activate
fi
ok "pnpm $(pnpm --version)"

# --- 6. Project setup ------------------------------------------------------

if [ ! -f .env ]; then
    step "copying .env.example -> .env"
    cp .env.example .env
    info "edit .env to add API keys when you're ready (most stages have a no-key fallback)"
else
    info ".env already exists — leaving it as-is"
fi

step "booting docker stack (postgres + redis + minio)"
make up

info "waiting for postgres to accept connections"
for i in $(seq 1 30); do
    if docker exec shortstack-postgres-1 pg_isready -U shortstack >/dev/null 2>&1; then
        ok "postgres ready"
        break
    fi
    sleep 1
    if [ "$i" -eq 30 ]; then
        err "postgres did not become ready within 30s — check 'docker logs shortstack-postgres-1'"
    fi
done

step "installing Python + Node dependencies"
make install

step "applying alembic migrations"
make migrate

step "seeding the ai-productivity niche"
make seed

step "running the test suite (164 tests, ~3s)"
uv run pytest -q

# --- summary ---------------------------------------------------------------

cat <<'EOF'

================================================================
  ShortStack setup complete.
================================================================

You can now:

  make dev            # api :8000, dashboard :3000, render :8787
  make e2e-stub       # full pipeline once (zero-key tier — no AI calls)

In a separate terminal (optional):
  make worker         # celery worker on all 6 queues
  make beat           # celery beat (cron for daily / weekly automation)

Useful URLs (once 'make dev' is running):
  - dashboard:    http://localhost:3000
  - API docs:     http://localhost:8000/docs
  - MinIO:        http://localhost:9001  (login: shortstack / shortstack-dev-secret)

Add API keys to .env to unlock more of the pipeline:
  - ANTHROPIC_API_KEY        Haiku trend scoring + Sonnet script gen
  - ELEVENLABS_API_KEY       voiceover (also: edit niches.persona_json.voice_id)
  - PEXELS_API_KEY           per-scene stock images
  - REPLICATE_API_TOKEN      Flux schnell for hero scene + low-relevance fallback
  - YOUTUBE_OAUTH_*          publish to YouTube Shorts
  - BUFFER_ACCESS_TOKEN      fan out to IG / TikTok / X / LinkedIn

See docs/USER_GUIDE.md for the full operator guide.
EOF
