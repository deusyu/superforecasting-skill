# Rainman Superforecast

[English](README.md) | 中文

我们日常焦虑的判断 — "应不应该"、"会不会成"、"概率有多大" — 大部分从来不会被结算。我们说一句模糊的话，世界继续展开，事后再用一个新的叙事把过去圆回来。判断从未真正被检验过，所以也从未真正进步过。

这个 skill 让判断变得**可结算**。它带你把每个焦虑改写为一个可结算的预测（明确事件、截止日期、判定标准）；用参考类而非个人故事来锚定概率；随证据更新；到期结算；长期 Brier 评分。账本是全局的 — 跨项目所有预测都落到同一个 `~/.superforecast/`，calibration 训练在真实结果上，而不是在记忆里。

> **超级预测 = 概率化 + 可检验。** 受 Philip Tetlock 的《超级预测》和 Good Judgment Project 启发。书给出方法论（参考类、基础概率、贝叶斯更新、Brier 评分）；本项目把方法论变成可执行的流程。LLM agent 带你走完 8 个 Gate（可结算性、费米化、三层参考类、基础概率、内部视角调整、预测与决策分离 ……）；一个确定性的 Python 引擎用状态机堵住两种最常见的预测堕落形式：没截止日期的开放式预测、事后改口的合理化叙事。目标不是"AI 预测未来"，而是"AI 把你的预测流程工程化；判断权和决策责任归人"。

---

## 工作原理

```
用户输入（"该不该离开北京？"、"deal 会不会成？"、焦虑）
  │
  ▼
[模式分类]  new / update / settle / review / coach
  │
  ▼ （Mode = new）
[Gate 1] 预测 vs 决策 vs 情绪
[Gate 2] 可结算？— 不可结算就重写
[Gate 3] 云状词？— 费米化为 3-7 个子问题
[Gate 4] 类型：binary（默认）/ multi_outcome / numeric / decision_bundle
[Gate 5] 三层参考类（broad / medium / narrow）
[Gate 6] 外部视角 base rate（先报基础概率，再讲个人故事）
[Gate 7] 内部视角调整（上调/下调因素 × 影响带）
[Gate 8] 决策阈值（act / test / pause）
  │
  ▼
[状态机] sf.py 持久化每一步
  ∅ → DRAFT → SCOPED → ACTIVE → UPDATED* → SETTLED → SCORED（自动算 Brier）
  │
  ▼
~/.superforecast/forecasts/   ← 全局账本，跨项目共享
~/.superforecast/reports/     ← Calibration 复盘报告

渲染 → 14 段 Markdown 预测卡
```

Skill 通过工程化方式堵住三个最常见的预测堕落形式：**没截止日期 + 没结算标准就不让出概率**、**结算后不能改写**、**非二元结果不能做 Brier**。这三条把"开放式预测"和"事后改口"两个最常见的失败模式从源头切断 — 这正是大多数人"判断力"长期不进步的原因。

## 功能特性

- **8-Gate 预测工作流** — 每条新预测都走过可结算性、费米化、三层参考类、基础概率、内部调整、决策阈值
- **状态机** — `DRAFT → SCOPED → ACTIVE → UPDATED* → SETTLED → SCORED`，非法转移直接报错并提示原因
- **Append-only 事件账本** — `events.jsonl` 是 single source of truth；`active.json` 和渲染卡片都是派生
- **Brier 自动评分** — `settle` 时自动算 `(p − outcome)²`，`review` 时按概率分档出报告
- **证据强度分档更新** — strong (±10–20%) / moderate (±5–10%) / weak (±2–5%)，避免机械调参
- **预测 ≠ 决策** — 输出 `act_if_above` / `test_if_between` / `pause_if_below` 阈值，从不替用户做决定
- **全局账本** — `~/.superforecast/` 跨项目跨运行时共享（Claude Code + Codex 看到同一份历史）
- **零依赖** — Python 3.10+ 标准库，无需 `pip install`

## 前置要求

- **Claude Code CLI** 或 **Codex CLI** — 已安装并完成认证
- **Python 3.10+** — 仅标准库

## 快速开始

### 1. 安装 Skill

**方式 A：Git 克隆（推荐）**

```bash
git clone https://github.com/deusyu/superforecasting-skill.git ~/.claude/skills/superforecast
```

Codex 用户：

```bash
git clone https://github.com/deusyu/superforecasting-skill.git ~/.codex/skills/superforecast
```

**方式 B：软链已有 checkout**

```bash
git clone https://github.com/deusyu/superforecasting-skill.git
ln -s "$(pwd)/superforecasting-skill" ~/.claude/skills/superforecast
ln -s "$(pwd)/superforecasting-skill" ~/.codex/skills/superforecast
```

两种 runtime 共享同一份 skill 内容和同一个全局账本 `~/.superforecast/`。

### 2. 提一个预测

在 Claude Code 中直接说：

```
我担心三个月后产品留存不行
该不该从北京搬到上海？
我们这季度内能上线的概率是多少？
```

Skill 自动触发，带你走完 8 个 Gate，索取缺失的关键信息（截止日期、结算标准、参考类锚点），最后写出预测卡。

### 3. 查看输出

| 路径 | 内容 |
|------|------|
| `~/.superforecast/forecasts/events.jsonl` | Append-only 事件流（source of truth） |
| `~/.superforecast/forecasts/active.json` | 每条预测的当前状态快照 |
| `~/.superforecast/forecasts/rendered/<id>.md` | Markdown 预测卡（14 段模板） |
| `~/.superforecast/reports/calibration_*.md` | Calibration 复盘报告 |

## 流程详解

### 第一步：模式分类

| 模式 | 触发 | 写账本？ |
|------|------|----------|
| `new` | "应不应该"、"会不会"、对未来的焦虑 | ✅ |
| `update` | 新证据、"情况变了" | ✅ |
| `settle` | 结果发生了/没发生、到期 | ✅ |
| `review` | "我做得怎么样"、calibration check | ✅（聚合） |
| `coach` | "解释一下"、"教我" | ❌ |

### 第二步：跑八个 Gate（Mode `new`）

Gate 是决策树而非清单。每个 Gate 的输出喂给下一个：

1. **预测 / 决策 / 情绪** — 焦虑先转预测；should-I 拆成多个子预测 + 决策阈值
2. **可结算？** — 必须有截止日期 AND 第三方可验证的判定标准，否则重写
3. **云状词？** — 模糊词如"幸福/成功/会火"触发费米化为 3-7 个子问题
4. **类型** — `binary`（默认）/ `multi_outcome` / `numeric` / `decision_bundle`
5. **三层参考类** — broad / medium / narrow，默认 primary = medium
6. **外部视角 base rate** — 先报来自主参考类的 base rate，**再**引入个人故事（这是最常被违反的一条）
7. **内部视角调整** — 上调/下调因素分开列，每条带明确影响区间（`+5% to +10%`）
8. **决策阈值** — `act_if_above` / `test_if_between` / `pause_if_below`，绝不给"应该 / 不应该"

完整的 Gate 操作细节见 [`references/workflow.md`](references/workflow.md)。

### 第三步：状态机

```
∅ ──forecast_created──▶ DRAFT ──question_scoped──▶ SCOPED
                                                    │
                                       decomposed（旁支，不改主状态）
                                                    │
                                                    │ probability_set
                                                    ▼
                                                 ACTIVE ◀──┐
                                                    │     │ evidence_update
                                                    ▼     │
                                                 UPDATED ─┘
                                                    │ settled
                                                    ▼
                                                 SETTLED ──scored（自动）──▶ SCORED
```

脚本强制三条工程约束：

1. **未 `scope` 不能 `set-prob`** — 每个概率必须绑定到截止日期 + 结算标准
2. **未 `ACTIVE` 不能 `update` 或 `settle`** — 没概率自然没法更新或结算
3. **`SETTLED` 之后不能改写** — 拒绝事后改口

这两条堵住了"开放式预测"和"事后改口"两种最常见的失败模式。

### 第四步：LLM ↔ 脚本边界

| LLM (agent) 负责 | 脚本 (`sf.py`) 负责 |
|------------------|---------------------|
| 模式分类 | ID / 日期 / 概率格式校验 |
| 跑 8 个 Gate | 状态机转移合法性 |
| 选参考类 | 持久化事件到 `events.jsonl` |
| 费米化拆解 | 计算 Brier Score |
| 判断证据强度 | 渲染 Markdown 卡片 |
| 设定决策阈值 | 聚合 calibration 报告 |
| 写叙事 + 反方观点 + 触发器 | 维护 `active.json` 快照 |

**原则**：语义判断 → LLM；确定性校验/计算/持久化 → 脚本。脚本拒绝替 LLM 做语义决定 — 它不会替你选参考类、不会替你判证据强弱、不会替你给概率背书。

### 第五步：Brier 评分与 Calibration 复盘

二元预测：`Brier = (final_probability − outcome)²`，区间 `[0, 1]`，越低越好。

`sf review --recent N` 按概率分档聚合所有 settled 预测，给出每档的 gap：

```
- < 20%   : 应大致 ~10% 发生
- 20–40%  : 应大致 ~30% 发生
- 40–60%  : 应大致 ~50% 发生
- 60–80%  : 应大致 ~70% 发生
- ≥ 80%   : 应大致 ~90% 发生
```

`gap > 0` 表示低估（事件比你预测的更频繁发生）；`gap < 0` 表示过度自信；`|gap| < 0.05` 且 `n ≥ 10` 表示该档已校准。和稀泥（≥ 40% 预测落在 40–60% 档）会被单独标出。

完整的 Brier 解读、证据强度分档、复盘写法见 [`references/scoring.md`](references/scoring.md)。

## 项目结构

| 文件 | 用途 |
|------|------|
| `SKILL.md` | Skill 定义 — 工作流、输出格式、硬约束、脚本集成 |
| `scripts/sf.py` | 零依赖 Python CLI 引擎 — 状态机、校验、Brier、渲染 |
| `references/workflow.md` | 5 模式 + 8 Gate 操作细则 |
| `references/superforecasting_concepts.md` | 术语和原理词表 |
| `references/examples.md` | 6 个工作示例（生活/产品/商业/学习/更新/结算） |
| `references/scoring.md` | Brier 解读、calibration 分档、证据强度 |
| `schemas/forecast_event.schema.json` | `events.jsonl` 行格式（8 种事件，oneOf） |
| `schemas/forecast_card.schema.json` | 渲染输入格式（14 段卡） |
| `docs/skill_design.md` | 原始设计稿 |
| `docs/concept_understanding.md` | 概念基础文档 |

## 常见问题

`sf.py` 的错误信息是自解释的 — 直接读即可。`illegal transition: state X, allowed sources [...]` 已经列出允许的源状态；`no current probability` 已经提示下一步是 `sf set-prob`。Coding agent（Claude Code / Codex）能直接读懂这些错误并修复，不需要额外的查询表。

这里只列环境/安装/恢复类问题 — agent 单凭错误信息无法解决：

| 场景 | 处理方式 |
|------|----------|
| Skill 在 Claude Code / Codex 中不自动触发 | 验证软链：`ls -L ~/.claude/skills/superforecast/SKILL.md`（或 `~/.codex/skills/...`）。如果文件不可达，runtime 根本没加载 skill — 重建软链。 |
| 账本丢失或损坏 | `events.jsonl` 是唯一 source of truth。只要它还在，replay 即可重建 `active.json` 和渲染卡。如果 `events.jsonl` 也丢了 — 历史就没了，今后请只备份这一个文件。 |
| `python3` 在 `sf.py` 上报语法错误 | 脚本要求 Python 3.10+（`__future__` annotations 中用了 `X \| Y` union 语法）。升级 Python 或用 `python3.10+` 解释器显式调用。 |

## 后续规划

MVP 覆盖单用户二元预测 + 手动 update/settle。后续按独立性分阶段：

### Phase 1 — 多结果评分（计划中）

把 Brier 推广到多类：`Σ (p_i − I(outcome=i))² / 类别数`。`sf settle` 增加 `--outcome-class` 支持 `multi_outcome` 预测。Numeric 预测用绝对误差或 quantile 误差，先手动记录直到对的指标达成共识。

### Phase 2 — 时间触发器（计划中，独立）

当前 skill 把 update 触发器以文本形式写在预测卡里。Phase 2 增加 `sf trigger add <id> --on-date YYYY-MM-DD --message "..."`，让 agent 能在合适时间自动 re-surface 预测。可选集成系统提醒 / cron。

### Phase 3 — 跨预测组合复盘（计划中，依赖 Phase 1）

当多条预测对应同一个决策时（"离开北京"那个案例就同时跑了 3 条并行预测），review 应该把它们当组合对比：哪条概率最高/方差最小，成本/可逆性差异在哪，该 settle 哪些保留哪些。当前 agent 用叙事处理；Phase 3 把它做成一等公民的 CLI 命令。

### 设计原则

- **脚本做记账，LLM 做语义判断**。状态、schema、去重、hash、IO、评分是确定性 Python；模式分类、参考类选择、证据强度分档、决策阈值是 LLM 调用。
- **共享状态单写者**。只有 `sf.py` 写账本。Agent 永不手改 `events.jsonl` 或 `active.json`。
- **把失败模式工程化堵掉**。没截止日期不能出概率。结算后不能改写。非二元不能算 Brier。状态机就是执行机制。
- **预测 ≠ 决策**。Skill 输出概率 + 阈值；用户负责行动。

## Star History

如果这个项目对您有帮助，请考虑为其点亮一颗 Star ⭐！

[![Star History Chart](https://api.star-history.com/svg?repos=deusyu/superforecasting-skill&type=Date)](https://star-history.com/#deusyu/superforecasting-skill&Date)

## 赞助

如果这个项目帮你节省了时间，或帮你做了一个更校准的决策，欢迎赞助支持后续维护和改进。

[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-pink?logo=github)](https://github.com/sponsors/deusyu)

## License

[MIT](LICENSE)
