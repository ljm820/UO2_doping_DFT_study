---
type: decision-log
project: UO2_doping_DFT_study
version: 1
---

# 决策日志 (Decision Log)

本文件是 SSHP 协议的权威源（WS 权威），记录项目中所有关键决策与否定方案。

---

DECISION D001 | 决策: 用本地 PyMuPDF 替代 docparse 在线解析 PDF
  备选方案:
    - ❌ docparse MCP 在线解析 → 余额不足 (insufficient balance)，不可用
    - ✅ 本地 PyMuPDF 提取全文 → 成功提取 12 页论文至 /tmp/opencode/paper_full_text.txt (72KB)
  选择理由: 在线服务不可用，本地库已安装 (pymupdf)，无需网络依赖。
  影响范围: 论文解析流程；docs/01_文章解析与方法论.md
  重新审视条件: docparse 余额恢复后可用其做更精确的公式/表格 OCR
  状态: 已执行

---

DECISION D002 | 决策: SlabGenerator 必须设 lll_reduce=False, in_unit_planes=False
  备选方案:
    - ❌ 默认参数 → 生成 slab 层数不对，无法得到论文级 6 层模型
    - ✅ lll_reduce=False, in_unit_planes=False → 111/110/100 均得到 6 层 x 4U+8O/层 = 96 原子
  选择理由: pymatgen 默认的 lll 约简与单位平面转换会改变 (111) 面的堆叠方向。
  影响范围: scripts/structure_utils.py generate_slab()
  重新审视条件: 若换晶面指数或需要非对称 slab
  状态: 已执行

---

DECISION D003 | 决策: write_structure 强制 U-M-O 原子顺序
  备选方案:
    - ❌ 依赖 pymatgen 默认排序 → 按电负性排序，破坏 U-M-O 连续性，导致 POSCAR 与 INCAR 的 LDAUL/MAGMOM/POTCAR 不一致
    - ✅ sort_by_species 显式重排为 U-M-O → 与 INCAR、POTCAR 拼接顺序完全一致
  选择理由: VASP 要求同种原子连续，POTCAR 拼接必须与 POSCAR 顺序匹配。
  影响范围: scripts/structure_utils.py sort_by_species/write_structure；所有 POSCAR 生成
  重新审视条件: 无，此为 VASP 硬性要求
  状态: 已执行

---

DECISION D004 | 决策: assign_layers 按 U 的 z 坐标聚类层中心
  备选方案:
    - ❌ 按全部原子 z 直接分组 → (111) 面 O 原子层插入 U 层之间，分组错误
    - ✅ 先按 U z 聚类得到层中心，其余原子归入最近层 → 正确区分 6 层
  选择理由: 萤石 (111) 面存在 U-O-U 交替堆叠，参考元素聚类更稳健。
  影响范围: scripts/structure_utils.py assign_layers；doping/空位/间隙定位
  重新审视条件: 若处理非萤石结构
  状态: 已执行

---

DECISION D005 | 决策: 掺杂元素（Mo/Nb/Zr/Ti）默认不加 DFT+U
  备选方案:
    - ❌ 给 d 轨道也加 U → 偏离论文"仅 U 5f 加 U"框架
    - ✅ LDAUL=-1（不加 U）→ 保持论文框架；d 轨道加 U（Mo/Nb Ueff≈2-3 eV）作为敏感性分支
  选择理由: 论文基准为 U 5f Ueff=4 eV，掺杂元素 d 轨道加 U 是可选敏感性测试。
  影响范围: vasp_utils.py write_incar LDAUL/LDAUU；templates
  重新审视条件: 若发现 d 电子局域化严重，启用敏感性分支
  状态: 已执行

---

DECISION D006 | 决策: POTCAR 赝势选择 Mo/Nb/Ti 用 _pv，Zr 用 _sv，U/O 用标准
  备选方案:
    - ❌ 全部用标准赝势 → 半芯态 s/p 处理不充分，Zr 4s4p 缺失
    - ✅ Mo_pv/Nb_pv/Ti_pv（半芯态 p），Zr_sv（4s4p 入价，VASP 无 Zr_pv）→ 更准确
  选择理由: VASP 赝势库中无 Zr_pv，Zr_sv 是最高精度选择。
  影响范围: potcars/POTCAR_info.md, make_potcar.sh, DOPANT_INFO
  重新审视条件: 若换 VASP 版本或 PAW 库
  状态: 已执行

---

DECISION D007 | 决策: pydefect 完美超胞不用 get_conventional_standard_structure
  备选方案:
    - ❌ bulk * [2,2,2] 后再 get_conventional_standard_structure → 96 原子被还原成 12 原子
    - ✅ 直接 bulk * [2,2,2] → 96 原子 (U32O64)
  选择理由: UO2 常规胞就是 12 原子，SymmetryAnalyzer 会把超胞还原回原胞。
  影响范围: 05_pydefect/run_pydefect.py build_perfect_supercell
  重新审视条件: 无
  状态: 已执行

---

DECISION D008 | 决策: 次表面掺杂方法 B/C 每侧替换 1 个 U（y=0.08）
  备选方案:
    - ❌ 方法 B/C 也做 4 种含量 → 计算量翻倍，方法 B/C 仅用于验证位次效应
    - ✅ 方法 B(2nd+5th 层) / C(3rd+4th 层) 各每侧 1 个 U → MOX-8 浓度，与表面掺杂对比
  选择理由: 论文结论是替换能对方法 A/B/C 不敏感，只需代表性浓度验证。
  影响范围: scripts/subsurface_doping.py, 05_subsurface_111/
  重新审视条件: 若某元素出现异常位次效应
  状态: 已执行

---

DECISION D009 | 决策: workflow.sh 使用 write_vasp_inputs.py 无参数自动分类
  备选方案:
    - ❌ workflow 传 --calc-type 参数 → 脚本实际 CLI 只有 --dry-run，不匹配
    - ✅ 无参数调用，脚本按目录路径自动分类 (00_bulk→bulk, 01/02→surface_sto, 03/04→surface_substo)
  选择理由: write_vasp_inputs.py 内部用路径前缀分类，无需外部传参。
  影响范围: workflow.sh stage0-5 调用
  重新审视条件: 若新增 stage 目录前缀
  状态: 已执行

---

DECISION D010 | 决策: SSHP 协议在本项目落地
  备选方案:
    - ❌ 不记录会话状态 → 跨会话丢失决策/上下文/推理链
    - ✅ 采用 SSHP 协议，双向同步 home 与 workspace 的 .claude/session-state/
  选择理由: 用户明确要求实现会话状态打包迁移，支持下次会话续跑与优化。
  影响范围: docs/SSHP_PROTOCOL.md, scripts/sync-session-state.sh, .claude/session-state/
  重新审视条件: 若 home 目录策略变化
  状态: 已执行
