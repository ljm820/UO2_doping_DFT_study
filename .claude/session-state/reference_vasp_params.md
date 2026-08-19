# Reference: VASP 输入参数（本项目基准）

## 核心参数（论文基准，复现必须遵守）

| 参数 | 值 | 说明 |
|------|-----|------|
| VASP 版本 | 5.4.1 | PAW |
| 泛函 | GGA-PBE | 论文明确 PBE 优于 PBE-Sol |
| DFT+U | Ueff=4 eV (U=4.5, J=0.5) | Dudarev 方法，仅 U 5f |
| ENCUT | 650 eV | 足够大，忽略 Pulay 应力 |
| k 点 | 5×5×1（表面）/ 8×8×8（体相）| Monkhorst-Pack |
| 磁性 | 1k 共线 AFM | 奇数层 spin-up，偶数层 spin-down |
| SOC | 忽略 | 对表面稳定性影响极小 |
| 真空层 | 18 Å | |
| 表面 | 2×2 六层 slab（96 原子）| U4O8×6 |
| ISIF | 2（MOX/亚计量比）/ 3（体相/纯 UO2 表面）| |
| SIGMA | 0.05 | ISMEAR=0 或 1 |

## INCAR 关键块

```
LDAU    = .TRUE.
LDAUTYPE= 2
LDAUL   = 3 -1          # 仅 U 加 U；O 不加；掺杂元素 D005 决策默认 -1
LDAUU   = 4.5 0.0
LDAUJ   = 0.5 0.0
ISPIN   = 2
MAGMOM  = 4*2.0 4*-2.0 4*2.0 4*-2.0 4*2.0 4*-2.0   # 6 层 2x2 约定，O=0
LMAXMIX = 4
```

## MAGMOM 层序约定（6 层 2×2 slab）

每层 4 U：`4*2.0 4*-2.0 4*2.0 4*-2.0 4*2.0 4*-2.0`，O 全部 0。
掺杂元素磁矩按 DOPANT_INFO d 电子数（Mo_pv=2, Nb_pv=1, Zr_sv=0, Ti_pv=0）。

## POTCAR 选择（D006 决策）

- U：标准（U）
- O：标准（O）
- Mo/Nb/Ti：_pv（半芯态 p）
- Zr：_sv（VASP 无 Zr_pv，4s4p 入价）

## 缺陷体系

- EDIFF=1E-7；建议 2-3 组初始磁矩测亚稳态
- pydefect 各电荷态单点：k=3×3×3，NELECT 按价电子数-电荷调整
