#!/usr/bin/env bash
# ============================================================================
# verify-public.sh — Проверка публичной ветки на утечку закрытых файлов
# ============================================================================
# Проверяет указанную ветку/refs (по умолчанию public) на наличие запрещённых
# файлов в working tree и в полной истории коммитов.
#
# Использование:
#   bash scripts/verify-public.sh [branch_or_ref]
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

BRANCH_REF="${1:-public}"

# Загружаем список исключаемых файлов из .publish-filter-list
FILTER_LIST=".publish-filter-list"
if [[ ! -f "$FILTER_LIST" ]]; then
    echo "[verify-public] ERROR: $FILTER_LIST not found"
    exit 1
fi
mapfile -t FORBIDDEN_FILES < <(grep -v '^\s*#' "$FILTER_LIST" | grep -v '^\s*$' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

log()  { echo "[verify-public] $*"; }
warn() { echo "[verify-public] WARNING: $*" >&2; }
fail() { echo "[verify-public] FAIL: $*" >&2; }
ok()   { echo "[verify-public] OK: $*"; }

git rev-parse --verify "$BRANCH_REF" >/dev/null 2>&1 \
    || { fail "Ref '$BRANCH_REF' does not exist."; exit 1; }

log "Checking ref: $BRANCH_REF"
log "Total commits: $(git rev-list --count "$BRANCH_REF")"
echo ""

TREE_ERRORS=0
HISTORY_ERRORS=0

log "--- Checking working tree (HEAD) ---"
for item in "${FORBIDDEN_FILES[@]}"; do
    if git ls-tree -r --name-only "$BRANCH_REF" | grep -q "^${item}\|^${item}/"; then
        fail "  TREE: $item"
        TREE_ERRORS=$((TREE_ERRORS + 1))
    else
        ok "  TREE: $item — clean"
    fi
done

echo ""
log "--- Checking full history ---"
HISTORY_FILES=$(git log "$BRANCH_REF" --pretty=format: --name-only | sort -u)

for item in "${FORBIDDEN_FILES[@]}"; do
    if echo "$HISTORY_FILES" | grep -q "^${item}$\|^${item}/"; then
        fail "  HISTORY: $item"
        HISTORY_ERRORS=$((HISTORY_ERRORS + 1))
    else
        ok "  HISTORY: $item — clean"
    fi
done

echo ""
log "============================================"
log "  Results"
log "============================================"
if [[ $TREE_ERRORS -gt 0 ]]; then
    fail "  Tree leaks: $TREE_ERRORS"
else
    ok "  Tree leaks: 0"
fi
if [[ $HISTORY_ERRORS -gt 0 ]]; then
    fail "  History leaks: $HISTORY_ERRORS"
else
    ok "  History leaks: 0"
fi

TOTAL=$((TREE_ERRORS + HISTORY_ERRORS))
if [[ $TOTAL -eq 0 ]]; then
    log ""
    ok "  ALL CLEAN — no forbidden files found"
    exit 0
else
    log ""
    fail "  $TOTAL leak(s) detected!"
    exit 1
fi
