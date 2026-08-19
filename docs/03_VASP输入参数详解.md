# 03 VASP 输入参数详解

> 本章逐项说明 INCAR / POSCAR / KPOINTS / POTCAR 的设置参数与细节，可直接对照 `templates/` 目录中的模板文件。

## 一、INCAR 详解

### 1.1 通用参数（所有计算）

| 参数 | 值 | 理由 |
|------|-----|------|
| PREC | Accurate | 与 650 eV 截断能匹配的高精度设置 |
| ENCUT | 650 | 论文值；对 U 的 PAW 赝势与 O 足够，可忽略 Pulay 应力 |
| EDIFF | 1E-6（表面）/ 1E-7（体相与缺陷）| 电子步收敛精度 |
| EDIFFG | -0.02（表面）/ -0.01（体相）| 离子步收敛：力的负阈值（eV/Å）|
| ISMEAR | 0（Gaussian）| UO2 为 Mott 绝缘体，0 或 -5 均可；用 0 便于金属性掺杂体系（MoO2 等）统一 |
| SIGMA | 0.05 | 配合 Gaussian smearing |
| LREAL | .FALSE. | 关闭实空间投影，保证 5f 电子描述精度（计算量增大可接受）|
| LWAVE / LCHARG | .TRUE. | 保留波函数与电荷密度，用于续算与后处理 |
| LORBIT | 11 | 输出逐原子与轨道投影态密度（自旋分辨）|

### 1.2 DFT+U（核心）

| 参数 | 值 | 理由 |
|------|-----|------|
| LDAU | .TRUE. | 开启 +U |
| LDAUTYPE | 2 | Dudarev 旋转不变方法（U−J 形式）|
| LDAUL | 3 -1（U、O）| U 的 f 轨道加 U；O 不加 |
| LDAUU | 4.5 0.0 | U 的 U 值 4.5 eV |
| LDAUJ | 0.5 0.0 | U 的 J 值 0.5 eV → Ueff = 4.0 eV |
| LMAXMIX | 4 | 允许非对角混合，正确描述含 f 电子的电荷密度 |

**掺杂元素是否需要 +U？**
- Zr/Ti：d⁰ 体系，无需 +U（LDAUL 填 -1）；
- Mo/Nb：4d 电子。**推荐策略**：基准计算先用 LDAUL = -1（不+U），对照实验晶格常数/带隙；如明显高估金属性，再对 4d 加 U（例如 Ueff ≈ 2-3 eV）做敏感性测试。本项目默认不加，保持与文章"仅对 U 5f 加 U"的一致框架，并把 d 轨道加 U 作为敏感性分支。

> 注意：LDAUL/LDAUU/LDAUJ 的数组长度必须与 POSCAR 原子种类数一致（顺序：U, M, O 等）。

### 1.3 磁性（1k 共线 AFM）

| 参数 | 值 | 理由 |
|------|-----|------|
| ISPIN | 2 | 自旋极化 |
| MAGMOM | 见下方 | 依层序设置 ± |

**MAGMOM 约定**（UO2 6 层 slab，2×2，每层 4 个 U）：
```
层序:    1st  2nd  3rd  4th  5th  6th
磁矩:   +2.0 -2.0 +2.0 -2.0 +2.0 -2.0   (每 U)
个数:    4    4    4    4    4    4
```
即 `MAGMOM = 4*2.0 4*-2.0 4*2.0 4*-2.0 4*2.0 4*-2.0 48*0.0`，O 磁矩初始为 0。替换 U 后：Zr/Ti 处填 0.0，Mo/Nb 处填 0.0 或按预期未成对电子数试探。

### 1.4 离子弛豫

| 参数 | 值 | 场景 |
|------|-----|------|
| IBRION | 2（CG）| 通用，稳健 |
| NSW | 200 | 足够收敛 |
| ISIF | 3（体相、纯 UO2 表面）| 全弛豫（形状+体积+离子）|
| ISIF | 2（MOX、空位、间隙体系）| 固定晶胞形状体积，仅离子弛豫（论文规定）|
| NCORE / KPAR | 按机器核数 | NCORE=核数/2^k，建议 NCORE=8-16 |

### 1.5 不同场景 INCAR 差异一览

| 场景 | ISIF | EDIFF | EDIFFG | MAGMOM 要点 |
|------|------|-------|--------|-------------|
| 体相 UO2 | 3 | 1E-7 | -0.01 | 4 个 U 原胞 +2 -2 +2 -2 |
| 体相 MO2 | 3 | 1E-7 | -0.01 | MoO2/NbO2 若为金属用 ISMEAR=1 SIGMA=0.2 |
| 纯 UO2 表面 | 3 | 1E-6 | -0.02 | 层序 ± |
| MOX 表面 | 2 | 1E-6 | -0.02 | 替换位磁矩按元素 |
| 空位/间隙 | 2 | 1E-7 | -0.02 | 多组初始磁矩测亚稳态 |

### 1.6 O2 分子计算

20 Å 立方盒子，单分子 O2，ISMEAR=0 SIGMA=0.05，MAGMOM = 2.0 2.0（三重态），只算电子步（NSW=0）或轻弛豫（固定键长 1.24 Å 附近、ISIF=2）。

## 二、KPOINTS 详解

| 场景 | 网格 | 说明 |
|------|------|------|
| 体相 UO2 | 8×8×8 | 先做 4/6/8/10 收敛测试 |
| 体相 MO2 | 8×8×8（MoO2/NbO2 可用 6×6×8）| 视晶胞形状 |
| 表面 slab | 5×5×1 | 论文最小网格；可测 7×7×1 |
| O2 分子 | Γ-only（1×1×1）| 大盒子 |

## 三、POSCAR 详解

POSCAR 由 `scripts/` 下 ASE/Pymatgen 脚本生成，注意以下约定：

1. **原子种类顺序**：`U M O`（M = Mo/Nb/Zr/Ti），与 POTCAR 拼接顺序一致，与 INCAR 中 LDAUL/LDAUU/LDAUJ 顺序一致。
2. **Direct 坐标**，第 3 轴为真空方向（垂直于表面）。
3. **6 层 slab 结构**：每层 4 U + 8 O（2×2 超胞），共 96 原子（掺杂后为 94/95/97 等）。
4. **对称替换**：掺杂与缺陷均在 slab 两侧对称执行，保持结构对称性、消除偶极。
5. **磁矩**：写在 INCAR 的 MAGMOM 中（或 POSCAR 第 7 行，若用 Poscar 的 magmom 扩展语法）。

## 四、POTCAR 详解

### 4.1 拼接方法

```bash
# 原子顺序与 POSCAR 一致：U M O
cat PAW_PBE/U/POTCAR PAW_PBE/Mo_pv/POTCAR PAW_PBE/O/POTCAR > POTCAR
```

### 4.2 赝势选择与理由

| 元素 | 推荐赝势 | 价电子 | 选择原因 |
|------|----------|--------|----------|
| U | PAW_PBE U (06Apr2008) | 6s²6p⁶5f³6d¹7s² | 5f 电子需显式处理；DFT+U 作用于 f |
| O | PAW_PBE O (08Apr2002) | 2s²2p⁴ | 标准赝势；2p 与金属 d/f 杂化描述充分 |
| Mo | PAW_PBE Mo_pv (07Sep2000) | 4s²4p⁶4d⁵5s¹ | pv：4s4p 半芯态参与成键，对氧化物/掺杂体系准确 |
| Nb | PAW_PBE Nb_pv (07Sep2000) | 4s²4p⁶4d⁴5s¹ | 同 Mo，需半芯态 |
| Zr | PAW_PBE Zr_sv (07Sep2000) | 4s²4p⁶4d²5s² | sv：4s4p+4d 全入价态，ZrO2 描述更准 |
| Ti | PAW_PBE Ti_pv (07Sep2000) | 3s²3p⁶3d²4s² | pv：3p 半芯态与 O2p 作用，TiO2 关键 |

### 4.3 选择方法与验证流程

1. 首选 `_pv`（含半芯态）版本：过渡金属氧化物中半芯态与氧发生显著杂化，标准（不带后缀）赝势会低估成键；
2. Zr 用 `_sv` 而非 `_pv`：Zr 的 4s4p 相对浅，直接放入价态更稳（VASP 无 Zr_pv 时用 Zr_sv 或 Zr）；
3. 验证：对每个元素做 MO2 体相计算，对比实验晶格常数（UO2: 5.47 Å；MoO2: a≈5.61,b≈4.86,c≈5.54 Å；NbO2: a≈4.85,c≈2.99 Å；ZrO2(立方): 5.09 Å；TiO2(金红石): a≈4.59,c≈2.96 Å），偏差 < 2% 视为合格；
4. POTCAR 头部 `TITEL` 行会写明 PAW_PBE 与生成日期，可用 `grep TITEL POTCAR` 校验拼接是否正确。

## 五、templates 目录

| 文件 | 用途 |
|------|------|
| templates/INCAR_bulk | 体相模板（ISIF=3）|
| templates/INCAR_surface_sto | 化学计量比表面（ISIF=3 纯 UO2 / ISIF=2 MOX）|
| templates/INCAR_surface_substo | 空位/间隙表面（ISIF=2, EDIFF=1E-7）|
| templates/KPOINTS_bulk | 8×8×8 |
| templates/KPOINTS_surface | 5×5×1 |
| templates/KPOINTS_gamma | Γ-only（O2）|

所有模板均以 96 原子、种类序 U M O 的 slab 为默认；实际原子数由脚本按结构自动重写 MAGMOM 与 LDAU 数组。
