---
type: activation
session: "2026-08-19"
---

# 启动指令

你即将开始新一轮会话。请严格按以下步骤执行：

## 步骤 0：读取状态

你已经读取了 `identity.md`、`decision-log.md` 和 `context.md`。
你现在是一个**连续的工作者**，不是初次见面的新 AI。

检查 `~/.claude/session-state/` 和 `./.claude/session-state/` 目录的状态：
- 如果两者一致 → 直接继续
- 如果 `context.md` 不同 → WS (project) 版本是权威源
- 如果 `decision-log.md` 不同 → 合并两者，按 D 编号去重

运行 `bash scripts/sync-session-state.sh status` 确认同步状态。

## 步骤 1：心智预热（内部执行，不要输出）

在回答用户之前，先在内部完成以下思维活动：

1. **定位断点**：查看 context.md 的未完成任务（P0/P1/P3）与当前版本
2. **恢复推理链**：阅读 decision-log.md 中最近 3 条决策 —— 了解上一次做了什么、留下了什么
3. **识别最可能的陷阱**：检查 D001-D010 已知陷阱（slab 生成参数、原子排序、MAGMOM 层序）
4. **识别当前优先级**：从 context.md TODO 中找出 P0 任务
5. **执行同步检查**：运行 `bash scripts/sync-session-state.sh status` 确认两个 session-state 目录一致

## 步骤 2：工作记忆刷新

快速消化关键决策（DECISION LOG）中的**每一个条目**。特别是这些最容易走偏的：

- **D002 — SlabGenerator 必须 lll_reduce=False, in_unit_planes=False**：否则得不到论文级 6 层
- **D003 — pymatgen 按电负性排序破坏 U-M-O 顺序**：必须用 sort_by_species 显式重排
- **D004 — (111) 面 O 层导致错误分层**：assign_layers 必须按 U z 聚类
- **D005 — 掺杂元素默认不加 +U**：LDAUL=-1，仅 U 5f 加 U（Ueff=4 eV）
- **D007 — VASP 无 Zr_pv**：Zr 用 _sv，Mo/Nb/Ti 用 _pv

## 步骤 3：开始交互

以这个状态开始工作。你的第一个输出应该类似：

> "项目状态: v2.0 — UO2 掺杂研究框架完整（脚本/文档/工作流/SSHP 已交付，GitHub 仓库已创建）。决策日志 D001-D010 已加载。建议从运行体相计算（Stage 0）或进入 06_analysis 后处理开始。"

## 执行风格（从历史对话提炼）

- **完整方案优先**：每次输出包含完整代码、操作步骤、预期输出、问题排查指南
- **根因诊断**：遇到错误时先定位根因（检查 D001-D010 已知陷阱），再给出靶向修复
- **避免在未经验证的方向上浪费时间**：复现问题、验证 fix、再继续下一步
- **端到端验证**：每次修改后运行完整的验证，确保所有组件协同工作
- **被否决的方案会明确记录**：新方案说明前先确认未被 D001-D010 中的决策排除

## 会话结束指令

当用户表示会话即将结束时，自动执行以下检查：

1. 回顾本次会话，更新 identity.md 中的行为模式观察（如果有新发现）
2. 将所有新决策追加到 decision-log.md 中（从 D011 开始编号）
3. 更新 context.md 的思维状态快照（闭合已完成的推理链，记录新的）
4. 更新 TODO 状态
5. 将本次会话的关键转折点总结为一段话
6. 运行 `bash scripts/sync-session-state.sh push` 将项目决策/上下文同步到 home
7. 创建备份 `bash scripts/sync-session-state.sh backup`

然后提示用户这些文件已更新。
