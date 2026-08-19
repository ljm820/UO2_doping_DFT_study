#!/usr/bin/env python3
"""
doping_poscar.py
掺杂结构生成脚本：将 UO2 表面 slab 两侧对称的表面 U 替换为
Mo / Nb / Zr / Ti，生成不同含量（y = 0.08 / 0.17 / 0.25 / 0.33）的
化学计量比 U1-yMyO2 结构，并写入 VASP 输入文件。

用法：
    python scripts/doping_poscar.py                        # 使用默认 slab
    python scripts/doping_poscar.py --surfaces 111 110 100
    python scripts/doping_poscar.py --dopants Mo Nb Zr Ti
    python scripts/doping_poscar.py --concentrations 8 17 25 33
    python scripts/doping_poscar.py --all-combos          # 生成所有替换组合
"""

from __future__ import annotations

import argparse
import os
import sys
from itertools import combinations

import numpy as np
from pymatgen.core import Structure

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from structure_utils import DOPANTS, assign_layers, write_structure
from vasp_utils import write_incar, write_kpoints

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SURFACE_NAMES = {"111": (1, 1, 1), "110": (1, 1, 0), "100": (1, 0, 0)}
# 每侧替换 U 数 -> 含量名称
CONC = {1: "MOX-8", 2: "MOX-17", 3: "MOX-25", 4: "MOX-33"}


def surface_u_indices(structure: Structure, n_per_side: int = 4) -> tuple:
    """
    返回上下两个表面层中各 n_per_side 个 U 的索引。

    策略：以层为单元取顶层与底层的 U，按面内坐标排序以便选择相邻位。
    """
    layers = assign_layers(structure, reference_species="U")
    layer_idx = sorted(layers.keys())
    top_u, bottom_u = [], []
    for li in [layer_idx[-1], layer_idx[-2]]:
        for i in layers[li]:
            if str(structure[i].specie) == "U":
                top_u.append(i)
    for li in [layer_idx[0], layer_idx[1]]:
        for i in layers[li]:
            if str(structure[i].specie) == "U":
                bottom_u.append(i)

    def sort_xy(indices):
        return sorted(indices, key=lambda i: (structure[i].coords[0], structure[i].coords[1]))

    return sort_xy(top_u)[:n_per_side], sort_xy(bottom_u)[:n_per_side]


def make_doped_structure(base: Structure, top_idx: list, bottom_idx: list,
                         element: str) -> Structure:
    """替换两侧表面 U 为掺杂元素."""
    s = base.copy()
    for idx in top_idx + bottom_idx:
        s.replace(idx, element)
    return s


def write_doping_calc(s, out_dir: str, system: str, calc_type="surface_sto",
                      species_order=None):
    os.makedirs(out_dir, exist_ok=True)
    write_structure(s, os.path.join(out_dir, "POSCAR"), species_order=species_order)
    write_incar(out_dir, system, calc_type=calc_type, n_ions=len(s),
                magmoms=None, species_order=species_order)
    write_kpoints(out_dir, (5, 5, 1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--surfaces", nargs="+", default=["111", "110", "100"])
    parser.add_argument("--dopants", nargs="+", default=DOPANTS)
    parser.add_argument("--concentrations", nargs="+", type=int, default=[8, 17, 25, 33])
    parser.add_argument("--all-combos", action="store_true",
                        help="对 n>=2 生成所有 C(4,n) 替换组合（默认只取一种相邻排列）")
    parser.add_argument("--slab-root", default=None,
                        help="纯 UO2 slab 所在目录（默认 01_surface_generation/UO2_<surface>）")
    parser.add_argument("--calc-type", default="surface_sto",
                        help="surface_sto 或 surface_substo")
    args = parser.parse_args()

    conc_map = {8: 1, 17: 2, 25: 3, 33: 4}
    for surf in args.surfaces:
        if surf not in SURFACE_NAMES:
            raise ValueError(f"unknown surface {surf}")
        slab_root = args.slab_root or os.path.join(
            PROJECT_ROOT, "01_surface_generation", f"UO2_{surf}")
        slab_poscar = os.path.join(slab_root, "POSCAR")
        if not os.path.exists(slab_poscar):
            print(f"[跳过] 未找到 {slab_poscar}")
            continue

        base = Structure.from_file(slab_poscar)
        top_u, bottom_u = surface_u_indices(base)
        print(f"[{surf}] 表面 U: top={top_u}, bottom={bottom_u}")

        for dop in args.dopants:
            for conc in args.concentrations:
                n_rep = conc_map[conc]
                species_order = ["U", dop, "O"]
                if n_rep > len(top_u):
                    continue
                if args.all_combos:
                    combos = list(combinations(range(len(top_u)), n_rep))
                else:
                    combos = [tuple(range(n_rep))]
                for c in combos:
                    top_sel = [top_u[i] for i in c]
                    bottom_sel = [bottom_u[i] for i in c]
                    s = make_doped_structure(base, top_sel, bottom_sel, dop)
                    out_dir = os.path.join(
                        PROJECT_ROOT, "02_stoichiometric_MOX", dop, conc_map_name(conc),
                        surf)
                    write_doping_calc(s, out_dir,
                                      system=f"U_{1 - conc / 100:.2f}{dop}_{conc / 100:.2f}O2_{surf}",
                                      calc_type=args.calc_type,
                                      species_order=species_order)
                    print(f"[OK] {dop} {conc} {surf} -> {out_dir}")
    print("\n掺杂结构生成完成。")


def conc_map_name(conc: int) -> str:
    return {8: "MOX-8", 17: "MOX-17", 25: "MOX-25", 33: "MOX-33"}[conc]


if __name__ == "__main__":
    main()
