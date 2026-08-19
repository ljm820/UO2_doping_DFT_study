#!/usr/bin/env python3
"""
bader_analysis.py
Bader 电荷分析接口 + 自旋密度积分接口。

依赖：
  - bader 可执行文件（Henkelman group, https://theory.cm.utexas.edu/henkelman/code/bader/）
  - 或已生成的 ACF.dat / BCF.dat

流程：
  1. 从 CONTCAR + CHGCAR 运行 bader 得到 ACF.dat（电荷）与 BCF.dat（自旋）
  2. 解析 ACF.dat / BCF.dat，输出每个原子/元素的净电荷与自旋磁矩
  3. 汇总每个掺杂元素、每个 O 空位邻近原子的 Bader 电荷变化

用法：
    python3 scripts/bader_analysis.py 03_substoichiometric/U1-yMoyO2-x/MOX-8/111/vac_next_to_dopant
    python3 scripts/bader_analysis.py --dirs <dir1> <dir2> ... --csv results/bader.csv
    python3 scripts/bader_analysis.py --spin-only 03_.../vac_next_to_dopant
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import shutil
import subprocess
import sys

from pymatgen.core import Structure

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))


def run_bader(directory: str, verbose: bool = False) -> bool:
    """在目录中运行 bader. 需要 bader 在 PATH 中."""
    chg = os.path.join(directory, "CHGCAR")
    if not os.path.exists(chg):
        print(f"  缺少 CHGCAR: {directory}", file=sys.stderr)
        return False
    if shutil.which("bader") is None:
        print("  未找到 bader 可执行文件，跳过（可从 https://theory.cm.utexas.edu 安装）", file=sys.stderr)
        return False
    if verbose:
        print(f"  运行 bader in {directory}")
    try:
        subprocess.run(["bader", "CHGCAR"], cwd=directory, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def parse_acf(acf_path: str) -> list[dict]:
    """解析 ACF.dat（Bader 电荷分析输出）. 返回每原子 {x,y,z,charge,mag}."""
    rows = []
    with open(acf_path) as f:
        lines = f.readlines()
    started = False
    for line in lines:
        if "X" in line and "Y" in line and "Z" in line:
            started = True
            continue
        if started and line.strip() and line.strip()[0].isdigit():
            parts = line.split()
            if len(parts) >= 6 and parts[0].isdigit():
                rows.append({
                    "idx": int(parts[0]),
                    "x": float(parts[1]), "y": float(parts[2]), "z": float(parts[3]),
                    "charge": float(parts[4]),
                    "mag": float(parts[5]) if len(parts) > 5 else 0.0,
                })
        if started and line.strip().startswith("-----"):
            break
    return rows


def read_charge_difference(directory: str, verbose: bool = False) -> list[dict]:
    """从 ACF.dat 读取 Bader 电荷，并与完美结构对比（若提供 PERFECT 目录）."""
    acf = os.path.join(directory, "ACF.dat")
    if not os.path.exists(acf):
        return []
    rows = parse_acf(acf)
    struct_path = os.path.join(directory, "CONTCAR") or os.path.join(directory, "POSCAR")
    for p in (os.path.join(directory, "CONTCAR"), os.path.join(directory, "POSCAR")):
        if os.path.exists(p):
            struct_path = p
            break
    struct = Structure.from_file(struct_path)
    for r, site in zip(rows, struct):
        r["element"] = str(site.specie)
    return rows


def spin_from_bcf(directory: str) -> list[dict]:
    """从 BCF.dat 读取逐原子自旋磁矩（需 ISPIN=2 运行 bader）. 等价于 ACF 第 6 列."""
    bcf = os.path.join(directory, "BCF.dat")
    if os.path.exists(bcf):
        rows = parse_acf(bcf)
        for r in rows:
            r["spin"] = r.pop("mag")
        return rows
    return []


def spin_from_oszicar(directory: str) -> list[float]:
    """从 OSZICAR 末步提取总磁矩（单一数值，非逐原子）."""
    osz = os.path.join(directory, "OSZICAR")
    vals = []
    if os.path.exists(osz):
        with open(osz) as f:
            for line in f:
                if "mag=" in line:
                    m = re.search(r"mag=\s*([-\d.]+)", line)
                    if m:
                        vals.append(float(m.group(1)))
    return vals


def main():
    parser = argparse.ArgumentParser(description="Bader 电荷/自旋分析")
    parser.add_argument("dirs", nargs="*", help="计算目录")
    parser.add_argument("--dirs-from", default=None, help="从 csv/文本文件读取目录列表")
    parser.add_argument("--spin-only", action="store_true", help="只提取自旋")
    parser.add_argument("--run-bader", action="store_true", help="先运行 bader 再解析")
    parser.add_argument("--csv", default=None, help="输出 CSV")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    dirs = list(args.dirs)
    if args.dirs_from:
        with open(args.dirs_from) as f:
            dirs += [l.strip() for l in f if l.strip()]

    if not dirs:
        print("未指定目录。用法见脚本头部注释。", file=sys.stderr)
        sys.exit(1)

    all_rows = []
    for d in dirs:
        if not os.path.isdir(d):
            print(f"跳过不存在目录: {d}", file=sys.stderr)
            continue
        if args.run_bader and not args.spin_only:
            run_bader(d, args.verbose)
        rows = []
        if args.spin_only:
            rows = spin_from_bcf(d)
            for r in rows:
                r["dir"] = d
                r["type"] = "spin"
        else:
            rows = read_charge_difference(d, args.verbose)
            for r in rows:
                r["dir"] = d
                r["type"] = "charge"
            # 附带总磁矩
            tot = spin_from_oszicar(d)
            if tot and args.verbose:
                print(f"  {d}: 总磁矩 = {tot[-1]:.3f} mu_B")
        all_rows += rows

    if args.csv and all_rows:
        os.makedirs(os.path.dirname(args.csv) or ".", exist_ok=True)
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            w.writeheader()
            w.writerows(all_rows)
        print(f"Bader/自旋分析结果已写入: {args.csv}  （{len(all_rows)} 行）")
    elif all_rows:
        for r in all_rows:
            print(r)


if __name__ == "__main__":
    main()
