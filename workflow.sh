#!/bin/bash
# ============================================================
# workflow.sh — UO2 掺杂体系 VASP 研究主工作流 (Stage 0-7)
#
# 用法:
#   ./workflow.sh --stage 0          # 只跑 Stage 0（体相）
#   ./workflow.sh --all              # 顺序执行 Stage 0-7
#   ./workflow.sh --resume 2         # 从 Stage 2 继续
#   ./workflow.sh --stage 6 --defect Va_O1
#
# 前置: 已安装 VASP (vasp_std)，POTCAR 已由 potcars/make_potcar.sh 生成。
# ============================================================

set -uo pipefail

# ---------- 配置 ----------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$PROJECT_ROOT/scripts"
RESULTS="$PROJECT_ROOT/results"
VASP_EXEC="${VASP_EXEC:-vasp_std}"        # 可用环境变量覆盖
MPIRUN="${MPIRUN:-mpirun -np ${OMPI_NUM_PROC:-64}}"
NCORE="${NCORE:-8}"
PYTHON="${PYTHON:-python3}"

mkdir -p "$RESULTS"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die() { log "错误: $*"; exit 1; }

# ---------- 运行 VASP 的辅助函数 ----------
run_vasp() {
    # 用法: run_vasp <目录>
    local d="$1"
    [[ -f "$d/INCAR" && -f "$d/POSCAR" && -f "$d/KPOINTS" && -f "$d/POTCAR" ]] \
        || { log "警告: $d 缺少 VASP 输入文件，跳过"; return 1; }
    log "运行 VASP: $d"
    ( cd "$d" && $MPIRUN "$VASP_EXEC" > vasp.log 2>&1 )
    if $PYTHON "$SCRIPTS/check_convergence.py" "$d" --csv "$RESULTS/conv_stage.csv" >/dev/null 2>&1; then
        :
    fi
}

# ---------- Stage 0: 体相优化 ----------
stage0() {
    log "=== Stage 0: 体相优化（UO2 + MO2 参考相 + O2 分子） ==="
    $PYTHON "$SCRIPTS/build_bulk.py"
    for d in "$PROJECT_ROOT/00_bulk"/*/; do
        [[ -d "$d" && -f "$d/POSCAR" ]] || continue
        run_vasp "$d"
    done
    log "Stage 0 完成，检查收敛: python3 $SCRIPTS/check_convergence.py $PROJECT_ROOT/00_bulk"
    # N1 分支判断（人工确认晶格常数与 5.47 Å 偏差 < 2%）
}

# ---------- Stage 1: 纯 UO2 表面 ----------
stage1() {
    log "=== Stage 1: 纯 UO2 表面（111/110/100） ==="
    $PYTHON "$SCRIPTS/generate_surfaces.py"
    $PYTHON "$SCRIPTS/write_vasp_inputs.py"
    for d in "$PROJECT_ROOT/01_surface_generation"/pure*/; do
        [[ -d "$d" && -f "$d/POSCAR" ]] || continue
        run_vasp "$d"
    done
    log "Stage 1 完成。检查 N2: E_sur(111) 应在 [0.45, 0.60] J/m²"
}

# ---------- Stage 2: 化学计量比掺杂 U1-yMyO2 ----------
stage2() {
    log "=== Stage 2: U1-yMyO2 表面（Mo/Nb/Zr/Ti x 4 含量） ==="
    $PYTHON "$SCRIPTS/doping_poscar.py"
    $PYTHON "$SCRIPTS/write_vasp_inputs.py"
    for d in "$PROJECT_ROOT/02_stoichiometric_MOX"/MOX*/; do
        [[ -d "$d" && -f "$d/POSCAR" ]] || continue
        run_vasp "$d"
    done
    log "Stage 2 完成。检查 N3: E_rep 趋势单调性。"
}

# ---------- Stage 3: 低化学计量比（O 空位） ----------
stage3() {
    log "=== Stage 3: UO2-x / U1-yMyO2-x（O 空位） ==="
    $PYTHON "$SCRIPTS/create_vacancy.py"
    $PYTHON "$SCRIPTS/write_vasp_inputs.py"
    for d in "$PROJECT_ROOT/03_substoichiometric"/*/; do
        [[ -d "$d" && -f "$d/POSCAR" ]] || continue
        run_vasp "$d"
    done
    log "Stage 3 完成。检查 N4: UO2 空位能 ≈ 5.81/5.47/4.98 eV (111/110/100)"
}

# ---------- Stage 4: 过化学计量比（间隙 O） ----------
stage4() {
    log "=== Stage 4: UO2+x / U1-yMyO2+x（间隙 O） ==="
    $PYTHON "$SCRIPTS/build_hyperstoich.py"
    $PYTHON "$SCRIPTS/write_vasp_inputs.py"
    for d in "$PROJECT_ROOT/04_hyperstoichiometric"/*/; do
        [[ -d "$d" && -f "$d/POSCAR" ]] || continue
        run_vasp "$d"
    done
    log "Stage 4 完成。检查 N5: 间隙 O 形成能与空位能对比。"
}

# ---------- Stage 5: 次表面掺杂（仅 111） ----------
stage5() {
    log "=== Stage 5: 次表面掺杂 111（方法 B/C） ==="
    if [[ -f "$SCRIPTS/subsurface_doping.py" ]]; then
        $PYTHON "$SCRIPTS/subsurface_doping.py"
        $PYTHON "$SCRIPTS/write_vasp_inputs.py"
        for d in "$PROJECT_ROOT/05_subsurface_111"/*/; do
            [[ -d "$d" && -f "$d/POSCAR" ]] || continue
            run_vasp "$d"
        done
    else
        log "警告: scripts/subsurface_doping.py 未生成，跳过 Stage 5"
    fi
    log "Stage 5 完成。检查 N6: 方法 A/B/C 替换能差异 < 0.2 eV"
}

# ---------- Stage 6: pydefect 缺陷热力学 ----------
stage6() {
    log "=== Stage 6: pydefect 缺陷热力学 ==="
    # 1) 生成缺陷结构目录
    if [[ -n "${DEFECT_FILTER:-}" ]]; then
        $PYTHON "$PROJECT_ROOT/05_pydefect/run_pydefect.py" setup --defect "$DEFECT_FILTER"
    else
        $PYTHON "$PROJECT_ROOT/05_pydefect/run_pydefect.py" setup
    fi
    # 2) 运行各电荷态 VASP（借用完美超胞的 POSCAR 输入与 MAGMOM 约定）
    for d in "$PROJECT_ROOT/05_pydefect"/[A-Z]*_*/; do
        [[ -d "$d" && -f "$d/POSCAR" ]] || continue
        # 补 POTCAR（从 00_bulk 复制）
        [[ -f "$d/POTCAR" ]] || {
            src="$(ls "$PROJECT_ROOT/00_bulk"/*/POTCAR 2>/dev/null | head -1)"
            [[ -n "$src" ]] && cp "$src" "$d/POTCAR"
        }
        run_vasp "$d"
    done
    # 3) 解析结果
    $PYTHON "$PROJECT_ROOT/05_pydefect/run_pydefect.py" parse
    log "Stage 6 完成。检查 N7: 转变能级位置与缺陷形成能排序。"
}

# ---------- Stage 7: 后处理与汇总 ----------
stage7() {
    log "=== Stage 7: 后处理与汇总 ==="
    if [[ -f "$SCRIPTS/analyze_energies.py" ]]; then
        $PYTHON "$SCRIPTS/analyze_energies.py" \
            "$PROJECT_ROOT/results" \
            "$PROJECT_ROOT/00_bulk" "$PROJECT_ROOT/01_surface_generation" \
            "$PROJECT_ROOT/02_stoichiometric_MOX" \
            "$PROJECT_ROOT/03_substoichiometric" \
            "$PROJECT_ROOT/04_hyperstoichiometric"
    else
        log "警告: scripts/analyze_energies.py 未生成，跳过能量汇总"
    fi
    log "Stage 7 完成。检查 N8: 所有物理量趋势自洽，输出最终报告。"
}

# ---------- 主入口 ----------
STAGE_ALL=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --all) STAGE_ALL=(0 1 2 3 4 5 6 7);;
        --stage) STAGE_ALL=("$2"); shift;;
        --resume) for ((i=$2; i<=7; i++)); do STAGE_ALL+=("$i"); done; shift;;
        --defect) DEFECT_FILTER="$2"; shift;;
        *) die "未知参数: $1";;
    esac
    shift
done

[[ ${#STAGE_ALL[@]} -eq 0 ]] && die "用法: $0 --all | --stage N | --resume N [--defect NAME]"

for s in "${STAGE_ALL[@]}"; do
    case "$s" in
        0) stage0;; 1) stage1;; 2) stage2;; 3) stage3;;
        4) stage4;; 5) stage5;; 6) stage6;; 7) stage7;;
        *) die "无效 Stage: $s";;
    esac
done

log "=== 工作流全部完成 ==="
