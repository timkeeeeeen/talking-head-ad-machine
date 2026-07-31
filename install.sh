#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLAN_ONLY=0
SKIP_DEMO=0

for argument in "$@"; do
  case "$argument" in
    --plan) PLAN_ONLY=1 ;;
    --skip-demo) SKIP_DEMO=1 ;;
    *) printf '%s\n' "Unknown option: $argument" >&2; exit 2 ;;
  esac
done

SYSTEM=$(uname -s)
MACHINE=$(uname -m)
if [ "$SYSTEM" != "Darwin" ]; then
  printf '%s\n' 'This installer supports macOS only. On Windows, run install.ps1.' >&2
  exit 1
fi
case "$MACHINE" in
  arm64|x86_64) ;;
  *) printf '%s\n' "Unsupported Mac architecture: $MACHINE" >&2; exit 1 ;;
esac

printf '%s\n' 'Talking-Head Ad Machine installation plan:'
printf '%s\n' '  1. Install Homebrew if it is missing.'
printf '%s\n' '  2. Install FFmpeg, Node 22, whisper.cpp, and uv.'
printf '%s\n' '  3. Create an isolated Python environment in this folder.'
printf '%s\n' '  4. Install pinned Kinocut, MCP, HyperFrames, and its browser.'
printf '%s\n' '  5. Run doctor and render the included demo.'
if [ "$PLAN_ONLY" -eq 1 ]; then
  exit 0
fi

find_brew() {
  if command -v brew >/dev/null 2>&1; then
    command -v brew
  elif [ -x /opt/homebrew/bin/brew ]; then
    printf '%s\n' /opt/homebrew/bin/brew
  elif [ -x /usr/local/bin/brew ]; then
    printf '%s\n' /usr/local/bin/brew
  fi
}

BREW_BIN=$(find_brew || true)
if [ -z "$BREW_BIN" ]; then
  INSTALLER=$(mktemp -t talking-head-homebrew.XXXXXX)
  trap 'rm -f "$INSTALLER"' EXIT HUP INT TERM
  curl --fail --silent --show-error --location \
    https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh \
    --output "$INSTALLER"
  /bin/bash "$INSTALLER"
  rm -f "$INSTALLER"
  trap - EXIT HUP INT TERM
  BREW_BIN=$(find_brew || true)
fi
if [ -z "$BREW_BIN" ]; then
  printf '%s\n' 'Homebrew installation finished but brew could not be located.' >&2
  exit 1
fi

eval "$($BREW_BIN shellenv)"
HOMEBREW_NO_AUTO_UPDATE=1
HOMEBREW_NO_INSTALL_CLEANUP=1
export HOMEBREW_NO_AUTO_UPDATE HOMEBREW_NO_INSTALL_CLEANUP
"$BREW_BIN" install ffmpeg node@22 whisper-cpp uv
NODE_PREFIX=$($BREW_BIN --prefix node@22)
PATH="$NODE_PREFIX/bin:$PATH"
export PATH

if [ -x "$ROOT_DIR/.venv/bin/python" ] && ! "$ROOT_DIR/.venv/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)'; then
  uv venv --clear --python 3.12 "$ROOT_DIR/.venv"
else
  uv venv --allow-existing --python 3.12 "$ROOT_DIR/.venv"
fi
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH
"$PYTHON_BIN" -m ad_machine.cli setup --apply --json
"$PYTHON_BIN" -m ad_machine.cli doctor --json
if [ "$SKIP_DEMO" -eq 0 ]; then
  "$PYTHON_BIN" -m ad_machine.cli demo --json
fi

printf '%s\n' 'Talking-Head Ad Machine installation completed successfully.'
