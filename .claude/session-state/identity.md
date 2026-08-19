---
type: identity
version: 1
last_updated: 2026-08-19
---

# 角色定义

- 用户：材料计算研究者（DFT/第一性原理方向）
- 项目角色：主导 UO2 掺杂体系（Mo/Nb/Zr/Ti）表面 DFT+U 研究的完整复现

# 用户画像

- 目标：复现 Chen & Kaltsoyannis, Appl. Surf. Sci. 537 (2021) 147972 的方法，并扩展掺杂元素
- 关注点：缺陷形成能、电荷态、转变能级、自旋密度、Bader 电荷、表面能、替换能
- 工作环境：VASP 5.4.1 + GGA-PBE + DFT+U (Ueff=4 eV, Dudarev)，pydefect 0.10.1，ASE/Pymatgen
- 沟通语言：中文

# 工作风格

- 完整方案优先：每次输出包含完整代码、操作步骤、预期输出、问题排查指南
- 根因诊断：遇到错误先定位根因，再给出靶向修复
- 端到端验证：每次修改后运行完整验证，确保组件协同工作
- 被否决方案会明确记录到 decision-log，新方案前先确认未被排除

# 项目心智模型

- UO2 萤石结构，6 层 2x2 slab（96 原子），18 Å 真空，5x5x1 k 点
- 关键公式：E_sur=(E_slab-6E_bulk)/2；E_rep=(E_MOX-(1-y)E_UO2-yE_MO2)/2；E_for=(E_sub+E_O2-E_sto)/2
- 数值基准：E_sur=0.51/0.91/1.34 J/m²；UO2 空位能=5.81/5.47/4.98 eV
- 状态管理：使用 SSHP 协议在 home 与 workspace 间同步会话状态
