#!/usr/bin/env python3
"""
build_hyperstoich.py
过化学计量比（UO2+x / U1-yMyO2+x）间隙氧结构生成脚本。

在 UO2 / MOX 表面 slab 两侧对称添加间隙氧（octahedral interstitial），
得到 O:M = 2.08:1（对应 x = 0.08），研究掺杂元素对过量氧容纳能力的影响。

间隙位点选择：
  - 萤石结构的八面体间隙位（4b, (1/2,1/2,1/2) 型）；
  - 用现有原子核间距检查避免重叠（min_dist 参数）。

用法：
    python scripts/build_hyperstoich.py --kind surface
    python scripts/build_hyperstoich.py --kind next_to_dopant
    python scripts/build_hyperstoich.py --kind away_from_dopant
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


def add_symmetric_interstitial(structure: Structure, frac_positions: list,
                               min_dist: float = 1.6) -> Structure:
    """
    在给定分数坐标位置添加间隙 O；返回新结构。
    frac_positions 已包含上下两个对称位置。
    """
    s = structure.copy()
    for fp in frac_positions:
        cart = s.lattice.get_cartesian_coords(np.array(fp))
        # 与现有原子最小距离检查
        dists = [s.lattice.get_distance_and_image(fp, site.frac_coords)[0]
                 for site in s]
        if min(dists) < min_dist:
            print(f"  [警告] 间隙位 {fp} 距最近原子 {min(dists):.2f} A，可能重叠")
        s.append("O", fp)
    return s


def octahedral_site(frac_center: np.ndarray, shift: float = 0.5):
    """八面体间隙位的相对偏移 (x,y,z) 之一."""
    return frac_center + np.array([shift, 0.0, 0.0])


def pick_surface_octahedral_sites(structure: Structure, kind: str,
                                  dopant_indices=None, top_layer=True):
    """
    在 slab 上表面挑选间隙氧位点。

    方法：以表面层的 U 为中心，在面外方向偏移构造候选八面体位，
    筛选不与现有原子重叠且（对 MOX）按 kind 靠近/远离掺杂元素。
    """
    layers = assign_layers(structure, reference_species="U")
    layer_idx = sorted(layers.keys())
    top_u = [i for i in layers[layer_idx[-1]] if str(structure[i].specie) == "U"]
    bottom_u = [i for i in layers[layer_idx[0]] if str(structure[i].specie) == "U"]
    if not top_u:
        return None

    # 取第一个表面 U 周围的八面体位（沿面外方向）
    def candidates(u_idx, outward):
        site = structure[u_idx]
        c = site.frac_coords.copy()
        cand = []
        for shift in [0.25, 0.5, 0.75]:
            fp = c.copy()
            fp[2] = fp[2] + outward * shift
            fp[2] = fp[2] % 1.0
            cand.append(fp)
        return cand

    top_u0 = top_u[0]
    top_cands = candidates(top_u0, outward=+1)
    bottom_u0 = bottom_u[0]
    bottom_cands = candidates(bottom_u0, outward=-1)

    # 用现有结构检查重叠，挑选最近原子距离最大的候选
    def score(structure, fp):
        dists = [structure.lattice.get_distance_and_image(fp, site.frac_coords)[0]
                 for site in structure]
        return min(dists)

    top_ok = [fp for fp in top_cands if score(structure, fp) > 1.5]
    bottom_ok = [fp for fp in bottom_cands if score(structure, fp) > 1.5]
    if not top_ok or not bottom_ok:
        print("  [警告] 未找到安全的间隙位点，尝试减小 min_dist")
        top_ok = top_cands
        bottom_ok = bottom_cands

    # 对 MOX，按 kind 排序候选：越靠近掺杂元素分数越高
    if kind == "next_to_dopant" and dopant_indices:
        def dop_score(fp):
            return min(structure.lattice.get_distance_and_image(fp, structure[d].frac_coords)[0]
                       for d in dopant_indices)
        top_ok = sorted(top_ok, key=dop_score, reverse=True)
        bottom_ok = sorted(bottom_ok, key=dop_score, reverse=True)
    elif kind == "away_from_dopant" and dopant_indices:
        def dop_score(fp):
            return min(structure.lattice.get_distance_and_image(fp, structure[d].frac_coords)[0]
                       for d in dopant_indices)
        top_ok = sorted(top_ok, key=dop_score)
        bottom_ok = sorted(bottom_ok, key=dop_score)

    return [top_ok[0], bottom_ok[0]]


def write_hyperstoich_calc(s, out_dir: str, system: str, species_order=None):
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
        if args.kind == "surface":
            slab = os.path.join(PROJECT_ROOT, "01_surface_generation",
                                f"UO2_{surf}", "POSCAR")
            if not os.path.exists(slab):
                continue
            s = Structure.from_file(slab)
            sites = pick_surface_octahedral_sites(s, "surface")
            if sites is None:
                print(f"[跳过] {surf} 无法定位间隙位")
                continue
            s_hy = add_symmetric_interstitial(s, sites)
            out = os.path.join(PROJECT_ROOT, "04_hyperstoichiometric",
                               "UO2+x", surf)
            write_hyperstoich_calc(s_hy, out, f"UO2+x_{surf}",
                                   species_order=["U", "O"])
            print(f"[OK] UO2+x {surf} -> {out}  (U={s_hy.composition['U']}, "
                  f"O={s_hy.composition['O']})")
            continue

        for dop in args.dopants:
            for conc in args.concentrations:
                base = os.path.join(PROJECT_ROOT, "02_stoichiometric_MOX",
                                    dop, conc_name(conc), surf)
                poscar = os.path.join(base, "POSCAR")
                if not os.path.exists(poscar):
                    continue
                s = Structure.from_file(poscar)
                dop_indices = [i for i, site in enumerate(s)
                               if str(site.specie) == dop]
                sites = pick_surface_octahedral_sites(s, args.kind, dop_indices)
                if sites is None:
                    continue
                s_hy = add_symmetric_interstitial(s, sites)
                out = os.path.join(PROJECT_ROOT, "04_hyperstoichiometric",
                                   f"U1-y{dop}yO2+x", conc_name(conc), surf,
                                   f"inter_{args.kind}")
                write_hyperstoich_calc(s_hy, out,
                                       system=f"U1-y{dop}yO2+x_{surf}_{args.kind}",
                                       species_order=["U", dop, "O"])
                print(f"[OK] {dop} {conc} {surf} {args.kind} -> {out} "
                      f"(U={s_hy.composition['U']}, {dop}={s_hy.composition[dop]}, "
                      f"O={s_hy.composition['O']})")
    print("\n过化学计量比结构生成完成。")


def conc_name(conc: int) -> str:
    return {8: "MOX-8", 17: "MOX-17", 25: "MOX-25", 33: "MOX-33"}[conc]


if __name__ == "__main__":
    main()
