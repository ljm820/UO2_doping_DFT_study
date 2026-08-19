#!/usr/bin/env python3
"""
subsurface_doping.py
次表面掺杂结构生成（仅 (111) 面，对应论文方法 B/C 与 docs/02 Stage 5）。

方法 A（表面掺杂，doping_poscar.py）：
    替换最外层 U（第 1/6 层）——已由 doping_poscar.py 覆盖。
方法 B（次表面掺杂）：
    替换第 2 层与第 5 层（2nd+5th，紧邻表面之下的一层）。
方法 C（内部掺杂）：
    替换第 3 层与第 4 层（3rd+4th，slab 中心附近）。

产物：
    05_subsurface_111/{Mo,Nb,Zr,Ti}/MOX-8/{methodB,methodC}/
    每侧替换 1 个 U（对应 y=0.08, MOX-8 浓度），保持化学计量比。

用法：
    python scripts/subsurface_doping.py                       # 全部 4 元素 x 2 方法
    python scripts/subsurface_doping.py --dopants Mo Nb
    python scripts/subsurface_doping.py --methods B
    python scripts/subsurface_doping.py --slab-root 01_surface_generation/UO2_111
"""

from __future__ import annotations

import argparse
import os
import sys

from pymatgen.core import Structure

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from structure_utils import DOPANTS, assign_layers, write_structure
from vasp_utils import write_incar, write_kpoints

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ROOT = os.path.join(PROJECT_ROOT, "05_subsurface_111")

# 方法 B: 层 1（次表面，从 0 计）两侧；方法 C: 层 2（内部）两侧
# assign_layers 返回 layer_index 从 0（最下层）到 N-1（最上层），6 层 slab 即 0..5
METHOD_LAYERS = {
    "B": (1, 4),   # 第 2 层（index 1）与第 5 层（index 4）
    "C": (2, 3),   # 第 3 层（index 2）与第 4 层（index 3）
}


def layer_u_indices(structure: Structure, layer_indices) -> list:
    """返回指定层中所有 U 的索引，按面内坐标排序."""
    layers = assign_layers(structure, reference_species="U")
    u_idx = []
    for li in layer_indices:
        for i in layers.get(li, []):
            if str(structure[i].specie) == "U":
                u_idx.append(i)
    # 按面内坐标排序，保证每侧替换的是对应位置（而非任意位）
    return sorted(u_idx, key=lambda i: (structure[i].coords[0], structure[i].coords[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dopants", nargs="+", default=DOPANTS)
    parser.add_argument("--methods", nargs="+", choices=["B", "C"], default=["B", "C"])
    parser.add_argument("--slab-root", default=None,
                        help="纯 UO2 (111) slab 目录（默认 01_surface_generation/UO2_111）")
    parser.add_argument("--n-sub-per-side", type=int, default=1,
                        help="每侧替换的次表面 U 数（默认 1，对应 y=0.08）")
    args = parser.parse_args()

    slab_root = args.slab_root or os.path.join(
        PROJECT_ROOT, "01_surface_generation", "UO2_111")
    slab_poscar = os.path.join(slab_root, "POSCAR")
    if not os.path.exists(slab_poscar):
        print(f"[跳过] 未找到 {slab_poscar}，请先生成 (111) slab")
        sys.exit(0)

    base = Structure.from_file(slab_poscar)
    print(f"[slab] {base.formula} ({len(base)} 原子)")

    for method in args.methods:
        layer_indices = METHOD_LAYERS[method]
        u_idx = layer_u_indices(base, layer_indices)
        n_per_side = args.n_sub_per_side
        if len(u_idx) < 2 * n_per_side:
            print(f"[跳过] 方法{method} 层 {layer_indices} 中 U 不足 "
                  f"({len(u_idx)} < {2 * n_per_side})")
            continue
        # 前一半属于下层（低 z），后一半属于上层（高 z）
        bottom_sel = u_idx[:n_per_side]
        top_sel = u_idx[-n_per_side:]
        print(f"[方法{method}] 层 {layer_indices}: bottom={bottom_sel}, top={top_sel}")

        for dop in args.dopants:
            s = base.copy()
            for idx in bottom_sel + top_sel:
                s.replace(idx, dop)
            out_dir = os.path.join(OUT_ROOT, dop, "MOX-8", f"method{method}")
            os.makedirs(out_dir, exist_ok=True)
            species_order = ["U", dop, "O"]
            write_structure(s, os.path.join(out_dir, "POSCAR"),
                            species_order=species_order)
            write_incar(out_dir, f"U1-y{dop}yO2_subsurf{method}", calc_type="surface_sto",
                        n_ions=len(s), magmoms=None, species_order=species_order)
            write_kpoints(out_dir, (5, 5, 1))
            print(f"[OK] {dop} 方法{method} -> {out_dir}  ({s.formula})")
    print("\n次表面掺杂结构生成完成。")


if __name__ == "__main__":
    main()
