#!/usr/bin/env python3
"""
analyze_energies.py
VASP 结果后处理：计算表面能 / 替换能 / O 空位形成能 / 间隙氧形成能。

公式（对应论文 eq.1-3，两侧对称操作取 1/2 因子）：
    E_sur = (E_slab - N_fu * E_bulk_UO2) / 2                (N_fu = 公式单元数)
    E_rep = (E_MOX - n_U*E_UO2_fu - n_M*E_MO2_fu) / 2
    E_for(VO)  = (E_sub + E_O2 - E_sto) / 2                  (两个对称空位)
    E_for(Oi)  = (E_hyper - E_sto - E_O2) / 2                (两个对称间隙氧)

用法：
    python3 scripts/analyze_energies.py --out results/energies.csv
    python3 scripts/analyze_energies.py --bulk-only
    python3 scripts/analyze_energies.py --verbose
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from pymatgen.core import Structure

from vasp_utils import read_energy

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BULK_DIR = os.path.join(PROJECT_ROOT, "00_bulk")
SURF_DIR = os.path.join(PROJECT_ROOT, "01_surface_generation")
STO_DIR = os.path.join(PROJECT_ROOT, "02_stoichiometric_MOX")
SUB_DIR = os.path.join(PROJECT_ROOT, "03_substoichiometric")
HYP_DIR = os.path.join(PROJECT_ROOT, "04_hyperstoichiometric")

DOPANT_OXIDE = {"Mo": "MoO2", "Nb": "NbO2", "Zr": "ZrO2", "Ti": "TiO2"}


def get_energy(dirpath: str) -> Optional[float]:
    """读取目录能量：优先 CONTCAR 目录的 OUTCAR，否则 OSZICAR 末行."""
    outcar = os.path.join(dirpath, "OUTCAR")
    e = read_energy(outcar)
    if e is not None:
        return e
    osz = os.path.join(dirpath, "OSZICAR")
    if os.path.exists(osz):
        try:
            with open(osz) as f:
                for line in f:
                    if "F=" in line or "E0=" in line:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if p in ("F=", "E0="):
                                return float(parts[i + 1])
        except Exception:
            pass
    return None


def read_structure(dirpath: str) -> Optional[Structure]:
    for name in ("CONTCAR", "POSCAR"):
        p = os.path.join(dirpath, name)
        if os.path.exists(p):
            try:
                return Structure.from_file(p)
            except Exception:
                continue
    return None


def formula_units(structure: Structure) -> int:
    """按 UO2 公式单元数估算（阳离子总数）."""
    n_cation = sum(1 for s in structure if str(s.specie) != "O")
    return max(n_cation, 1)


def energy_of(stage_dir: str, name: str) -> Optional[float]:
    d = os.path.join(stage_dir, name)
    return get_energy(d)


class Analyzer:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.rows: list[dict] = []

    def log(self, msg):
        if self.verbose:
            print(msg)

    def run(self):
        # ---- Stage 0: 体相参考能量 ----
        e_uo2 = energy_of(BULK_DIR, "UO2_bulk")
        e_o2 = energy_of(BULK_DIR, "O2_molecule")
        self.log(f"[bulk] E_UO2 = {e_uo2}, E_O2 = {e_o2}")
        if e_uo2 is None or e_o2 is None:
            print("警告: 缺少 UO2_bulk 或 O2_molecule 的 OUTCAR，无法计算能量指标", file=sys.stderr)
            return
        uo2_struct = read_structure(os.path.join(BULK_DIR, "UO2_bulk"))
        n_fu_uo2 = formula_units(uo2_struct) if uo2_struct else 4
        e_uo2_fu = e_uo2 / n_fu_uo2

        mo2_fu: dict[str, tuple] = {}
        for m, ox in DOPANT_OXIDE.items():
            d = os.path.join(BULK_DIR, f"{ox}_bulk")
            e = get_energy(d)
            st = read_structure(d)
            n_fu = formula_units(st) if st else 2
            mo2_fu[m] = (e, e / n_fu if e else None)
            self.log(f"[bulk] E_{ox} = {e}, per_fu = {mo2_fu[m][1]}")

        # ---- Stage 1: 表面能 ----
        for surf in ["UO2_111", "UO2_110", "UO2_100"]:
            e_slab = energy_of(SURF_DIR, surf)
            st = read_structure(os.path.join(SURF_DIR, surf))
            if e_slab is None or st is None:
                self.log(f"[surf] {surf}: 缺 OUTCAR")
                continue
            n_fu = formula_units(st)
            area = st.lattice.a * st.lattice.b * abs(st.lattice.c * st.lattice.cos_gamma) if False else None
            # 面积 = |a x b|（真空沿 c）
            import numpy as np
            a = np.array(st.lattice.matrix[0])
            b = np.array(st.lattice.matrix[1])
            area = np.linalg.norm(np.cross(a, b)) * 1e-20  # m^2
            e_sur = (e_slab - n_fu * e_uo2_fu) / 2  # eV
            e_sur_jm2 = e_sur / area / 2  # 每个表面（上+下）/2
            e_sur_jm2 = e_sur * 1.602176634e-19 / area / 2  # eV -> J 再除两面
            self.rows.append({
                "stage": "1_surface", "system": surf, "face": surf[-3:],
                "E_tot_eV": e_slab, "N_formula": n_fu,
                "quantity": "E_sur", "value_eV": e_sur,
                "value_per_area": f"{e_sur_jm2:.4f} J/m2",
                "ref": "0.51/0.91/1.34",
            })
            self.log(f"[surf] {surf}: E_sur = {e_sur:.3f} eV = {e_sur_jm2:.3f} J/m2")

        # ---- Stage 2: 替换能 ----
        if os.path.isdir(STO_DIR):
            for elem in sorted(os.listdir(STO_DIR)):
                elem_dir = os.path.join(STO_DIR, elem)
                if not os.path.isdir(elem_dir):
                    continue
                for conc in sorted(os.listdir(elem_dir)):
                    conc_dir = os.path.join(elem_dir, conc)
                    if not os.path.isdir(conc_dir):
                        continue
                    for face in sorted(os.listdir(conc_dir)):
                        d = os.path.join(conc_dir, face)
                        if not os.path.isdir(d):
                            continue
                        self._analyze_mox(elem, conc, face, d, mo2_fu, e_uo2_fu)

        # ---- Stage 3/4: 空位与间隙 ----
        self._analyze_substoich("UO2-x", e_uo2_fu, e_o2)
        self._analyze_substoich_mox(mo2_fu, e_uo2_fu, e_o2)
        self._analyze_hyper("UO2+x", e_uo2_fu, e_o2)
        self._analyze_hyper_mox(mo2_fu, e_uo2_fu, e_o2)

    # ---------- Stage 2 ----------
    def _analyze_mox(self, elem, conc, face, d, mo2_fu, e_uo2_fu):
        e_mox = get_energy(d)
        st = read_structure(d)
        if e_mox is None or st is None:
            self.log(f"[mox] {elem}/{conc}/{face}: 缺 OUTCAR")
            return
        n_u = sum(1 for s in st if str(s.specie) == "U")
        n_m = sum(1 for s in st if str(s.specie) == elem)
        e_mo2, e_mo2_fu = mo2_fu.get(elem, (None, None))
        if e_mo2_fu is None:
            return
        e_rep = (e_mox - n_u * e_uo2_fu - n_m * e_mo2_fu) / 2
        y = n_m / max(n_u + n_m, 1)
        self.rows.append({
            "stage": "2_mox", "system": f"{elem}/{conc}/{face}",
            "face": face, "E_tot_eV": e_mox, "N_formula": n_u + n_m,
            "quantity": "E_rep", "value_eV": e_rep, "value_per_area": f"y={y:.3f}",
            "ref": "趋势单调",
        })
        self.log(f"[mox] {elem}/{conc}/{face}: E_rep = {e_rep:.3f} eV (y={y:.3f})")

    # ---------- Stage 3 ----------
    def _analyze_substoich(self, system, e_uo2_fu, e_o2):
        base = os.path.join(SUB_DIR, system)
        if not os.path.isdir(base):
            return
        for face in sorted(os.listdir(base)):
            d = os.path.join(base, face)
            if not os.path.isdir(d):
                continue
            e_sub = get_energy(d)
            st = read_structure(d)
            if e_sub is None or st is None:
                continue
            n_fu = formula_units(st)
            e_sto = n_fu * e_uo2_fu
            e_for = (e_sub + e_o2 - e_sto) / 2
            self.rows.append({
                "stage": "3_vacancy", "system": f"UO2-x/{face}", "face": face,
                "E_tot_eV": e_sub, "N_formula": n_fu,
                "quantity": "E_for(VO)", "value_eV": e_for,
                "value_per_area": "", "ref": "5.81/5.47/4.98",
            })
            self.log(f"[sub] {system}/{face}: E_for(VO) = {e_for:.3f} eV")

    def _analyze_substoich_mox(self, mo2_fu, e_uo2_fu, e_o2):
        if not os.path.isdir(SUB_DIR):
            return
        for elem in sorted(os.listdir(SUB_DIR)):
            if not elem.startswith("U1-yM"):
                continue
            elem_dir = os.path.join(SUB_DIR, elem)
            for conc in sorted(os.listdir(elem_dir)):
                conc_dir = os.path.join(elem_dir, conc)
                for face in sorted(os.listdir(conc_dir)):
                    face_dir = os.path.join(conc_dir, face)
                    if not os.path.isdir(face_dir):
                        continue
                    for variant in sorted(os.listdir(face_dir)):
                        d = os.path.join(face_dir, variant)
                        if not os.path.isdir(d):
                            continue
                        e_sub = get_energy(d)
                        st = read_structure(d)
                        if e_sub is None or st is None:
                            continue
                        n_u = sum(1 for s in st if str(s.specie) == "U")
                        n_m = sum(1 for s in st if str(s.specie) != "U" and str(s.specie) != "O")
                        e_sto = n_u * e_uo2_fu
                        if n_m:
                            _, e_mo2_fu = mo2_fu.get([k for k in mo2_fu if k in elem][0], (None, None))
                            if e_mo2_fu:
                                e_sto = n_u * e_uo2_fu + n_m * e_mo2_fu
                        e_for = (e_sub + e_o2 - e_sto) / 2
                        self.rows.append({
                            "stage": "3_vacancy", "system": f"{elem}/{conc}/{face}/{variant}",
                            "face": face, "E_tot_eV": e_sub, "N_formula": n_u + n_m,
                            "quantity": "E_for(VO)", "value_eV": e_for,
                            "value_per_area": variant, "ref": "",
                        })
                        self.log(f"[submox] {elem}/{conc}/{face}/{variant}: E_for(VO) = {e_for:.3f} eV")

    # ---------- Stage 4 ----------
    def _analyze_hyper(self, system, e_uo2_fu, e_o2):
        base = os.path.join(HYP_DIR, system)
        if not os.path.isdir(base):
            return
        for face in sorted(os.listdir(base)):
            d = os.path.join(base, face)
            if not os.path.isdir(d):
                continue
            e_hyper = get_energy(d)
            st = read_structure(d)
            if e_hyper is None or st is None:
                continue
            n_fu = formula_units(st)
            e_sto = n_fu * e_uo2_fu
            e_for = (e_hyper - e_sto - e_o2) / 2
            self.rows.append({
                "stage": "4_hyper", "system": f"{system}/{face}", "face": face,
                "E_tot_eV": e_hyper, "N_formula": n_fu,
                "quantity": "E_for(Oi)", "value_eV": e_for,
                "value_per_area": "", "ref": "",
            })
            self.log(f"[hyper] {system}/{face}: E_for(Oi) = {e_for:.3f} eV")

    def _analyze_hyper_mox(self, mo2_fu, e_uo2_fu, e_o2):
        if not os.path.isdir(HYP_DIR):
            return
        for elem in sorted(os.listdir(HYP_DIR)):
            if not elem.startswith("U1-yM"):
                continue
            elem_dir = os.path.join(HYP_DIR, elem)
            for conc in sorted(os.listdir(elem_dir)):
                conc_dir = os.path.join(elem_dir, conc)
                for face in sorted(os.listdir(conc_dir)):
                    face_dir = os.path.join(conc_dir, face)
                    if not os.path.isdir(face_dir):
                        continue
                    for variant in sorted(os.listdir(face_dir)):
                        d = os.path.join(face_dir, variant)
                        if not os.path.isdir(d):
                            continue
                        e_hyper = get_energy(d)
                        st = read_structure(d)
                        if e_hyper is None or st is None:
                            continue
                        n_u = sum(1 for s in st if str(s.specie) == "U")
                        n_m = sum(1 for s in st if str(s.specie) != "U" and str(s.specie) != "O")
                        e_sto = n_u * e_uo2_fu
                        if n_m:
                            _, e_mo2_fu = mo2_fu.get([k for k in mo2_fu if k in elem][0], (None, None))
                            if e_mo2_fu:
                                e_sto = n_u * e_uo2_fu + n_m * e_mo2_fu
                        e_for = (e_hyper - e_sto - e_o2) / 2
                        self.rows.append({
                            "stage": "4_hyper", "system": f"{elem}/{conc}/{face}/{variant}",
                            "face": face, "E_tot_eV": e_hyper, "N_formula": n_u + n_m,
                            "quantity": "E_for(Oi)", "value_eV": e_for,
                            "value_per_area": variant, "ref": "",
                        })
                        self.log(f"[hypermox] {elem}/{conc}/{face}/{variant}: E_for(Oi) = {e_for:.3f} eV")


def main():
    parser = argparse.ArgumentParser(description="计算表面能/替换能/缺陷形成能")
    parser.add_argument("--out", default=os.path.join(PROJECT_ROOT, "results", "energies.csv"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    a = Analyzer(verbose=args.verbose)
    a.run()

    if not a.rows:
        print("未收集到任何能量数据（需先运行 VASP 生成 OUTCAR）。")
        return

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(a.rows[0].keys()))
        w.writeheader()
        w.writerows(a.rows)
    print(f"\n能量汇总已写入: {args.out}  （{len(a.rows)} 条记录）")


if __name__ == "__main__":
    main()
