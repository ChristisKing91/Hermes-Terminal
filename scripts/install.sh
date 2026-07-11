#!/usr/bin/env bash
set -euo pipefail

if ! grep -qi microsoft /proc/version 2>/dev/null; then
  echo "Note: Hermes Terminal is intended to be installed from WSL2 Ubuntu." >&2
fi

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON:-python3}"
venv_dir="${HERMES_VENV_DIR:-$HOME/.local/share/hermes-terminal/venv}"

command -v "$python_bin" >/dev/null 2>&1 || {
  echo "python3 is required. Install it with: sudo apt install python3 python3-venv" >&2
  exit 1
}

"$python_bin" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' || {
  echo "Python 3.11 or newer is required." >&2
  exit 1
}

"$python_bin" -m venv "$venv_dir"
"$venv_dir/bin/python" -m pip install --upgrade pip
"$venv_dir/bin/python" -m pip install "$project_dir"
"$venv_dir/bin/hermes" setup
mkdir -p "$HOME/.local/bin"
ln -sfn "$venv_dir/bin/hermes" "$HOME/.local/bin/hermes"

echo "Hermes Terminal is installed."
echo "Launch: $HOME/.local/bin/hermes"
