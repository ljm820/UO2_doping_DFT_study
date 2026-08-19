# POTCAR 赝势选择与拼接说明

> VASP 计算中 POTCAR 的顺序必须与 POSCAR 原子种类顺序一致，本项目的统一原子顺序为 **U M O**（M = Mo/Nb/Zr/Ti）。

## 一、推荐赝势表

| 元素 | 推荐赝势（PAW_PBE）| 价电子构型 | 选择原因 |
|------|---------------------|-----------|----------|
| U | `U` (06Apr2008) | 6s² 6p⁶ 5f³ 6d¹ 7s² | 5f 电子需显式处理；DFT+U 作用于 f 轨道 |
| O | `O` (08Apr2002) | 2s² 2p⁴ | 标准赝势足够，氧 2p 与金属 d/f 杂化描述准确 |
| Mo | `Mo_pv` (07Sep2000) | 4s² 4p⁶ 4d⁵ 5s¹ | **pv**：4s/4p 半芯态参与成键，对 Mo 氧化物（MoO2/MoO3）与掺杂环境准确 |
| Nb | `Nb_pv` (07Sep2000) | 4s² 4p⁶ 4d⁴ 5s¹ | **pv**：同 Mo，4d 过渡金属需半芯态 |
| Zr | `Zr_sv` (07Sep2000) | 4s² 4p⁶ 4d² 5s² | **sv**：Zr 4s/4p 较浅直接入价态，对 ZrO2 萤石结构描述更稳（VASP 无 Zr_pv）|
| Ti | `Ti_pv` (07Sep2000) | 3s² 3p⁶ 3d² 4s² | **pv**：3p 半芯态与 O 2p 作用，TiO2 中关键 |

## 二、赝势选择方法（为何不用标准无后缀版本）

1. 过渡金属氧化物中，半芯态（Mo/Nb/Ti 的 p，Zr 的 s+p）与氧 2p 轨道发生显著杂化；
   标准（无后缀）赝势把这些电子冻结在芯中，会低估 M-O 键的共价性，导致晶格常数偏大、形成能偏差。
2. `_pv` = semi-core p 态入价；`_sv` = semi-core s 态入价；`_d` 一般不用于氧化物（4d 已在价态）。
3. 对掺杂体系，杂质元素的键合环境与纯金属不同，用更完整的价态描述更可靠。

## 三、拼接命令

```bash
# 原子顺序: U M O (示例 Mo)
cat PAW_PBE/U/POTCAR PAW_PBE/Mo_pv/POTCAR PAW_PBE/O/POTCAR > POTCAR

# Zr 体系
cat PAW_PBE/U/POTCAR PAW_PBE/Zr_sv/POTCAR PAW_PBE/O/POTCAR > POTCAR
```

可用脚本 `potcars/make_potcar.sh` 批量生成，需要设置 `POTCAR_DIR` 指向赝势库根目录。

## 四、拼接校验

```bash
# 检查每段 POTCAR 的 TITEL 行
grep -c "PAW_PBE" POTCAR
grep "TITEL" POTCAR
# 期望: 3 段 (U, M, O)，顺序与 POSCAR 一致
```

## 五、赝势验证流程（体相基准）

| 体系 | 实验晶格常数 (Å) | 验证标准 |
|------|------------------|----------|
| UO2 | 5.47 | 偏差 < 2% |
| MoO2 | a≈5.61, b≈4.86, c≈5.54 | 偏差 < 2%（注意单斜畸变）|
| NbO2 | a≈4.85, c≈2.99 | 偏差 < 2% |
| ZrO2 (立方) | 5.09 | 偏差 < 2% |
| TiO2 (金红石) | a≈4.59, c≈2.96 | 偏差 < 2% |

> 若体相晶格偏差 > 2%：优先检查 ISMEAR/SIGMA（金属性 MoO2/NbO2 需 ISMEAR=1）、MAGMOM 初始化，再考虑换赝势版本。
