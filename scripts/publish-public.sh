#!/usr/bin/env bash
# ============================================================================
# publish-public.sh — Публикация очищенной версии проекта в публичный GitHub
# ============================================================================
# Создаёт временный bare-репозиторий, фильтрует только origin/main через
# filter-branch (удаляет приватные файлы из ВСЕХ коммитов этой ветки),
# пушит очищенную историю в GitHub как main.
#
# Использование:
#   git remote add public <URL_GITHUB_REPO>  # однократно
#   bash scripts/publish-public.sh
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

# ---------- настройка ----------
PUBLIC_REMOTE="public"
TARGET_BRANCH="main"
SOURCE_REF="refs/heads/main"
PUBLIC_REF="refs/heads/public-main"
TEMP_DIR=$(mktemp -d)

cleanup() { rm -rf "$TEMP_DIR"; }
trap cleanup EXIT

# ---------- загрузка фильтра ----------
FILTER_LIST=".publish-filter-list"
[[ -f "$FILTER_LIST" ]] || { echo "[publish-public] ERROR: $FILTER_LIST not found"; exit 1; }
mapfile -t FORBIDDEN_FILES < <(grep -v '^\s*#' "$FILTER_LIST" | grep -v '^\s*$' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

# ---------- функции ----------
log()  { echo "[publish-public] $*"; }
warn() { echo "[publish-public] WARNING: $*" >&2; }
die()  { echo "[publish-public] ERROR: $*" >&2; exit 1; }

# ---------- проверка ----------
[[ "$(git rev-parse --abbrev-ref HEAD)" == "main" ]] \
    || die "Switch to main branch first: git checkout main"
git remote get-url "$PUBLIC_REMOTE" >/dev/null 2>&1 \
    || die "Remote '$PUBLIC_REMOTE' not found.\n  Add it: git remote add public git@github.com:USER/REPO.git"

log "Fetching latest from origin..."
git fetch origin main

log "Excluding ${#FORBIDDEN_FILES[@]} paths (from $FILTER_LIST):"
for item in "${FORBIDDEN_FILES[@]}"; do
    log "  ✗ $item"
done

# Сохраняем URL GitHub до входа в bare-клон
GITHUB_URL=$(git remote get-url "$PUBLIC_REMOTE")

# ---------- фильтр через bare-репозиторий ----------
log "Creating temporary bare clone..."
git clone --bare "$REPO_ROOT" "$TEMP_DIR/filter.git"
cd "$TEMP_DIR/filter.git"

git rev-parse --verify "$SOURCE_REF" >/dev/null 2>&1 \
    || die "Source ref '$SOURCE_REF' not found in temporary clone"

log "Creating isolated public branch from $SOURCE_REF..."
git branch -f public-main "$SOURCE_REF"

# Формируем команду rm
RM_ARGS=""
for item in "${FORBIDDEN_FILES[@]}"; do
    RM_ARGS="$RM_ARGS '$item'"
done

log "Filtering history with git filter-branch..."
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --index-filter \
    "git rm -rf --cached --ignore-unmatch $RM_ARGS" \
    --prune-empty -- "$PUBLIC_REF"

# Удаляем backup refs
git for-each-ref --format='%(refname)' refs/original/ | while read ref; do
    git update-ref -d "$ref"
done
git reflog expire --expire=now --all
git gc --prune=now

# ---------- верификация ----------
log "Verifying no forbidden files in HEAD..."
FOUND=0
for item in "${FORBIDDEN_FILES[@]}"; do
    if git ls-tree -r --name-only "$PUBLIC_REF" | grep -q "^${item}\|^${item}/"; then
        warn "Forbidden file still present: $item"
        FOUND=1
    fi
done
[[ $FOUND -eq 0 ]] || die "Forbidden files found in HEAD — aborting push"

log "Verifying no forbidden files in history..."
HISTORY_LEAK=0
for item in "${FORBIDDEN_FILES[@]}"; do
    if git log "$PUBLIC_REF" --pretty=format: --name-only | grep -q "^${item}$\|^${item}/"; then
        warn "Forbidden file found in history: $item"
        HISTORY_LEAK=1
    fi
done
[[ $HISTORY_LEAK -eq 0 ]] || die "History contains forbidden files — aborting push"

# ---------- пуш ----------
log "Pushing cleaned history to $PUBLIC_REMOTE::$TARGET_BRANCH..."
cd "$TEMP_DIR/filter.git"
git push --force "$GITHUB_URL" "$PUBLIC_REF:refs/heads/$TARGET_BRANCH"

# ---------- итог ----------
log ""
log "============================================"
log "  Published to $PUBLIC_REMOTE::$TARGET_BRANCH"
log "  History fully rewritten (no private files)"
log "  Commits: $(git -C "$TEMP_DIR/filter.git" rev-list --count "$PUBLIC_REF")"
log "============================================"
