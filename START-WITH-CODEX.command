#!/bin/sh
set -eu
ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT_DIR"
if ! command -v codex >/dev/null 2>&1; then
  printf '%s\n' 'Codex was not found. Install or open Codex, then open this folder and say: Set this up and run the included demo.'
  printf '%s' 'Press Return to close.'
  read -r _answer
  exit 1
fi
exec codex

