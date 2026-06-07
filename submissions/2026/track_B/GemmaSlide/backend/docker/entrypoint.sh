#!/usr/bin/env sh
set -eu

# Refresh font cache so runtime-mounted fonts are available to LibreOffice.
if command -v fc-cache >/dev/null 2>&1; then
  fc-cache -f >/dev/null 2>&1 || true
fi

exec "$@"
