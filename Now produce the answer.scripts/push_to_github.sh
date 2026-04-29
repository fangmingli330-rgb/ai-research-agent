#!/bin/bash
# Script to push the current project to the GitHub repository.
# Assumes git is installed and authentication is configured (SSH or token).

set -e

REMOTE_URL="https://github.com/fangmingli330-rgb/ai-research-agent.git"
BRANCH="main"

echo "=== Initializing git repository (if needed) ==="
if [ ! -d ".git" ]; then
    git init
    echo "Git repository initialized."
else
    echo "Git repository already exists."
fi

echo "=== Adding remote origin (if not already set) ==="
if git remote get-url origin >/dev/null 2>&1; then
    echo "Remote origin already set to: $(git remote get-url origin)"
else
    git remote add origin "$REMOTE_URL"
    echo "Remote origin added: $REMOTE_URL"
fi

echo "=== Adding all files ==="
git add .

echo "=== Checking for changes to commit ==="
if git diff --cached --quiet; then
    echo "No changes to commit."
else
    git commit -m "Initial commit"
    echo "Changes committed."
fi

echo "=== Pushing to remote ==="
git push -u origin "$BRANCH"

echo "=== Done ==="
