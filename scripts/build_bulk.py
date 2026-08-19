#!/usr/bin/env python3
"""
build_bulk.py
体相结构构建脚本：生成 UO2 与 MO2（M = Mo/Nb/Zr/Ti）体相 + O2 分子 POSCAR，
并写入 Stage 0 所需的 VASP 输入文件。

用法：
    python scripts/build_bulk.py            # 生成所有体相结构
    python scripts/build_bulk.py --poscar-only   # 只写 POSCAR，不写 INCAR/KPOINTS
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from pymatgen.core import Lattice, Structure

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from structure_utils import build_uo2_bulk_pymatgen, write_structure
from vasp_utils import write_incar, write_kpoints

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_mo2_bulk(element: str) -> Structure:
    """
    构建 MO2 体相（金红石结构，作为替换能参考相）。

    对 MoO2/NbO2 金红石结构参数见文章参考体系；此处给出标准金红石参数，
    实际使用时应以实验/文献结构为准（可用 Materials Project 结构）。
    a, c 为金红石晶格常数（Å）。
    """
    params = {
        "Mo": {"a": 4.86, "c": 2.79},   # MoO2 单斜畸变 → 这里用金红石近似
        "Nb": {"a": 4.84, "c": 2.99},
        "Zr": {"a": 3.60, "c": 5.20},   # 注意：ZrO2 萤石立方为 5.09，此处金红石近似
        "Ti": {"a": 4.59, "c": 2.96},
    }
    a = params[element]["a"]
    c = params[element]["c"]
    # 金红石 MO2: M 在 (0,0,0),(0.5,0.5,0.5); O 在 (x,x,0) 等, x≈0.305
    x = 0.305
    lat = Lattice.from_parameters(a, a, c, 90, 90, 90)
    coords = [
        [0.0, 0.0, 0.0], [0.5, 0.5, 0.5],
        [x, x, 0.0], [-x, -x, 0.0],
        [0.5 - x, 0.5 + x, 0.5], [0.5 + x, 0.5 - x, 0.5],
    ]
    species = [element, element, "O", "O", "O", "O"]
    return Structure(lat, species, coords)


def build_zro2_cubic() -> Structure:
    """立方萤石 ZrO2（与 UO2 同构，a=5.09 Å）."""
    a = 5.09
    species = ["Zr"] * 4 + ["O"] * 8
    coords = [
        [0.0, 0.0, 0.0], [0.0, 0.5, 0.5], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0],
        [0.25, 0.25, 0.25], [0.25, 0.75, 0.75], [0.75, 0.25, 0.75], [0.75, 0.75, 0.25],
        [0.25, 0.25, 0.75], [0.25, 0.75, 0.25], [0.75, 0.25, 0.25], [0.75, 0.75, 0.75],
    ]
    return Structure(Lattice.cubic(a), species, coords)


def build_o2_molecule() -> Structure:
    """O2 分子在 20 Å 盒子（三重态计算用）."""
    lat = Lattice.cubic(20.0)
    coords = [[0.0, 0.0, 0.0], [0.0, 0.0, 1.24]]
    return Structure(lat, ["O", "O"], coords)


def write_bulk_inputs(struct: Structure, out_dir: str, system: str,
                      kpoints: tuple, magmoms=None):
    os.makedirs(out_dir, exist_ok=True)
    species_order = []
    for s in struct:
        el = str(s.specie)
        if el not in species_order:
            species_order.append(el)
    write_structure(struct, os.path.join(out_dir, "POSCAR"),
                    species_order=species_order)
    write_incar(out_dir, system, calc_type="bulk", n_ions=len(struct),
                magmoms=magmoms, species_order=species_order)
    write_kpoints(out_dir, kpoints)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--poscar-only", action="store_true", help="只生成 POSCAR")
    args = parser.parse_args()

    base = os.path.join(PROJECT_ROOT, "00_bulk")

    # 1. UO2 体相
    uo2 = build_uo2_bulk_pymatgen(5.47)
    write_bulk_inputs(uo2, os.path.join(base, "UO2_bulk"), "UO2_bulk",
                      kpoints=(8, 8, 8), magmoms=[2.0, 2.0, -2.0, -2.0] + [0.0] * 8)
    print("[OK] UO2_bulk  (a=5.47 A, AFM, DFT+U)")

    # 2. MO2 体相
    for el in ["Mo", "Nb", "Zr", "Ti"]:
        if el == "Zr":
            mo2 = build_zro2_cubic()
            mesh = (8, 8, 8)
        else:
            mo2 = build_mo2_bulk(el)
            mesh = (6, 6, 8)
        out = os.path.join(base, f"{el}O2_bulk")
        write_bulk_inputs(mo2, out, f"{el}O2_bulk", kpoints=mesh)
        print(f"[OK] {el}O2_bulk  (reference oxide)")

    # 3. O2 分子
    o2 = build_o2_molecule()
    write_bulk_inputs(o2, os.path.join(base, "O2_molecule"), "O2_molecule",
                      kpoints=(1, 1, 1), magmoms=[1.0, 1.0])
    print("[OK] O2_molecule  (triplet, 20 A box)")

    print("\n体相结构生成完成。")
    print("注意：MO2 参考相若需更精确结构，请用 Materials Project 下载 POSCAR 替换。")


if __name__ == "__main__":
    main()
