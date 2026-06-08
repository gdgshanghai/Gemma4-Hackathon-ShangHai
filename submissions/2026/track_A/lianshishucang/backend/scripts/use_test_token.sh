#!/usr/bin/env bash

if [ -n "${ZSH_VERSION:-}" ]; then
  SCRIPT_PATH="${(%):-%N}"
else
  SCRIPT_PATH="${BASH_SOURCE[0]}"
fi

SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"

export TOKEN="$(python3 "$SCRIPT_DIR/gen_test_jwt.py")"

echo "TOKEN generated for TEST_USER_ID=${TEST_USER_ID:-2} TEST_WALLET_ADDRESS=${TEST_WALLET_ADDRESS:-0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266}"
echo "TOKEN length: ${#TOKEN}"
