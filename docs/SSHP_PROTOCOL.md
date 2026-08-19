---
type: protocol
name: sshp-session-state-handover-protocol
version: 1
created: 2026-05-27
adapted: 2026-08-19
---

# SSHP — Session State Handover Protocol

## 概述

SSHP 定义了项目工作空间与用户 home 目录之间 `.claude/session-state/` 的双向同步协议，确保：
1. **项目可迁移**: 复制项目目录到任何机器即可恢复完整会话状态
2. **用户身份跨项目**: `identity.md` 和 `activation-prompt.md` 在所有项目间共享
3. **决策库不丢失**: `decision-log.md` 同时存在于 home 和 workspace
4. **上下文最新**: 最新的 project 状态始终从 workspace 同步到 home

本项目适配说明：
- 项目侧 session-state 目录：`<project>/.claude/session-state/`
- 同步脚本：`scripts/sync-session-state.sh`（push / pull / status / backup）
- 协议应用于 UO2_doping_DFT_study 项目全生命周期

---

## 文件角色与同步方向

```
~/.claude/session-state/          ←→    <project>/.claude/session-state/
────────────────────────────────         ────────────────────────────────
identity.md             ───Home→WS──→    identity.md (副本)
activation-prompt.md    ───Home→WS──→    activation-prompt.md (副本)
decision-log.md         ←──WS─Home──    decision-log.md (权威版本)
context.md              ←──WS─Home──    context.md (权威版本)
reference_*.md          ←──WS─Home──    reference_*.md (权威版本)
```

### 详细说明

| 文件 | 职责 | 权威源 | 同步触发 |
|------|------|--------|---------|
| `identity.md` | 用户画像、工作风格、角色定义 | Home | 会话开始时 Home→WS |
| `activation-prompt.md` | 启动指令、预热步骤、已知陷阱 | Home | 会话开始时 Home→WS |
| `decision-log.md` | 所有决策 (D001-D021+) 及否定方案 | Workspace | 每次决策更新后 WS→Home |
| `context.md` | TODO、推理链、阻塞点、文件心智模型 | Workspace | 每次 context 更新后 WS→Home |
| `reference_*.md` | 特定主题参考知识 | Workspace | 每次创建/更新后 WS→Home |

---

## 文件格式规范

### 1. decision-log.md (决策日志)

每条决策必须包含以下 6 个字段：

```markdown
DECISION DXXX | 决策: <一句话总结>
  备选方案:
    - ❌ <被否定的做法1> → 失败原因
    - ❌ <被否定的做法2> → 失败原因
    - ✅ <当前做法> → 为什么这个有效
  选择理由: <详细解释，包括物理/技术根因>
  影响范围: <所有受影响的文件/目录>
  重新审视条件: <什么情况下这个决策需要重新评估>
  状态: 已执行 | 已评估，无需修改 | 已修复
```

### 2. context.md (上下文状态)

必须包含以下 7 个章节：

```markdown
---
type: context
session: "<日期范围>"
status: "<当前版本> — <一句话状态>"
---

## 1. 项目/任务全景
## 2. 关键决策日志 (Top-3 陷阱)
## 3. 思维状态快照 (推理链 + 待验证假设)
## 4. 未完成任务 (P0/P1/P3)
## 5. 文件心智模型
## 6. 已完成的计算结果摘要
## 7. 外部参考
```

### 3. identity.md (用户身份)

```markdown
---
type: identity
version: <N>
last_updated: <日期>
---

# 角色定义
# 用户画像
# 工作风格
# 项目心智模型
```

### 4. activation-prompt.md (启动指令)

```markdown
---
type: activation
session: "<日期>"
---

# 步骤 0：读取状态
# 步骤 1：心智预热
# 步骤 2：工作记忆刷新
# 步骤 3：开始交互
# 会话结束指令
```

---

## 同步流程

### 会话开始时 (Agent 启动)

```
1. 读取 ~/.claude/session-state/identity.md → 恢复工作风格
2. 读取 ~/.claude/session-state/decision-log.md → 加载决策库
3. 读取 ~/.claude/session-state/context.md → 了解 TODO 和阻塞点
4. 读取 <project>/.claude/session-state/context.md → 了解最新的 project 状态
5. 执行 activation-prompt.md 步骤0-2 → 预热
```

### 会话结束时 (Agent 关闭)

```
1. 更新 <project>/.claude/session-state/decision-log.md (追加新决策)
2. 更新 <project>/.claude/session-state/context.md (闭合推理链)
3. bash scripts/sync-session-state.sh push  → 将 project 状态同步到 home
   - decision-log.md  WS→Home
   - context.md       WS→Home
   - reference_*.md   WS→Home
   - identity.md      Home→WS (如果 home 更新)
   - activation-prompt.md Home→WS (如果 home 更新)
4. 创建备份 <project>/archives/<timestamp>_session-state/
```

### 新会话启动时 (另一台机器/会话)

```
1. bash scripts/sync-session-state.sh pull  → 将 home 状态同步到 project
   - identity.md      Home→WS
   - activation-prompt.md Home→WS
   - decision-log.md  Home→WS (如果 home 比 WS 新)
   - context.md       Home→WS (如果 home 比 WS 新)
2. 读取所有文件 → 恢复完整状态
```

---

## 冲突解决

| 场景 | 规则 |
|------|------|
| decision-log.md 在 home 和 WS 中都有 D021 但内容不同 | 合并两者，保留所有决策条目，按编号去重 |
| context.md 在 home 和 WS 中不同 | WS 优先 (project context 应为最新) |
| identity.md 在 home 和 WS 中不同 | Home 优先 (用户身份跨项目不变) |
| reference_*.md 在 WS 中有新文件 | 全部同步到 home |

---

## 备份

每次同步前，sync.sh 自动在以下位置创建备份：

```
<project>/archives/session-state-backups/<timestamp>_pre-sync/
```

这样即使同步出错也能从备份恢复。
