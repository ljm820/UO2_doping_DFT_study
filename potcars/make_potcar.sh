#!/bin/bash
# ============================================================
# make_potcar.sh -- 批量拼接 POTCAR
# 用法: POTCAR_DIR=/path/to/paw_pbe ./potcars/make_potcar.sh
# ============================================================
set -e

POTCAR_DIR=${POTCAR_DIR:-/path/to/paw_pbe}
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

make_potcar() {
    local out_dir=$1; shift
    local out_file="$out_dir/POTCAR"
    mkdir -p "$out_dir"
    : > "$out_file"
    for el in "$@"; do
        cat "$POTCAR_DIR/$el/POTCAR" >> "$out_file"
    done
    echo "[OK] $out_file  ($*)"
}

# 体相
make_potcar "$PROJECT_ROOT/00_bulk/UO2_bulk" U O
make_potcar "$PROJECT_ROOT/00_bulk/MoO2_bulk" Mo_pv O
make_potcar "$PROJECT_ROOT/00_bulk/NbO2_bulk" Nb_pv O
make_potcar "$PROJECT_ROOT/00_bulk/ZrO2_bulk" Zr_sv O
make_potcar "$PROJECT_ROOT/00_bulk/TiO2_bulk" Ti_pv O
make_potcar "$PROJECT_ROOT/00_bulk/O2_molecule" O

# 表面
for surf in 111 110 100; do
    make_potcar "$PROJECT_ROOT/01_surface_generation/UO2_$surf" U O
done

# 掺杂体系 (Mo/Nb/Zr/Ti)
for dop in Mo Nb Zr Ti; do
    case $dop in
        Mo) pot=Mo_pv ;;
        Nb) pot=Nb_pv ;;
        Zr) pot=Zr_sv ;;
        Ti) pot=Ti_pv ;;
    esac
    for conc in MOX-8 MOX-17 MOX-25 MOX-33; do
        for surf in 111 110 100; do
            make_potcar "$PROJECT_ROOT/02_stoichiometric_MOX/$dop/$conc/$surf" U $pot O
            make_potcar "$PROJECT_ROOT/03_substoichiometric/U1-y${dop}yO2-x/$conc/$surf/vac_next_to_dopant" U $pot O
            make_potcar "$PROJECT_ROOT/03_substoichiometric/U1-y${dop}yO2-x/$conc/$surf/vac_away_from_dopant" U $pot O
            make_potcar "$PROJECT_ROOT/04_hyperstoichiometric/U1-y${dop}yO2+x/$conc/$surf/inter_next_to_dopant" U $pot O
            make_potcar "$PROJECT_ROOT/04_hyperstoichiometric/U1-y${dop}yO2+x/$conc/$surf/inter_away_from_dopant" U $pot O
        done
    done
done

# 纯 UO2 空位/间隙
for surf in 111 110 100; do
    make_potcar "$PROJECT_ROOT/03_substoichiometric/UO2-x/$surf" U O
    make_potcar "$PROJECT_ROOT/04_hyperstoichiometric/UO2+x/$surf" U O
done

echo ""
echo "POTCAR 拼接完成。请用 'grep TITEL POTCAR' 校验各文件。"
