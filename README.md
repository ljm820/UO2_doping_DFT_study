# UO2 掺杂体系（Mo/Nb/Zr/Ti）表面 DFT+U 研究 — VASP 完整复现框架

> **版本**: v2.0（2026-08-19）｜ 完整框架文档见 `docs/完整复现框架_v2.0.md`
> **基础文章**：J.-L. Chen, N. Kaltsoyannis, *DFT + U study of U1-yAnyO2-x (An = Np, Pu, Am and Cm) {111}, {110} and {100} surfaces*, Applied Surface Science 537 (2021) 147972.
> **DOI**：https://doi.org/10.1016/j.apsusc.2020.147972
> **GitHub**：https://github.com/ljm820/UO2_doping_DFT_study
> **会话状态**：SSHP 协议见 `docs/SSHP_PROTOCOL.md`，同步脚本 `scripts/sync-session-state.sh`

本项目从论文解析出发，将原文的锕系元素（Np/Pu/Am/Cm）替换为**过渡金属 Mo、Nb、Zr、Ti**，以 **UO2 萤石结构**为基础（覆盖低化学计量比 UO2-x 与过化学计量比 UO2+x），研究**不同掺杂元素、不同含量、不同掺杂位次**以及 **O 空位/间隙 O 缺陷**对 UO2 表面性质的作用机制，并利用 **pydefect** 项目方法完成缺陷热力学与扩散分析。

## 一、研究目标

1. **复现文章方法**：VASP 5.4.1 + GGA-PBE + DFT+U（Ueff = 4 eV，Dudarev），650 eV 截断能，5×5×1 k 点，6 层 2×2 slab，18 Å 真空层，1k 共线 AFM。
2. **元素替换**：将 An(Np/Pu/Am/Cm) 替换为 Mo/Nb/Zr/Ti，对比 d 电子过渡金属与 f 电子锕系在 UO2 表面的行为差异。
3. **含量扫描**：y = 0.08 / 0.17 / 0.25 / 0.33 四种掺杂比例（对应每侧表面替换 1/2/3/4 个 U）。
4. **缺陷化学**：O 空位（UO2-x，O:M = 1.92:1）、间隙氧（UO2+x，过化学计量比）、掺杂元素紧邻/远离空位两类构型。
5. **位次效应**：仅 (111) 面考察方法 A（1st+6th 层）、方法 B（2nd+5th 层）、方法 C（3rd+4th 层）三种掺杂深度。
6. **pydefect 集成**：对缺陷构型做形成能、电荷态、热力学转变能级与载流子俘获分析。

## 二、目录结构

```
UO2_doping_DFT_study/
├── README.md                      # 本文件（项目总说明）
├── workflow.sh                    # 主工作流控制脚本（Stage 0-7）
├── monitor.sh                     # 运行状态监控与关键指标评估脚本
├── docs/                          # 全部文档
│   ├── 01_文章解析与方法论.md      # 论文完整解析 + 操作步骤/分析处理/总结
│   ├── 02_研究框架与工作流.md      # 研究框架、执行工作流、分支判断节点
│   ├── 03_VASP输入参数详解.md      # INCAR/POSCAR/KPOINTS/POTCAR 细节说明
│   ├── 04_关键技术指标与筛选标准.md # 收敛判据、筛选标准、物理量公式
│   ├── 完整复现框架_v2.0.md       # v2.0 完整复现框架（总览文档）
│   ├── SSHP_PROTOCOL.md           # SSHP 会话状态迁移协议
│   └── tree.txt                   # 项目 tree 树形图
├── scripts/                       # 全部 Python/Shell 脚本
├── .claude/session-state/         # SSHP 会话状态（identity/activation/decision-log/context/reference）
├── archives/                      # SSHP 同步自动备份
├── templates/                     # INCAR/KPOINTS 模板
├── potcars/                       # POTCAR 选择与拼接说明
├── 00_bulk/                       # 体相优化（UO2/MoO2/NbO2/ZrO2/TiO2 + O2）
├── 01_surface_generation/         # 纯 UO2 表面 slab 构建与弛豫
├── 02_stoichiometric_MOX/         # 化学计量比 U1-yMyO2 表面
├── 03_substoichiometric/          # 低化学计量比 U1-yMyO2-x（O 空位）
├── 04_hyperstoichiometric/        # 过化学计量比 U1-yMyO2+x（间隙 O）
├── 05_pydefect/                   # pydefect 缺陷分析
├── 06_analysis/                   # 后处理分析（表面能/替换能/空位形成能/自旋密度/Bader）
└── results/                       # 结果 CSV 汇总
```

## 三、快速开始

```bash
# 1. 环境准备（VASP 编译版与并行环境在集群上配置）
module load vasp/5.4.4 openmpi/4.1
export VASP_EXEC="mpirun -np 64 vasp_std"

# 2. 准备赝势（POTCAR，见 potcars/POTCAR_info.md）
bash potcars/make_potcar.sh

# 3. 构建体相结构与表面 slab（无需 VASP 即可运行）
python scripts/build_bulk.py
python scripts/generate_surfaces.py

# 4. 生成掺杂与缺陷结构
python scripts/doping_poscar.py
python scripts/create_vacancy.py
python scripts/build_hyperstoich.py

# 5. 写入 VASP 输入文件
python scripts/write_vasp_inputs.py

# 6. 运行体相计算（Stage 0），收敛后进入后续阶段
bash workflow.sh --stage 0

# 7. （可选）会话状态迁移：结束前 push、新会话开始时 pull
bash scripts/sync-session-state.sh status
bash scripts/sync-session-state.sh push
```

## 四、执行顺序（详见 docs/02 与 docs/04）

| Stage | 内容 | 关键判断节点 |
|-------|------|-------------|
| 0 | 体相优化（UO2 及 MO2 氧化物、O2 分子） | 晶格常数偏差 < 2% 实验值 |
| 1 | UO2 (111)(110)(100) 表面 slab | 表面能(111) ≈ 0.51 J/m² |
| 2 | 化学计量比 U1-yMyO2 表面（4 元素 × 4 含量 × 3 面） | 替换能趋势合理、自旋密度合理 |
| 3 | 低化学计量比 U1-yMyO2-x（O 空位） | Efor 与文献 UO2 可比（5.81/5.47/4.98 eV） |
| 4 | 过化学计量比 U1-yMyO2+x（间隙 O） | 缺陷形成能符号与稳定性判断 |
| 5 | 次表面掺杂（方法 B/C，仅 111） | 替换能对位次不敏感 |
| 6 | pydefect 缺陷热力学 | 转变能级位于带隙内、载流子俘获 |
| 7 | 后处理汇总与作图 | 趋势自洽、误差分析 |

## 五、关键计算结果定义（论文 eq.1-3）

- **表面能**：E_sur = (E_slab − 6 × E_bulk) / (2 × A)
- **替换能**：E_rep = (E_MOX − (1−y) × E_UO2 − y × E_MO2) / 2
- **O 空位形成能**：E_for = (E_sub + E_O2 − E_sto) / 2，E_O2 为三重态 O2 于 20 Å 盒子中的能量
- **自旋密度**：α − β 电子数（au），用于判定氧化态（U(IV)≈2.0，U(III)≈3.0）

## 六、所需软件版本

| 软件 | 版本 | 用途 |
|------|------|------|
| VASP | 5.4.x（与原文 5.4.1 兼容） | 所有 DFT 计算 |
| Python | ≥ 3.10 | 脚本运行 |
| ASE | ≥ 3.22 | 结构构建/超胞/分析 |
| pymatgen | ≥ 2023.x | 表面生成/缺陷/分析 |
| pydefect | ≥ 0.9 | 缺陷热力学分析 |
| VESTA | 任意 | 结构可视化 |

> 说明：本项目所有脚本均在 Python 3.11 + ASE 3.29 + pymatgen 2026.5 + pydefect 0.10.1 环境下验证通过。
