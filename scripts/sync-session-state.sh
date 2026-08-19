#!/bin/bash
# ============================================================
# sync-session-state.sh — SSHP (Session State Handover Protocol) 同步脚本
#
# 作用：在 <project>/.claude/session-state/ 与 ~/.claude/session-state/
#       之间双向同步会话状态（identity/activation/decision-log/context/reference）。
#
# 用法:
#   bash scripts/sync-session-state.sh status    # 查看两目录差异
#   bash scripts/sync-session-state.sh push      # WS -> Home（会话结束调用）
#   bash scripts/sync-session-state.sh pull      # Home -> WS（新会话开始调用）
#   bash scripts/sync-session-state.sh backup    # 仅创建备份
#
# 文件权威源规则（见 docs/SSHP_PROTOCOL.md）:
#   identity.md / activation-prompt.md : Home 权威（会话开始 Home→WS）
#   decision-log.md / context.md / reference_*.md : WS 权威（会话结束 WS→Home）
# ============================================================

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$PROJECT_ROOT/.claude/session-state"
HOME_DIR="${HOME:-/root}/.claude/session-state"
ARCHIVE_DIR="$PROJECT_ROOT/archives/session-state-backups"

HOME_AUTHORITATIVE=("identity.md" "activation-prompt.md")
WS_AUTHORITATIVE=("decision-log.md" "context.md")

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die() { log "错误: $*"; exit 1; }

# ---------- 备份 ----------
backup() {
    local ts
    ts=$(date '+%Y%m%d_%H%M%S')
    local dest="$ARCHIVE_DIR/${ts}_pre-sync"
    mkdir -p "$dest"
    # 备份两目录中存在的文件（不删除源）
    for d in "$WS_DIR" "$HOME_DIR"; do
        [[ -d "$d" ]] || continue
        for f in "$d"/*.md; do
            [[ -f "$f" ]] && cp -p "$f" "$dest/"
        done
    done
    log "备份已创建: $dest"
}

# ---------- 确保目录存在 ----------
ensure_dirs() {
    mkdir -p "$WS_DIR" "$HOME_DIR"
}

# ---------- status ----------
status() {
    echo "WS  : $WS_DIR"
    echo "Home: $HOME_DIR"
    echo ""
    for f in identity.md activation-prompt.md decision-log.md context.md; do
        ws_f="$WS_DIR/$f"
        home_f="$HOME_DIR/$f"
        if [[ -f "$ws_f" && -f "$home_f" ]]; then
            if ! diff -q "$ws_f" "$home_f" >/dev/null 2>&1; then
                echo "DIFF : $f  (WS 与 Home 不同)"
            else
                echo "SAME : $f"
            fi
        elif [[ -f "$ws_f" ]]; then
            echo "WS-ONLY : $f"
        elif [[ -f "$home_f" ]]; then
            echo "HOME-ONLY : $f"
        else
            echo "MISSING : $f (两端都不存在)"
        fi
    done
    echo ""
    echo "reference_*.md:"
    for f in "$WS_DIR"/reference_*.md; do
        [[ -f "$f" ]] && echo "  $(basename "$f")  (WS 权威)"
    done
}

# ---------- push: WS -> Home (会话结束) ----------
push() {
    ensure_dirs
    backup
    log "同步 WS -> Home ..."
    # WS 权威文件：决策/上下文/参考
    for f in "${WS_AUTHORITATIVE[@]}"; do
        [[ -f "$WS_DIR/$f" ]] && cp -p "$WS_DIR/$f" "$HOME_DIR/$f" \
            && log "  push: $f"
    done
    for f in "$WS_DIR"/reference_*.md; do
        [[ -f "$f" ]] && cp -p "$f" "$HOME_DIR/" \
            && log "  push: $(basename "$f")"
    done
    # Home 权威文件：若 home 更新则拉回 WS
    for f in "${HOME_AUTHORITATIVE[@]}"; do
        if [[ -f "$HOME_DIR/$f" ]] && \
           { [[ ! -f "$WS_DIR/$f" ]] || ! diff -q "$HOME_DIR/$f" "$WS_DIR/$f" >/dev/null 2>&1; }; then
            cp -p "$HOME_DIR/$f" "$WS_DIR/$f"
            log "  pull(Home->WS): $f"
        fi
    done
    log "push 完成。"
}

# ---------- pull: Home -> WS (新会话开始) ----------
pull() {
    ensure_dirs
    backup
    log "同步 Home -> WS ..."
    # Home 权威文件
    for f in "${HOME_AUTHORITATIVE[@]}"; do
        [[ -f "$HOME_DIR/$f" ]] && cp -p "$HOME_DIR/$f" "$WS_DIR/$f" \
            && log "  pull: $f"
    done
    # WS 权威文件：仅在 home 比 WS 新时覆盖（按 mtime 比较）
    for f in "${WS_AUTHORITATIVE[@]}"; do
        if [[ -f "$HOME_DIR/$f" && -f "$WS_DIR/$f" ]]; then
            if [[ "$HOME_DIR/$f" -nt "$WS_DIR/$f" ]]; then
                cp -p "$HOME_DIR/$f" "$WS_DIR/$f"
                log "  pull(Home 更新): $f"
            fi
        elif [[ -f "$HOME_DIR/$f" ]]; then
            cp -p "$HOME_DIR/$f" "$WS_DIR/$f"
            log "  pull(新文件): $f"
        fi
    done
    log "pull 完成。"
}

# ---------- 主入口 ----------
case "${1:-status}" in
    status)  status ;;
    push)    push ;;
    pull)    pull ;;
    backup)  backup ;;
    *)       die "未知子命令: $1 (支持: status | push | pull | backup)" ;;
esac
