#!/usr/bin/env python3
"""
generate_surfaces.py
纯 UO2 表面 slab 生成脚本：构建 (111)/(110)/(100) 三个低指数面的 2x2 六层 slab，
写入 POSCAR 与 VASP 输入（INCAR/KPOINTS/MAGMOM），并保存 CIF 便于可视化。

用法：
    python scripts/generate_surfaces.py
    python scripts/generate_surfaces.py --only 111 110
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from structure_utils import (
    build_uo2_bulk_pymatgen,
    generate_slab,
    set_afm_magmoms,
    assign_layers,
    write_structure,
    write_cif,
)
from vasp_utils import write_incar, write_kpoints

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SURFACE_NAMES = {"111": (1, 1, 1), "110": (1, 1, 0), "100": (1, 0, 0)}


def verify_6_layers(structure, label: str) -> bool:
    """检查 slab 是否为 6 层、每层 4 U（2x2 超胞时）."""
    layers = assign_layers(structure, axis=2)
    print(f"  [{label}] 层数 = {len(layers)}")
    for li in sorted(layers.keys()):
        u_count = sum(1 for i in layers[li] if str(structure[i].specie) == "U")
        o_count = sum(1 for i in layers[li] if str(structure[i].specie) == "O")
        print(f"    layer {li}: {u_count} U + {o_count} O")
    return len(layers) >= 6


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="+", default=["111", "110", "100"],
                        help="只生成指定晶面")
    parser.add_argument("--slab-size", type=float, default=18.0,
                        help="slab 厚度 (A), 默认 18 约 6 层")
    parser.add_argument("--vacuum", type=float, default=18.0,
                        help="真空层厚度 (A)")
    args = parser.parse_args()

    base = os.path.join(PROJECT_ROOT, "01_surface_generation")
    os.makedirs(base, exist_ok=True)

    bulk = build_uo2_bulk_pymatgen(5.47)
    bulk_dir = os.path.join(PROJECT_ROOT, "00_bulk", "UO2_bulk")
    os.makedirs(bulk_dir, exist_ok=True)
    write_structure(bulk, os.path.join(bulk_dir, "POSCAR"))

    for name in args.only:
        if name not in SURFACE_NAMES:
            raise ValueError(f"unknown surface: {name}")
        miller = SURFACE_NAMES[name]
        print(f"\n[1] 生成 UO2({name}) 表面 ...")
        slab = generate_slab(bulk, miller, min_slab_size=args.slab_size,
                             min_vacuum_size=args.vacuum, n_2x2=True)
        ok = verify_6_layers(slab, name)
        if not ok:
            print(f"  [警告] {name} slab 层数不足 6，请增大 slab-size 参数")

        out_dir = os.path.join(base, f"UO2_{name}")
        os.makedirs(out_dir, exist_ok=True)
        write_structure(slab, os.path.join(out_dir, "POSCAR"))
        write_cif(slab, os.path.join(out_dir, f"UO2_{name}.cif"))

        # AFM 磁矩：1/3/5 层 +2.0，2/4/6 层 -2.0
        magmoms = set_afm_magmoms(
            slab, magmoms={}, layer_mag={0: 2.0, 1: -2.0, 2: 2.0, 3: -2.0, 4: 2.0, 5: -2.0})
        write_incar(out_dir, f"UO2_{name}_pure_stoichiometric",
                    calc_type="surface_sto", n_ions=len(slab),
                    magmoms=magmoms, species_order=["U", "O"])
        write_kpoints(out_dir, (5, 5, 1))

        # 额外写入 k 点收敛测试模板（可选，7x7x1）
        kconv = os.path.join(base, f"UO2_{name}", "kconv_7x7x1")
        os.makedirs(kconv, exist_ok=True)
        write_kpoints(kconv, (7, 7, 1))
        write_structure(slab, os.path.join(kconv, "POSCAR"))

        print(f"  [OK] {out_dir}  (96 原子: 24U + 48O)")

    print("\n表面生成完成。可先用 VESTA 打开 01_surface_generation/UO2_*/UO2_*.cif 检查结构。")


if __name__ == "__main__":
    main()
