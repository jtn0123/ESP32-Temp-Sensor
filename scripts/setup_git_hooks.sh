#!/bin/bash

echo "Setting up Git hooks for security..."

# Configure git to use our hooks directory
git config core.hooksPath .githooks

echo "✅ Git hooks configured!"
echo ""
echo "The pre-commit hook will now:"
echo "  - Check for credential leaks before each commit"
echo "  - Block commits if passwords are found"
echo "  - Verify .gitignore is properly configured"
echo ""
echo "To test the hook:"
echo "  git add -A && git commit -m 'test'"
echo ""
echo "To bypass the hook (emergency only):"
echo "  git commit --no-verify"