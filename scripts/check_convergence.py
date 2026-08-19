#!/usr/bin/env python3
"""
check_convergence.py
批量检查 VASP 计算目录的收敛状态。

支持：
  - 目录递归扫描（寻找 OUTCAR / OSZICAR / INCAR）
  - 判定状态：CONVERGED / RUNNING / FAILED / NOT_STARTED / NO_OUTCAR
  - 读取末步自由能、最大力、SCF 步数、离子步数与耗时
  - 输出 CSV 汇总 + 终端表格，供 workflow 分支判断使用

用法：
    python3 scripts/check_convergence.py [root_dir] [--csv results/conv_summary.csv]
    python3 scripts/check_convergence.py --strict   # 离子步未收敛也算 FAILED
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from vasp_utils import read_energy, read_max_force, is_converged, is_failed

STATUS_ICON = {
    "CONVERGED": "  OK ",
    "RUNNING":   " RUN ",
    "FAILED":    "FAIL ",
    "NOT_STARTED": "----",
    "NO_OUTCAR": "NO-O ",
}


@dataclass
class CalcStatus:
    name: str = ""
    status: str = "NO_OUTCAR"
    energy: Optional[float] = None
    max_force: Optional[float] = None
    n_scf: int = 0
    n_ionic: int = 0
    wall_time: str = ""
    n_atoms: int = 0
    notes: str = ""
    outcar: str = ""


def _read_oszicar_meta(outcar_dir: str) -> tuple:
    """从 OSZICAR 读取 (scf_steps, ionic_steps)."""
    osz = os.path.join(outcar_dir, "OSZICAR")
    n_scf = n_ionic = 0
    if os.path.exists(osz):
        try:
            with open(osz, errors="ignore") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 3 and parts[0].isdigit() and parts[2] in ("F=", "E0="):
                        n_ionic = int(parts[0])
                        n_scf += 1
        except Exception:
            pass
    return n_scf, n_ionic


def _read_wall_time(outcar: str) -> str:
    """从 OUTCAR 末行读取耗时 (s)."""
    if not os.path.exists(outcar):
        return ""
    try:
        with open(outcar, errors="ignore") as f:
            lines = f.readlines()
        for line in reversed(lines[-200:]):
            if "LOOP+" in line:
                parts = line.split()
                return parts[-1] if parts else ""
    except Exception:
        pass
    return ""


def _read_natoms(outcar: str) -> int:
    if not os.path.exists(outcar):
        return 0
    try:
        with open(outcar, errors="ignore") as f:
            for line in f:
                m = re.search(r"NIONS\s*=\s*(\d+)", line)
                if m:
                    return int(m.group(1))
    except Exception:
        pass
    return 0


def scan_dir(root: str, strict: bool = False) -> List[CalcStatus]:
    results: List[CalcStatus] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # 跳过隐藏目录
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        if "INCAR" not in filenames:
            continue
        name = os.path.relpath(dirpath, root)
        c = CalcStatus(name=name)
        has_outcar = "OUTCAR" in filenames
        has_oszicar = "OSZICAR" in filenames
        incar_path = os.path.join(dirpath, "INCAR")

        if not has_outcar and not has_oszicar:
            c.status = "NOT_STARTED"
            c.notes = "无 OUTCAR/OSZICAR，VASP 尚未启动"
            results.append(c)
            continue

        if not has_outcar:
            c.status = "RUNNING"
            c.notes = "有 OSZICAR 无 OUTCAR（首步进行中）"
            results.append(c)
            continue

        outcar = os.path.join(dirpath, "OUTCAR")
        c.outcar = outcar
        c.n_atoms = _read_natoms(outcar)
        c.energy = read_energy(outcar)
        c.max_force = read_max_force(outcar)
        c.wall_time = _read_wall_time(outcar)
        n_scf, n_ionic = _read_oszicar_meta(dirpath)
        c.n_scf, c.n_ionic = n_scf, n_ionic

        failed = is_failed(outcar)
        if failed:
            c.status = "FAILED"
            c.notes = "OUTCAR 含 error/aborting"
        elif is_converged(outcar) and c.energy is not None:
            # 电子步已收敛；离子步是否收敛（NSW=0 或达到 EDIFFG）
            if strict and c.max_force is not None:
                # 判断是否达到 EDIFFG 阈值（读 INCAR 近似）
                ediffg = 0.02
                try:
                    with open(incar_path) as f:
                        for line in f:
                            if line.strip().startswith("EDIFFG"):
                                ediffg = abs(float(line.split("=")[-1].strip()))
                except Exception:
                    pass
                if c.max_force > ediffg:
                    c.status = "RUNNING"
                    c.notes = f"电子步收敛但力未收敛 ({c.max_force:.3f} > {ediffg})"
                    results.append(c)
                    continue
            c.status = "CONVERGED"
            c.notes = f"末步能量 {c.energy:.4f} eV"
        elif c.energy is not None:
            c.status = "RUNNING"
            c.notes = f"已跑 {n_ionic} 离子步，未达精度"
        else:
            c.status = "FAILED"
            c.notes = "OUTCAR 无 free energy（异常退出）"
        results.append(c)
    return sorted(results, key=lambda r: (r.status, r.name))


def _fmt(v, width=14, nd=4, placeholder="-"):
    if v is None:
        return f"{placeholder:>{width}}"
    return f"{v:>{width}.{nd}f}"


def print_table(results: List[CalcStatus]) -> None:
    print(f"\n{'状态':<8} {'目录':<44} {'能量(eV)':>14} {'|F|max':>10} {'SCF':>5} {'ION':>5} {'耗时':>10}")
    print("-" * 100)
    for c in results:
        print(f"{STATUS_ICON.get(c.status,'    ')}  {c.name:<44} "
              f"{_fmt(c.energy)} {_fmt(c.max_force, 10)} "
              f"{c.n_scf:>5} {c.n_ionic:>5} {c.wall_time:>10}")


def write_csv(results: List[CalcStatus], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "status", "energy_eV", "max_force", "scf_steps",
                    "ionic_steps", "wall_time_s", "n_atoms", "notes"])
        for c in results:
            w.writerow([c.name, c.status, c.energy, c.max_force, c.n_scf,
                        c.n_ionic, c.wall_time, c.n_atoms, c.notes])
    print(f"\nCSV 汇总已写入: {path}")


def main():
    parser = argparse.ArgumentParser(description="批量检查 VASP 收敛状态")
    parser.add_argument("root", nargs="?", default=".",
                        help="扫描根目录（默认当前目录）")
    parser.add_argument("--csv", default=None, help="输出 CSV 路径")
    parser.add_argument("--strict", action="store_true",
                        help="严格模式：力未达 EDIFFG 视为 RUNNING")
    args = parser.parse_args()

    results = scan_dir(args.root, strict=args.strict)
    print_table(results)
    # 汇总统计
    from collections import Counter
    cnt = Counter(r.status for r in results)
    print(f"\n统计: {dict(cnt)}  共 {len(results)} 个计算目录")
    if args.csv:
        write_csv(results, args.csv)


if __name__ == "__main__":
    main()
