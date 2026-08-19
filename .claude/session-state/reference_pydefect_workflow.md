# Reference: pydefect 工作流（0.10.1）

## CLI 工具链

- `pydefect` 主命令：supercell / defect_set / cpd_and_vertices / defect_energy_infos / plot_defect_formation_energy 等
- `pydefect_vasp`：unitcell / defect_entries / calc_results / make_poscars
- `pydefect_vasp_util`：rdp（结构对称化）
- `vise vs -t defect`：生成缺陷 VASP 输入

## 完整流程

```
1. 准备标准原胞（必须是标准 primitive cell，否则 NotPrimitiveError）
   pydefect supercell -p unitcell.yaml --matrix 2 2 2
2. 设置氧化态（defect_set 用）
   pydefect defect_set --oxi_states U 4 O -2 Mo 4
3. 生成 defect_in.yaml（缺陷种类与电荷态）
   如 Va_O1: [0, 1, 2]  Oi: [-2, -1, 0]
4. 生成缺陷结构并跑 VASP（各电荷态）
   pydefect_vasp de ; for i in */; do cd $i; vise vs -t defect; cd ../; done
5. 解析结果
   pydefect_vasp calc_results -d *_*/ perfect
6. 生成缺陷能量信息（需 unitcell + standard_energies）
   pydefect defect_energy_infos -d *_*/ -pcr perfect/calc_results.json \
            -u ../unitcell/unitcell.yaml -s ../cpd/standard_energies.yaml
7. 有限尺寸修正（带电缺陷）
   pydefect efnv -d *_*/ -pcr perfect/calc_results.json -u ../unitcell/unitcell.yaml
8. 画缺陷形成能图（多电荷态/化学势区间）
   pydefect plot_defect_formation_energy
```

## 本项目封装

`05_pydefect/run_pydefect.py` 提供：
- `setup [--defect NAME]`：构建 2×2×2 完美超胞（96 原子）+ Va_O/Oi/M_U 缺陷多电荷态目录
- `parse`：调用 `pydefect_vasp calc_results`
- `formation-energy`：简化缺陷形成能计算（需 VASP 输出）

## 关键陷阱

- 完美超胞勿用 `get_conventional_standard_structure()`（会把 2×2×2 还原成 12 原子原胞）→ D007
- 大超胞建议 Gamma-only k 点
- charged defect 需 FNV 有限尺寸修正（介电常数 UO2≈24）
