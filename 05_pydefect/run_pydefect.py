#!/usr/bin/env python3
"""
run_pydefect.py
pydefect 缺陷热力学分析驱动脚本

流程（pydefect 项目方法）：
  1. 用 pymatgen 生成完美超胞 (2x2x2, 96 原子)
  2. 用 pydefect/pymatgen 生成缺陷结构（Va_O, Oi, M_U），多电荷态
  3. 组织 VASP 计算目录：perfect/ 与 Va_O1_+2/ 等
  4. 解析计算结果（pydefect_vasp cr / dei）
  5. 计算缺陷形成能随化学势/费米能级的变化（缺陷形成能图）

用法：
    python 05_pydefect/run_pydefect.py setup            # 生成所有结构
    python 05_pydefect/run_pydefect.py setup --defect Va_O1
    python 05_pydefect/run_pydefect.py parse            # 解析 VASP 结果
    python 05_pydefect/run_pydefect.py formation-energy # 形成能图
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import yaml

from pymatgen.core import Structure

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from structure_utils import build_uo2_bulk_pymatgen, write_structure

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYDEFECT_DIR = os.path.join(PROJECT_ROOT, "05_pydefect")
PERFECT_DIR = os.path.join(PYDEFECT_DIR, "perfect")

DOPANTS = {"Mo": 4, "Nb": 5, "Zr": 4, "Ti": 4}


def load_config() -> dict:
    cfg_path = os.path.join(PYDEFECT_DIR, "pydefect_config.yaml")
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def build_perfect_supercell(config: dict) -> Structure:
    """构建 2x2x2 UO2 超胞（96 原子），保存 POSCAR。"""
    bulk = build_uo2_bulk_pymatgen(5.47)
    supercell = bulk * [2, 2, 2]
    os.makedirs(PERFECT_DIR, exist_ok=True)
    write_structure(supercell, os.path.join(PERFECT_DIR, "POSCAR"),
                    species_order=["U", "O"])
    return supercell


def generate_vacancy_structure(perfect: Structure, oxi_states: dict) -> Structure:
    """移除一个 O 原子生成 O 空位结构."""
    o_indices = [i for i, s in enumerate(perfect) if str(s.specie) == "O"]
    s = perfect.copy()
    s.remove_sites([o_indices[0]])
    return s


def generate_interstitial_structure(perfect: Structure) -> Structure:
    """在八面体间隙位（1/2,1/2,1/2）添加间隙氧."""
    s = perfect.copy()
    s.append("O", [0.5, 0.5, 0.5])
    return s


def generate_substitution_structure(perfect: Structure, element: str,
                                    oxi_states: dict) -> Structure:
    """替换一个 U 为掺杂元素."""
    u_indices = [i for i, s in enumerate(perfect) if str(s.specie) == "U"]
    s = perfect.copy()
    s.replace(u_indices[0], element)
    return s


def setup(config: dict, defect_filter: str | None = None):
    """生成完美与缺陷结构目录。"""
    perfect = build_perfect_supercell(config)
    print(f"[OK] perfect supercell: {perfect.formula} ({len(perfect)} 原子)")

    oxi = config["oxi_states"]
    defect_specs = config["defects"]
    created = 0
    for name, charges in defect_specs.items():
        if defect_filter and defect_filter not in name:
            continue
        base = name.split("_")[0]
        if base == "Va":
            struct = generate_vacancy_structure(perfect, oxi)
        elif base == "Oi":
            struct = generate_interstitial_structure(perfect)
        elif base in DOPANTS:
            struct = generate_substitution_structure(perfect, base, oxi)
        else:
            continue
        for q in charges:
            d = os.path.join(PYDEFECT_DIR, f"{name}_{q:+d}".replace("+", "").replace("-0", "0"))
            os.makedirs(d, exist_ok=True)
            sp = ["U"] + (["Mo"] if base == "Mo" else []) + ["O"]
            write_structure(struct, os.path.join(d, "POSCAR"),
                            species_order=["U", base, "O"] if base in DOPANTS else ["U", "O"])
            _write_vasp_inputs(d, struct, name, q, config)
            created += 1
            print(f"[OK] {name} charge={q} -> {d}")
    print(f"共生成 {created} 个缺陷目录。运行 VASP 后执行 parse。")


def _write_vasp_inputs(out_dir: str, struct: Structure, name: str,
                       charge: int, config: dict):
    vp = config["vasp_params"]
    n = len(struct)
    mag = [2.0 if str(s.specie) == "U" and i < n // 2 else
           (-2.0 if str(s.specie) == "U" else 0.0) for i, s in enumerate(struct)]
    n_u = sum(1 for s in struct if str(s.specie) == "U")
    mags = []
    half = n_u // 2
    idx = 0
    for s in struct:
        if str(s.specie) == "U":
            mags.append(2.0 if idx < half else -2.0)
            idx += 1
        else:
            mags.append(0.0)
    incar = f"""SYSTEM  = {name}_q{charge}
PREC    = Accurate
ENCUT   = {vp['encut']}
EDIFF   = {vp['ediff']}
EDIFFG  = {vp['ediffg']}
ISMEAR  = {vp['ismea']}
SIGMA   = {vp['sigma']}
LREAL   = .FALSE.
LDAU    = .TRUE.
LDAUTYPE= 2
LDAUL   = 3 -1
LDAUU   = {vp['ldauu']} 0.0
LDAUJ   = 0.5 0.0
LMAXMIX = 4
ISPIN   = 2
MAGMOM  = {' '.join(f'{v:.2f}' for v in mags)}
NELECT  = {_nelect(struct) - charge}
NSW     = 100
IBRION  = 2
ISIF    = 2
NCORE   = 8
LWAVE   = .FALSE.
LCHARG  = .TRUE.
LORBIT  = 11
"""
    with open(os.path.join(out_dir, "INCAR"), "w") as f:
        f.write(incar)
    k = vp["kpoints"]
    kpt = f"""Automatic mesh
0
Monkhorst-Pack
{k[0]}  {k[1]}  {k[2]}
0  0  0
"""
    with open(os.path.join(out_dir, "KPOINTS"), "w") as f:
        f.write(kpt)


def _nelect(struct: Structure) -> int:
    """估算价电子数（供 NELECT 参考，按各元素价电子近似）。"""
    valence = {"U": 14, "O": 6, "Mo": 12, "Nb": 11, "Zr": 10, "Ti": 10}
    return sum(valence.get(str(s.specie), 6) for s in struct)


def parse(config: dict):
    """解析所有 VASP 结果（调用 pydefect_vasp calc_results + defect_energy_infos）。"""
    dirs = [os.path.join(PYDEFECT_DIR, d)
            for d in sorted(os.listdir(PYDEFECT_DIR))
            if os.path.isdir(os.path.join(PYDEFECT_DIR, d))
            and d != "perfect" and "POSCAR" in os.listdir(os.path.join(PYDEFECT_DIR, d))]
    if not dirs:
        print("没有找到缺陷目录，请先运行 setup。")
        return
    print("运行 pydefect_vasp calc_results ...")
    subprocess.run(["pydefect_vasp", "calc_results", "-d"] + dirs + [PERFECT_DIR],
                   cwd=PYDEFECT_DIR, check=False)


def formation_energy(config: dict, fermi: float = 0.0, mu_O_shift: float = 0.0):
    """
    计算缺陷形成能（简化实现，供分析参考）。

    E_f[V_O^q] = E[V_O^q] - E[perfect] + mu_O + q*(E_VBM + eF)
    """
    # 从 OUTCAR 读取能量
    def get_energy(d):
        outcar = os.path.join(d, "OUTCAR")
        if not os.path.exists(outcar):
            return None
        vals = []
        with open(outcar) as f:
            for line in f:
                if "free  energy" in line:
                    parts = line.split("=")
                    if len(parts) > 1:
                        vals.append(float(parts[1].split()[0]))
        return vals[-1] if vals else None

    e_perfect = get_energy(PERFECT_DIR)
    if e_perfect is None:
        print("缺少 perfect/OUTCAR，先运行 VASP。")
        return
    print(f"E_perfect = {e_perfect:.4f} eV")
    print(f"{'缺陷':<12} {'电荷':<5} {'E_defect':>12} {'E_f(eV)':>12}")
    for d in sorted(os.listdir(PYDEFECT_DIR)):
        path = os.path.join(PYDEFECT_DIR, d)
        if not os.path.isdir(path) or d == "perfect":
            continue
        e_def = get_energy(path)
        if e_def is None:
            continue
        q = 0
        name = d
        if "_" in d:
            qstr = d.rsplit("_", 1)[1]
            try:
                q = int(qstr)
            except ValueError:
                q = 0
        # 简化：O 空位形成能 mu_O = E_O2/2（富氧极限）
        ef = e_def - e_perfect + mu_O_shift + q * fermi
        print(f"{d:<12} {q:<5} {e_def:>12.4f} {ef:>12.4f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["setup", "parse", "formation-energy"])
    parser.add_argument("--defect", default=None, help="只处理指定缺陷名")
    args = parser.parse_args()

    config = load_config()
    if args.mode == "setup":
        setup(config, args.defect)
    elif args.mode == "parse":
        parse(config)
    elif args.mode == "formation-energy":
        formation_energy(config)


if __name__ == "__main__":
    main()
