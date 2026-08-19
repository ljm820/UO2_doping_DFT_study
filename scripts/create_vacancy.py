#!/usr/bin/env python3
"""
create_vacancy.py
O 空位生成脚本：在 UO2 / MOX 表面两侧对称移除一个表面 O，
生成低化学计量比 UO2-x / U1-yMyO2-x 结构（O:M = 1.92:1）。

支持两类空位位置：
  - next_to_dopant   : 空位紧邻掺杂元素（MOX 体系）
  - away_from_dopant : 空位远离掺杂元素（MOX 体系）
  - surface          : 纯 UO2 表面空位（选取表面 O）

用法：
    python scripts/create_vacancy.py --surfaces 111 110 100 --kind surface
    python scripts/create_vacancy.py --surfaces 111 --kind next_to_dopant
    python scripts/create_vacancy.py --surfaces 111 --kind away_from_dopant
    python scripts/create_vacancy.py --dopants Mo Nb --concentrations 8
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from pymatgen.core import Structure

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from structure_utils import DOPANTS, assign_layers, write_structure
from vasp_utils import write_incar, write_kpoints

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SURFACE_NAMES = ["111", "110", "100"]
CONC_MAP = {8: 1, 17: 2, 25: 3, 33: 4}


def surface_oxygens(structure: Structure, n_layers: int = 1):
    """返回上下表面层的 O 原子索引."""
    layers = assign_layers(structure, reference_species="U")
    layer_idx = sorted(layers.keys())
    top = [i for li in layer_idx[-n_layers:] for i in layers[li]
           if str(structure[i].specie) == "O"]
    bottom = [i for li in layer_idx[:n_layers] for i in layers[li]
              if str(structure[i].specie) == "O"]
    return top, bottom


def mirror_index(structure: Structure, idx: int, n_layers: int = 1):
    """
    在相对表面上找与 idx 对称的 O 索引（按 |z_bottom - z_top| 最近匹配）。
    """
    layers = assign_layers(structure, reference_species="U")
    layer_idx = sorted(layers.keys())
    z = structure[idx].frac_coords[2]
    # 判断 idx 在上还是在下
    top_layers = layer_idx[-n_layers:]
    if z in [structure[i].frac_coords[2] for i in layers[top_layers[-1]]]:
        # idx 在上表面，找下表面 z 最小侧对应的 O
        target_z = min(structure[i].frac_coords[2] for i in layers[layer_idx[0]])
        candidates = [i for li in layer_idx[:n_layers] for i in layers[li]
                      if str(structure[i].specie) == "O"]
        # 选面内 xy 最接近的
        best = min(candidates, key=lambda i: np.linalg.norm(
            structure[i].coords[:2] - structure[idx].coords[:2]))
        return best
    else:
        target_z = max(structure[i].frac_coords[2] for i in layers[layer_idx[-1]])
        candidates = [i for li in layer_idx[-n_layers:] for i in layers[li]
                      if str(structure[i].specie) == "O"]
        best = min(candidates, key=lambda i: np.linalg.norm(
            structure[i].coords[:2] - structure[idx].coords[:2]))
        return best


def find_oxygens_near_dopants(structure: Structure, dopant_indices,
                              surface_os: list, k: int = 3):
    """返回离任一掺杂元素最近的 surface O 索引（按距离排序）."""
    def dist(o_idx):
        c = structure[o_idx].coords
        return min(np.linalg.norm(c - structure[d].coords) for d in dopant_indices)
    return sorted(surface_os, key=dist)[:k]


def find_oxygens_far_from_dopants(structure: Structure, dopant_indices,
                                  surface_os: list, k: int = 3):
    """返回离所有掺杂元素最远的 surface O 索引."""
    def dist(o_idx):
        c = structure[o_idx].coords
        return min(np.linalg.norm(c - structure[d].coords) for d in dopant_indices)
    return sorted(surface_os, key=dist, reverse=True)[:k]


def remove_symmetric_vacancy(structure: Structure, o_idx: int) -> Structure:
    """移除 o_idx 及其在相对表面的对称 O，返回新结构."""
    mirror = mirror_index(structure, o_idx)
    s = structure.copy()
    if mirror == o_idx:
        # 兜底：找同表面最近的其他 O
        s.remove_sites([o_idx])
    else:
        s.remove_sites([o_idx, mirror])
    return s


def write_vacancy_calc(s, out_dir: str, system: str, species_order=None):
    os.makedirs(out_dir, exist_ok=True)
    write_structure(s, os.path.join(out_dir, "POSCAR"), species_order=species_order)
    write_incar(out_dir, system, calc_type="surface_substo", n_ions=len(s),
                magmoms=None, species_order=species_order)
    write_kpoints(out_dir, (5, 5, 1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--surfaces", nargs="+", default=SURFACE_NAMES)
    parser.add_argument("--kind", default="surface",
                        choices=["surface", "next_to_dopant", "away_from_dopant"])
    parser.add_argument("--dopants", nargs="+", default=DOPANTS)
    parser.add_argument("--concentrations", nargs="+", type=int, default=[8])
    args = parser.parse_args()

    for surf in args.surfaces:
        # ===== 纯 UO2 空位 =====
        if args.kind == "surface":
            slab = os.path.join(PROJECT_ROOT, "01_surface_generation",
                                f"UO2_{surf}", "POSCAR")
            if not os.path.exists(slab):
                print(f"[跳过] 缺少 {slab}")
                continue
            s = Structure.from_file(slab)
            top_os, bottom_os = surface_oxygens(s)
            if not top_os:
                print(f"[跳过] {surf} 无表面 O")
                continue
            o_idx = top_os[0]
            s_vac = remove_symmetric_vacancy(s, o_idx)
            out = os.path.join(PROJECT_ROOT, "03_substoichiometric",
                               "UO2-x", surf)
            write_vacancy_calc(s_vac, out, f"UO2-x_{surf}", species_order=["U", "O"])
            print(f"[OK] UO2-x {surf} -> {out}  (U={s_vac.composition['U']}, "
                  f"O={s_vac.composition['O']})")
            continue

        # ===== MOX 空位 =====
        for dop in args.dopants:
            for conc in args.concentrations:
                base = os.path.join(PROJECT_ROOT, "02_stoichiometric_MOX",
                                    dop, conc_name(conc), surf)
                poscar = os.path.join(base, "POSCAR")
                if not os.path.exists(poscar):
                    print(f"[跳过] 缺少 {poscar}")
                    continue
                s = Structure.from_file(poscar)
                dop_indices = [i for i, site in enumerate(s)
                               if str(site.specie) == dop]
                top_os, bottom_os = surface_oxygens(s)
                if not top_os or not dop_indices:
                    print(f"[跳过] {dop} {conc} {surf} 缺少表面 O 或掺杂位")
                    continue
                if args.kind == "next_to_dopant":
                    cands = find_oxygens_near_dopants(s, dop_indices, top_os)
                else:
                    cands = find_oxygens_far_from_dopants(s, dop_indices, top_os)
                o_idx = cands[0]
                s_vac = remove_symmetric_vacancy(s, o_idx)
                out = os.path.join(PROJECT_ROOT, "03_substoichiometric",
                                   f"U1-y{dop}yO2-x", conc_name(conc), surf,
                                   f"vac_{args.kind}")
                write_vacancy_calc(s_vac, out,
                                   system=f"U1-y{dop}yO2-x_{surf}_{args.kind}",
                                   species_order=["U", dop, "O"])
                print(f"[OK] {dop} {conc} {surf} {args.kind} -> {out} "
                      f"(U={s_vac.composition['U']}, {dop}={s_vac.composition[dop]}, "
                      f"O={s_vac.composition['O']})")
    print("\n空位结构生成完成。")


def conc_name(conc: int) -> str:
    return {8: "MOX-8", 17: "MOX-17", 25: "MOX-25", 33: "MOX-33"}[conc]


if __name__ == "__main__":
    main()
