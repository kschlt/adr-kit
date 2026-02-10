#!/usr/bin/env bash
# Branch context: structured snapshot of the full branch landscape.
# Used by the /branch skill to evaluate fit in one call.
# Output is labeled and consistent — the AI parses it to make branching decisions.
#
# What this script does (in order):
#   1. Fetches from remote (so origin/main is current)
#   2. Cleans up stale branches (merged into main)
#   3. Reports current branch state
#   4. Lists surviving WIP branches with their commits and changed files

set -euo pipefail

# ─── Step 1: Fetch from remote ───────────────────────────────────────────────
git fetch origin --quiet 2>/dev/null || echo "fetch-warning: could not reach remote"

# ─── Step 2: Clean up stale branches ─────────────────────────────────────────
# Stale = all commits already in main (git branch --merged main), excluding main itself.
STALE=$(git branch --merged main 2>/dev/null | grep -v '^\*' | grep -vE '^\s*(main|master)\s*$' | sed 's/^[* ]*//' || true)

if [ -n "$STALE" ]; then
    echo "cleaned-up:"
    for BRANCH in $STALE; do
        git branch -d "$BRANCH" >/dev/null 2>&1 && echo "  - $BRANCH" || echo "  - $BRANCH (failed to delete)"
    done
else
    echo "cleaned-up: none"
fi

# ─── Step 3: Current branch state ────────────────────────────────────────────
CURRENT=$(git branch --show-current)
echo "branch: $CURRENT"

# Clean or dirty working tree
if [ -z "$(git status --porcelain)" ]; then
    echo "clean: yes"
else
    echo "clean: no"
fi

# On main or feature branch?
if [ "$CURRENT" = "main" ] || [ "$CURRENT" = "master" ]; then
    echo "status: on-main"
else
    echo "status: on-feature"

    # Pushed to remote?
    if git rev-parse --verify "origin/$CURRENT" >/dev/null 2>&1; then
        echo "pushed: yes"
    else
        echo "pushed: no"
    fi

    # Commits on this branch since main
    COMMIT_COUNT=$(git rev-list --count main..HEAD 2>/dev/null || echo "0")
    echo "commit-count: $COMMIT_COUNT"
    echo "commits:"
    git log main..HEAD --format="  - %s" 2>/dev/null || echo "  (none)"

    # Files changed on this branch since main
    echo "files-changed:"
    git diff --name-only main..HEAD 2>/dev/null | sed 's/^/  /' || echo "  (none)"
fi

# ─── Step 4: WIP branches (other feature branches with unmerged work) ────────
# List all local branches except main/master and the current branch.
WIP_BRANCHES=$(git branch 2>/dev/null | grep -v '^\*' | grep -vE '^\s*(main|master)\s*$' | sed 's/^[* ]*//' || true)

if [ -n "$WIP_BRANCHES" ]; then
    echo "wip-branches:"
    for WIP in $WIP_BRANCHES; do
        WIP_COUNT=$(git rev-list --count main.."$WIP" 2>/dev/null || echo "0")
        # Check if pushed
        if git rev-parse --verify "origin/$WIP" >/dev/null 2>&1; then
            WIP_PUSHED="yes"
        else
            WIP_PUSHED="no"
        fi
        echo "  - name: $WIP"
        echo "    pushed: $WIP_PUSHED"
        echo "    commit-count: $WIP_COUNT"
        echo "    commits:"
        git log main.."$WIP" --format="      - %s" 2>/dev/null || echo "      (none)"
        echo "    files-changed:"
        git diff --name-only main.."$WIP" 2>/dev/null | sed 's/^/      /' || echo "      (none)"
    done
else
    echo "wip-branches: none"
fi
