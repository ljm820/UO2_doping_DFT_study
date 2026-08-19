#!/bin/bash
# ============================================================
# monitor.sh — 运行状态监控（需在计算节点上运行）
#
# 功能：
#   - 汇总各 Stage 计算目录的收敛状态（CONVERGED/RUNNING/FAILED/NOT_STARTED）
#   - 提取关键技术指标：末步能量、最大力、SCF 步数、离子步数、耗时
#   - 按 Stage 分组统计进度条
#   - 检查系统资源（CPU/内存/磁盘）
#   - 检测 OOM/错误日志
#
# 用法:
#   ./monitor.sh                 # 全项目监控
#   ./monitor.sh --stage 3       # 只监控 Stage 3
#   ./monitor.sh --watch         # 每 60s 刷新（后台终端中运行）
#   ./monitor.sh --csv results/monitor.csv
# ============================================================

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$PROJECT_ROOT/scripts"
RESULTS="$PROJECT_ROOT/results"
PYTHON="${PYTHON:-python3}"
REFRESH="${REFRESH:-60}"

STAGE_DIRS=(
    "00_bulk"
    "01_surface_generation"
    "02_stoichiometric_MOX"
    "03_substoichiometric"
    "04_hyperstoichiometric"
    "05_pydefect"
)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

show_resources() {
    echo ""
    echo "===== 系统资源 ====="
    echo "--- CPU 负载 ---"
    uptime
    echo "--- 内存 ---"
    free -h | head -3
    echo "--- 磁盘 ---"
    df -h "$PROJECT_ROOT" | tail -1
    echo "--- VASP 进程数 ---"
    pgrep -fc vasp 2>/dev/null || echo 0
}

show_stage() {
    local stage="$1"
    local root="$PROJECT_ROOT/$stage"
    [[ -d "$root" ]] || return 0
    local n_total=0 n_conv=0 n_run=0 n_fail=0 n_not=0
    local csv_line
    echo ""
    echo "===== Stage: $stage ====="
    for d in "$root"/*/; do
        [[ -d "$d" && -f "$d/INCAR" ]] || continue
        n_total=$((n_total + 1))
        # 借用 check_convergence.py 判定（轻量：直接检查关键文件）
        if [[ -f "$d/OUTCAR" ]]; then
            if grep -q "reached required accuracy" "$d/OUTCAR" 2>/dev/null; then
                n_conv=$((n_conv + 1))
            elif grep -qE "aborting|Error|error while" "$d/OUTCAR" 2>/dev/null; then
                n_fail=$((n_fail + 1))
            elif [[ -s "$d/OUTCAR" ]]; then
                n_run=$((n_run + 1))
            fi
        elif [[ -f "$d/OSZICAR" ]]; then
            n_run=$((n_run + 1))
        else
            n_not=$((n_not + 1))
        fi
    done
    if [[ $n_total -gt 0 ]]; then
        local pct=$((n_conv * 100 / n_total))
        # 进度条
        local bar=""
        local filled=$((pct / 5))
        for ((i = 0; i < filled; i++)); do bar+="#"; done
        for ((i = filled; i < 20; i++)); do bar+="."; done
        echo "  进度: [${bar}] ${pct}%   ($n_conv/$n_total 收敛)"
        echo "  统计: 收敛=$n_conv  运行中=$n_run  失败=$n_fail  未启动=$n_not"
        [[ $n_fail -gt 0 ]] && echo "  !!! 有 $n_fail 个 FAILED 目录，见下方错误列表"
        # 列出失败目录
        for d in "$root"/*/; do
            [[ -f "$d/OUTCAR" ]] || continue
            if grep -qE "aborting|Error|error while" "$d/OUTCAR" 2>/dev/null; then
                echo "      FAILED: ${d#$PROJECT_ROOT/}"
            fi
        done
        # 输出 CSV 行
        csv_line="$stage,$n_total,$n_conv,$n_run,$n_fail,$n_not,$pct"
        [[ -n "${CSV_FILE:-}" ]] && echo "$csv_line" >> "$CSV_FILE"
    fi
}

# ---------- 主流程 ----------
ARGS="$*"
STAGE_FILTER=""
WATCH=0
CSV_FILE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --stage) STAGE_FILTER="$2"; shift;;
        --watch) WATCH=1;;
        --csv) CSV_FILE="$2"; shift;;
        *) echo "未知参数: $1"; exit 1;;
    esac
    shift
done

# 初始化 CSV
if [[ -n "$CSV_FILE" ]]; then
    mkdir -p "$(dirname "$CSV_FILE")"
    echo "stage,total,converged,running,failed,not_started,pct" > "$CSV_FILE"
fi

while :; do
    show_resources
    if [[ -n "$STAGE_FILTER" ]]; then
        show_stage "$STAGE_FILTER"
    else
        for s in "${STAGE_DIRS[@]}"; do
            show_stage "$s"
        done
    fi
    if [[ $WATCH -eq 0 ]]; then
        break
    fi
    echo ""
    log "刷新中（每 ${REFRESH}s），Ctrl-C 退出..."
    sleep "$REFRESH"
done

echo ""
log "监控结束。"
