#!/usr/bin/env bash

# Start Gamma Blast from a clean Python/Streamlit process.
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Error: $PYTHON is not installed or is not on PATH." >&2
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Creating virtual environment in $VENV_DIR..."
  "$PYTHON" -m venv "$VENV_DIR"
fi

if [[ ! -f "$VENV_DIR/.requirements-installed" || requirements.txt -nt "$VENV_DIR/.requirements-installed" ]]; then
  echo "Installing dependencies..."
  "$VENV_DIR/bin/python" -m pip install --disable-pip-version-check -r requirements.txt
  touch "$VENV_DIR/.requirements-installed"
fi

if [[ ! -f .env && -z "${FYERS_APP_ID:-}" ]]; then
  cp .env.example .env
  cat <<'EOF'
Created .env from .env.example.

Before starting Gamma Blast:
  1. Add your FYERS App ID and Secret ID to .env.
  2. Make sure the FYERS dashboard redirect URL is http://localhost:8080/
  3. Run: ./run.sh --login

Your credentials stay in the local .env file and must not be committed.
EOF
  exit 0
fi

case "${1:-}" in
  --login)
    shift
    exec "$VENV_DIR/bin/python" login_local.py "$@"
    ;;
  --preflight)
    shift
    exec "$VENV_DIR/bin/python" preflight.py "$@"
    ;;
esac

# A new process starts with empty in-memory Streamlit caches. Removing bytecode
# as well makes this a predictable fresh launch without touching trades or .env.
find . -path "./$VENV_DIR" -prune -o -type d -name __pycache__ -exec rm -rf {} +

echo "Starting Gamma Blast at http://${STREAMLIT_ADDRESS:-localhost}:${STREAMLIT_PORT:-8501}"
exec "$VENV_DIR/bin/python" -m streamlit run app.py \
  --server.address "${STREAMLIT_ADDRESS:-localhost}" \
  --server.port "${STREAMLIT_PORT:-8501}" \
  --browser.gatherUsageStats false \
  "$@"
