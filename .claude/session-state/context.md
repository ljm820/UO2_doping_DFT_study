---
type: context
session: "2026-08-18 — 2026-08-19"
status: "v2.0 — 研究框架完整交付（脚本/文档/工作流/SSHP 就绪，GitHub 仓库已建），待实机 VASP 计算"
---

## 1. 项目/任务全景

复现 Chen & Kaltsoyannis, Appl. Surf. Sci. 537 (2021) 147972 方法，构建 UO2 掺杂体系（Mo/Nb/Zr/Ti）表面 DFT+U 完整研究框架：

- UO2 萤石结构；覆盖 UO2-x（O:M=1.92）、UO2+x（间隙 O）、4 元素 × 4 含量（y=0.08/0.17/0.25/0.33）× 3 晶面（111/110/100）
- 次表面掺杂（方法 B/C，仅 111）、空位紧邻/远离掺杂位两类构型
- pydefect 缺陷热力学（缺陷形成能/电荷态/转变能级）
- 论文基准参数：VASP 5.4.1, GGA-PBE, DFT+U (Ueff=4 eV, Dudarev), ENCUT=650, k=5×5×1, 18 Å 真空, 2×2 slab, 6 层, ISIF=2, 1k AFM

## 2. 关键决策日志 (Top-3 陷阱)

- **D002 SlabGenerator 参数**：必须 `lll_reduce=False, in_unit_planes=False`，否则 slab 层数错误。第一检查点。
- **D003 POSCAR 原子顺序**：pymatgen 按电负性排序破坏 U-M-O 连续，必须 `sort_by_species`。若 INCAR/POSCAR/POTCAR 不匹配，查此项。
- **D004 (111) 分层**：O 层插入 U 层间，`assign_layers` 必须按 U z 聚类。若空位/间隙定位错误，查此项。
- D005 掺杂元素不加 U (LDAUL=-1)；D006 POTCAR 用 _pv/_sv；D007 pydefect 超胞勿还原。

## 3. 思维状态快照 (推理链 + 待验证假设)

- 已完成链：PDF 解析 → 方法提取 → 目录/脚本 → 结构生成验证 → VASP 输入批量写入 → pydefect → workflow/monitor → SSHP
- 已生成并验证：109 个计算目录 VASP 输入；111/110/100 slab 均 96 原子；MOX-8/17/25/33 结构；空位/间隙构型
- 待验证假设（需实机 VASP）：
  - H1: 各晶面表面能复现论文 (111=0.51, 110=0.91, 100=1.34 J/m²)
  - H2: UO2 空位能复现 5.81/5.47/4.98 eV
  - H3: 掺杂后 U(IV) 自旋密度 ≈2.0 au、电荷补偿路径
  - H4: pydefect 转变能级位于 DFT+U 带隙 (≈1.8-2.2 eV) 内

## 4. 未完成任务 (P0/P1/P3)

- **P0**: 实机 VASP 计算（当前环境无 vasp_std，脚本仅语法/结构级验证）
- **P0**: POTCAR 拼接（需用户本地 VASP 赝势库，potcars/make_potcar.sh 已就绪）
- **P1**: Stage 0 体相优化与收敛验证（UO2 晶格常数 vs 5.47 Å <2%）
- **P1**: Stage 1 表面能复现（N2 分支判断）
- **P3**: 亚稳态扫描（2-3 组初始磁矩）、d 轨道加 U 敏感性分支
- **P3**: 论文图复现（自旋密度地图、缺陷形成能图、Bader 电荷转移图）

## 5. 文件心智模型

```
UO2_doping_DFT_study/
├── workflow.sh / monitor.sh          # 主工作流 + 监控
├── docs/01-04_*.md, tree.txt, SSHP_PROTOCOL.md
├── scripts/                          # structure/vasp 工具 + 各 Stage 生成器 + 分析
│   ├── structure_utils.py            # 体相/slab/分层/排序/AFM 核心
│   ├── vasp_utils.py                 # INCAR/KPOINTS/OUTCAR 解析
│   ├── build_bulk / generate_surfaces / doping_poscar / create_vacancy / build_hyperstoich
│   ├── subsurface_doping.py          # 方法 B/C
│   ├── write_vasp_inputs.py          # 批量写输入（自动分类）
│   ├── check_convergence.py / analyze_energies.py / bader_analysis.py
│   └── sync-session-state.sh         # SSHP 同步
├── templates/ INCAR_* KPOINTS_*     # VASP 输入模板
├── potcars/                          # POTCAR_info.md + make_potcar.sh
├── 00_bulk ~ 05_pydefect/            # Stage 0-6 计算目录
├── 06_analysis/ results/             # 分析输出
└── .claude/session-state/            # SSHP 会话状态
```

## 6. 已完成的计算结果摘要

- 结构级验证通过（无 VASP 能量，因环境无 vasp_std）：
  - 111/110/100 slab：6 层 × 4U+8O = 96 原子
  - MOX：MOX-8=U22M2O48, MOX-17=U20M4O48, MOX-25=U18M6O48, MOX-33=U16M8O48
  - UO2-x=U24O46, UO2+x=U24O50；MOX 空位=U22M2O46, 间隙=U22M2O50
  - pydefect 完美超胞 U32O64（96 原子），Va_O1/Oi/M_U 多电荷态目录
  - 109 个计算目录已写 INCAR/KPOINTS/MAGMOM；121 个目录被 check_convergence 识别
  - 次表面方法 B/C：U22Mo2O48 (2nd+5th / 3rd+4th 层)
- 全部 Python/bash 脚本语法校验通过

## 7. 外部参考

- 论文：Chen & Kaltsoyannis, Appl. Surf. Sci. 537 (2021) 147972
- 全文文本：/tmp/opencode/paper_full_text.txt（本地 PyMuPDF 解析）
- 早期方案：/workspace/初步方案-DFT计算基于VASP的UO₂掺杂体系（Mo:Nb:Zr:Ti）表面DFT+U研究 — 完整复现框架.md
- pydefect 文档：https://kumagai-group.github.io/pydefect/
- GitHub: https://github.com/ljm820/UO2_doping_DFT_study
