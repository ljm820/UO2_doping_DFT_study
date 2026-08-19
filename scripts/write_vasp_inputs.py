#!/usr/bin/env python3
"""
write_vasp_inputs.py
为项目中所有已生成的 POSCAR 目录统一写入 INCAR / KPOINTS，
自动识别体系类型并生成 AFM 初始磁矩（MAGMOM）。

识别规则（按目录路径）：
  - 00_bulk            -> bulk        (ISIF=3)
  - 01_surface_generation -> surface_sto (纯 UO2, ISIF=3)
  - 02_stoichiometric_MOX -> surface_sto (MOX, ISIF=2)
  - 03_substoichiometric  -> surface_substo (ISIF=2)
  - 04_hyperstoichiometric-> surface_substo (ISIF=2)

用法：
    python scripts/write_vasp_inputs.py
    python scripts/write_vasp_inputs.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pymatgen.core import Structure

from structure_utils import assign_layers, DOPANTS, DOPANT_INFO
from vasp_utils import write_incar, write_kpoints, build_magmoms

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def classify(path: str) -> str:
    rel = os.path.relpath(path, PROJECT_ROOT)
    if rel.startswith("00_bulk"):
        return "bulk"
    if rel.startswith("01_surface_generation"):
        return "surface_sto"
    if rel.startswith("02_stoichiometric_MOX"):
        return "surface_sto"
    if rel.startswith("03_substoichiometric") or rel.startswith("04_hyperstoichiometric"):
        return "surface_substo"
    return "surface_sto"


def species_order_of(structure: Structure) -> list:
    """返回结构中出现的元素顺序（按首次出现）."""
    order = []
    for s in structure:
        el = str(s.specie)
        if el not in order:
            order.append(el)
    return order


def gen_magmoms(structure: Structure, calc_type: str) -> list:
    """生成初始磁矩。bulk 与 slab 分开处理。"""
    order = species_order_of(structure)
    if calc_type == "bulk":
        # 体相 UO2: 4 U 的 +2 -2 +2 -2 (对 12 原子原胞)；其他元素按 d 电子数
        u_idx = [i for i, s in enumerate(structure) if str(s.specie) == "U"]
        mag = [0.0] * len(structure)
        signs = [1, -1, 1, -1]
        for k, idx in enumerate(u_idx):
            mag[idx] = 2.0 * signs[k % 4]
        for i, s in enumerate(structure):
            el = str(s.specie)
            if el in DOPANTS:
                mag[i] = DOPANT_INFO.get(el, {}).get("d_electrons", 0) * 1.0
        return mag
    # slab
    mag = build_magmoms(structure)
    for i, s in enumerate(structure):
        el = str(s.specie)
        if el in DOPANTS:
            mag[i] = DOPANT_INFO.get(el, {}).get("d_electrons", 0) * 1.0
    return mag


def process_dir(poscar: str, dry_run: bool):
    out_dir = os.path.dirname(poscar)
    calc_type = classify(out_dir)
    structure = Structure.from_file(poscar)
    order = species_order_of(structure)
    mag = gen_magmoms(structure, calc_type)
    system = os.path.basename(out_dir)

    if dry_run:
        print(f"[dry-run] {out_dir}  ({calc_type}, {len(structure)} 原子, order={order})")
        return

    write_incar(out_dir, system, calc_type=calc_type, n_ions=len(structure),
                magmoms=mag, species_order=order)
    if "bulk" in calc_type or "O2" in system:
        mesh = (8, 8, 8)
    else:
        mesh = (5, 5, 1)
    if calc_type == "bulk" and any(el in system for el in ["MoO2", "NbO2", "ZrO2", "TiO2"]):
        mesh = (6, 6, 8)
    if "O2" in system and os.path.basename(out_dir) == "O2_molecule":
        mesh = (1, 1, 1)
    write_kpoints(out_dir, mesh)
    print(f"[OK] {out_dir}  ({calc_type}, MAGMOM={len(mag)})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    n = 0
    poscar_dirs = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        if "POSCAR" in files:
            poscar_dirs.append(os.path.join(root, "POSCAR"))
    poscar_dirs.sort()
    for poscar in poscar_dirs:
        process_dir(poscar, args.dry_run)
        n += 1
    print(f"\n共处理 {n} 个 POSCAR 目录。")


if __name__ == "__main__":
    main()
