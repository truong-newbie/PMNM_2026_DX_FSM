#!/usr/bin/env bash
# Install DX-FSM git hooks (pre-commit secret scan).
#
# Usage:
#   bash scripts/install-hooks.sh
#
# Bypass per commit: git commit --no-verify

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"
SOURCE_HOOK="$REPO_ROOT/scripts/pre-commit"

# 1. Install pre-commit
if [ -f "$HOOKS_DIR/pre-commit" ]; then
    echo "✓ pre-commit hook already exists at $HOOKS_DIR/pre-commit"
else
    if [ -f "$SOURCE_HOOK" ]; then
        cp "$SOURCE_HOOK" "$HOOKS_DIR/pre-commit"
        chmod +x "$HOOKS_DIR/pre-commit"
        echo "✓ Installed pre-commit hook (with secret scan)"
    else
        echo "⚠️  $SOURCE_HOOK not found, skipping pre-commit install"
    fi
fi

# 2. Verify Node.js is available
if ! command -v node >/dev/null 2>&1; then
    echo "❌ Node.js not found in PATH"
    echo "   Pre-commit hook requires Node.js to run secret scanner."
    echo "   Install: https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node -v)
echo "✓ Node.js detected: $NODE_VERSION"

# 3. Test the scanner
echo ""
echo "Testing secret scanner..."
node "$REPO_ROOT/scripts/check-secrets.cjs" || {
    echo ""
    echo "⚠️  Scanner found secrets in currently-staged files."
    echo "   This is normal if you're working on features that reference secrets."
    echo "   Resolve before committing."
    exit 0
}

echo ""
echo "✅ All hooks installed. Pre-commit secret scan is active."
echo ""
echo "Bypass (NOT recommended): git commit --no-verify"
