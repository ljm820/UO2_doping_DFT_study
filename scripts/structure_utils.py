#!/usr/bin/env python3
"""
structure_utils.py
UO2 掺杂体系结构构建工具库（ASE / Pymatgen）

提供：
- UO2 萤石体相构建（ASE 与 Pymatgen 两种）
- 表面 slab 生成（pymatgen SlabGenerator）
- 2x2 超胞
- 层归属判断（按 z 坐标分层）
- AFM 磁矩设置
- 替换/空位/间隙氧操作
"""

from __future__ import annotations

import numpy as np

from ase import Atoms
from ase.io import read, write
from pymatgen.core import Lattice, Structure
from pymatgen.core.surface import SlabGenerator

# 元素信息：POTCAR 顺序固定为 U M O
DOPANTS = ["Mo", "Nb", "Zr", "Ti"]

# 掺杂元素价电子/期望自旋密度（用于 MAGMOM 初始化和结果判读）
DOPANT_INFO = {
    "Mo": {"pseudo": "Mo_pv", "valence": 12, "d_electrons": 2, "expected_spin": 2.0},
    "Nb": {"pseudo": "Nb_pv", "valence": 11, "d_electrons": 1, "expected_spin": 1.0},
    "Zr": {"pseudo": "Zr_sv", "valence": 10, "d_electrons": 0, "expected_spin": 0.0},
    "Ti": {"pseudo": "Ti_pv", "valence": 10, "d_electrons": 0, "expected_spin": 0.0},
}


def build_uo2_bulk(lattice_constant: float = 5.47) -> Atoms:
    """用 ASE 构建 UO2 萤石体相（12 原子原胞）."""
    a = lattice_constant
    u_pos = np.array([
        [0.0, 0.0, 0.0], [0.0, 0.5, 0.5],
        [0.5, 0.0, 0.5], [0.5, 0.5, 0.0],
    ])
    o_pos = np.array([
        [0.25, 0.25, 0.25], [0.25, 0.75, 0.75], [0.75, 0.25, 0.75], [0.75, 0.75, 0.25],
        [0.25, 0.25, 0.75], [0.25, 0.75, 0.25], [0.75, 0.25, 0.25], [0.75, 0.75, 0.75],
    ])
    cell = a * np.eye(3)
    atoms = Atoms(
        symbols=["U"] * 4 + ["O"] * 8,
        positions=np.vstack([u_pos * a, o_pos * a]),
        cell=cell,
        pbc=True,
    )
    return atoms


def build_uo2_bulk_pymatgen(lattice_constant: float = 5.47) -> Structure:
    """用 Pymatgen 构建 UO2 萤石体相."""
    a = lattice_constant
    species = ["U"] * 4 + ["O"] * 8
    coords = [
        [0.0, 0.0, 0.0], [0.0, 0.5, 0.5], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0],
        [0.25, 0.25, 0.25], [0.25, 0.75, 0.75], [0.75, 0.25, 0.75], [0.75, 0.75, 0.25],
        [0.25, 0.25, 0.75], [0.25, 0.75, 0.25], [0.75, 0.25, 0.25], [0.75, 0.75, 0.75],
    ]
    return Structure(Lattice.cubic(a), species, coords)


def generate_slab(bulk: Structure, miller_index, min_slab_size: float = 18.0,
                  min_vacuum_size: float = 18.0, center_slab: bool = True,
                  n_2x2: bool = True, target_u_layers: int = 6) -> Structure:
    """
    用 pymatgen 生成指定晶面的 slab，可选 2x2 超胞。

    自动扫描 slab 厚度，使 1x1 slab 的 U 原子数恰好等于 target_u_layers
    （即论文的 6 层模型：1x1 = 6 UO2，2x2 = 24 UO2、每层 4 U + 8 O）。

    返回 2x2 slab（每层 4 U + 8 O，6 层共 72 原子）。
    """
    chosen = None
    for size in np.arange(6.0, 26.0, 1.0):
        slabgen = SlabGenerator(
            initial_structure=bulk,
            miller_index=miller_index,
            min_slab_size=float(size),
            min_vacuum_size=min_vacuum_size,
            center_slab=center_slab,
            lll_reduce=False,
            in_unit_planes=False,
        )
        cands = slabgen.get_slabs()
        for c in cands:
            n_u = c.composition.get_el_amt_dict().get("U", 0)
            if abs(n_u - target_u_layers) < 1e-6 and not c.is_polar():
                chosen = c
                break
        if chosen is not None:
            break
    if chosen is None:
        raise RuntimeError(f"未能生成 {miller_index} 的 {target_u_layers} 层 slab，请检查参数")
    if n_2x2:
        chosen.make_supercell([2, 2, 1])
    return chosen


def make_2x2(structure: Structure) -> Structure:
    """返回 2x2 超胞（面内放大两倍，z 不变）."""
    s = structure.copy()
    s.make_supercell([2, 2, 1])
    return s


def assign_layers(structure: Structure, axis: int = 2,
                  reference_species: str = "U", tol: float = 0.05) -> dict:
    """
    按分数坐标将原子分配到层（以参考元素的 z 层为基准）。

    对萤石 (111) 面，U 层之间夹着 O，直接按全部原子 z 分组会把层错误合并；
    因此先用参考元素（默认 U）的 z 坐标聚类得到层中心，再让每个原子归属
    到最近的层中心。

    返回 {layer_index: [site_indices]}，layer_index 从 0（最下层）开始。
    """
    frac = structure.frac_coords[:, axis]
    species = [str(s.specie) for s in structure]

    ref_z = np.sort(frac[np.array(species) == reference_species])
    if ref_z.size == 0:
        ref_z = np.sort(frac)
    centers = [ref_z[0]]
    for z in ref_z[1:]:
        if z - centers[-1] > tol:
            centers.append(z)
        else:
            centers[-1] = (centers[-1] + z) / 2.0
    centers = np.array(centers)

    layers: dict = {}
    for i, z in enumerate(frac):
        li = int(np.argmin(np.abs(centers - z)))
        layers.setdefault(li, []).append(i)
    return layers


def surface_site_indices(structure: Structure, species: str,
                         n_layers: int = 1, axis: int = 2) -> tuple:
    """
    返回指定元素在 slab 上表面（高 z）与下表面（低 z）的原子索引。

    返回 (top_indices, bottom_indices)，按 z 从高到低排列的 top。
    """
    layers = assign_layers(structure, axis)
    layer_idx = sorted(layers.keys())
    top = []
    bottom = []
    for li in layer_idx[:n_layers]:
        bottom.extend([i for i in layers[li]
                       if str(structure[i].specie) == species])
    for li in layer_idx[-n_layers:]:
        top.extend([i for i in layers[li]
                    if str(structure[i].specie) == species])
    return top, bottom


def set_afm_magmoms(structure: Structure, magmoms: dict, layer_mag: dict,
                    axis: int = 2) -> list:
    """
    按层设置初始磁矩。

    magmoms: {species: (indices, value)} 精确指定某元素磁矩
    layer_mag: {layer_index: value} 用于按层整体指定（U 的 AFM 排序）
    """
    layers = assign_layers(structure, axis)
    n = len(structure)
    mag = np.zeros(n)
    for li, value in layer_mag.items():
        for idx in layers[li]:
            mag[idx] = value
    for species, (idx_list, value) in magmoms.items():
        for idx in idx_list:
            mag[idx] = value
    return mag.tolist()


def sort_by_species(structure: Structure, species_order: list) -> Structure:
    """
    按指定元素顺序分组重排原子，保证 POSCAR 中同种原子连续、
    且种类顺序与 INCAR 的 LDAU/MAGMOM 一致。
    VASP 要求同种原子在 POSCAR 中连续出现，pymatgen 默认按电负性
    排序会破坏 U-M-O 约定，因此必须显式排序。
    """
    order = list(species_order)
    for s in structure:
        el = str(s.specie)
        if el not in order:
            order.append(el)
    site_lists = {el: [] for el in order}
    for site in structure:
        site_lists[str(site.specie)].append(site)
    new_species = []
    new_coords = []
    for el in order:
        for site in site_lists[el]:
            new_species.append(el)
            new_coords.append(site.coords)
    from pymatgen.core import Structure as _S
    new_struct = _S(structure.lattice, new_species, new_coords,
                    coords_are_cartesian=True)
    return new_struct


def write_structure(structure: Structure, filename: str,
                    species_order: list = None) -> Structure:
    """
    写 POSCAR（pymatgen 格式），默认按 U-M-O 顺序排序原子。

    返回排序后的结构（用于后续 MAGMOM/INCAR 生成保持顺序一致）。
    """
    if species_order is None:
        species_order = ["U", "Mo", "Nb", "Zr", "Ti", "O"]
    s = sort_by_species(structure, species_order)
    s.to(fmt="poscar", filename=filename)
    return s


def write_cif(structure: Structure, filename: str):
    """写 CIF 便于 VESTA 查看."""
    structure.to(fmt="cif", filename=filename)


def read_structure(filename: str) -> Structure:
    """读取 POSCAR/CIF 为 pymatgen Structure."""
    return Structure.from_file(filename)
