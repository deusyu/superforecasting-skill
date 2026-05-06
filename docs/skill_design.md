# Superforecasting Skill 设计文稿

> 版本：v0.2  
> 定位：Claude Code / Codex 共用的 Superforecasting Skill 设计稿  
> 核心修正：Claude Code 与 Codex 的 skill 视为同一套 skill；不使用 Excel；不依赖 Git 历史；不需要提交记录。

---

## 1. 一句话定义

**Superforecasting Skill 是一个把模糊判断、焦虑、战略问题、产品赌注、人生决策转化为可结算、可更新、可记分的概率预测工作流。**

它不是“给用户一个神谕”，而是帮助用户建立一个可校准的判断过程：

```text
模糊问题 / 焦虑 / 决策
→ 费米化拆解
→ 可结算问题
→ 参考类与基础概率
→ 内部视角修正
→ 当前概率
→ 更新触发器
→ 到期结算
→ Brier 记分
→ 复盘校准
```

---

## 2. 设计前提

本设计采用以下前提：

1. **Claude Code 和 Codex 的 skill 是一致的。**
   - 不为 Claude Code 和 Codex 写两套不同设计。
   - 使用同一份 `SKILL.md`、同一套 workflow、同一套脚本和同一套概念文件。
   - 若环境需要不同目录，只做路径适配，不改变 skill 内容。

2. **不使用 Excel。**
   - Excel 不适合作为 agent-driven skill 的核心载体。
   - 预测记录、更新、结算、评分应由结构化文件和脚本处理。

3. **不依赖 Git 历史。**
   - 不把 Git commit 当成预测历史。
   - 不要求用户提交、打标签、回滚或维护仓库历史。
   - 如果需要记录预测更新历史，由 forecast ledger 自身保存，而不是靠 Git。

4. **LLM 与确定性代码分工。**
   - LLM 负责语义工作：拆解问题、选择参考类、解释证据、生成预测卡、帮助复盘。
   - 脚本负责确定性工作：字段校验、状态转换、概率范围校验、Brier Score 计算、报告渲染。

---

## 3. Skill 的核心产品形态

Superforecasting Skill 可以被理解为三层：

```text
1. Skill Workflow
   - 识别问题类型
   - 费米化
   - 改写为可结算预测
   - 选择参考类
   - 估计概率
   - 生成更新触发器
   - 输出预测卡

2. Deterministic Engine
   - 校验预测字段
   - 保存预测事件
   - 计算 Brier Score
   - 渲染 forecast card / review report
   - 防止概率非法、状态非法

3. Forecast Artifacts
   - events.jsonl
   - active_forecasts.json
   - rendered forecast cards
   - calibration reports
```

这里的 artifacts 不是 Excel，也不是 Git 历史，而是 skill 运行后产生的结构化预测文件与可读报告。

---

## 4. 推荐目录结构

可以使用一个统一目录：

```text
superforecasting-skill/
├── SKILL.md
├── references/
│   ├── workflow.md
│   ├── superforecasting_concepts.md
│   ├── examples.md
│   └── scoring.md
├── scripts/
│   └── sf.py
├── schemas/
│   ├── forecast_event.schema.json
│   └── forecast_card.schema.json
└── artifacts/
    ├── forecasts/
    │   ├── events.jsonl
    │   ├── active.json
    │   └── rendered/
    └── reports/
        └── calibration_summary.md
```

如果 Claude Code 或 Codex 需要不同发现路径，只做包装：

```text
.claude/skills/superforecast/ → 指向同一份 skill 内容
.agents/skills/superforecast/ → 指向同一份 skill 内容
```

但设计上只维护一个 skill。

---

## 5. Skill 的输入类型

Skill 接收自然语言输入，但内部要归类为五种模式。

### 5.1 新建预测：`new`

用户输入：

```text
我担心三个月后产品留存不行。
```

Skill 识别为：

```yaml
mode: new
raw_question: 我担心三个月后产品留存不行。
needs_scoping: true
```

目标是把它改写成：

```yaml
canonical_question: 到 2026-08-06，产品 30 日留存率是否低于 25%？
outcome_type: binary
resolution_date: 2026-08-06
settlement_criterion: 以产品后台统计口径为准；若 30 日留存率 < 25%，记为发生。
```

---

### 5.2 更新预测：`update`

用户输入：

```text
update sf-2026-001：今天拿到了两个广州公司的面试。
```

Skill 识别为：

```yaml
mode: update
forecast_id: sf-2026-001
evidence: 今天拿到了两个广州公司的面试。
```

输出应包含：

```yaml
old_probability: 0.62
new_probability: 0.71
evidence_direction: upward
evidence_strength: moderate
reason: 面试数量增加，说明工作维度的成功概率上升，但尚未转化为 offer。
```

---

### 5.3 结算预测：`settle`

用户输入：

```text
settle sf-2026-001 occurred
```

Skill 或脚本处理：

```yaml
forecast_id: sf-2026-001
outcome: 1
final_probability: 0.71
brier_score: 0.0841
```

二元预测的 Brier Score：

```text
Brier = (p - outcome)^2
```

其中：

```text
发生 = 1
未发生 = 0
```

---

### 5.4 复盘预测：`review`

用户输入：

```text
review 最近 20 条预测
```

输出应包括：

```yaml
average_brier_score: 0.18
calibration_notes:
  - 70% 档预测实际发生率接近 65%，略微过度自信。
  - 30% 以下预测中有若干发生，说明低概率事件被低估。
resolution_notes:
  - 有较多 45%-55% 的预测，可能存在和稀泥倾向。
```

---

### 5.5 概念解释 / 训练：`coach`

用户输入：

```text
教我怎么把这个问题做费米化。
```

Skill 不一定写入 ledger，而是输出教学式拆解。

---

## 6. 输出：预测卡

每个新预测的标准输出是一张 Forecast Card。

```markdown
# Superforecasting 预测卡

## 1. 原始问题
用户最初怎么问。

## 2. 可结算问题
到什么日期，什么事件是否发生。

## 3. 判定标准
什么算发生，什么算没发生，数据来源是什么。

## 4. 问题类型
binary / multi_outcome / numeric / decision_bundle。

## 5. 费米化拆解
如果原始问题是云状问题，拆成 3-7 个子预测。

## 6. 参考类
宽参考类、中参考类、窄参考类分别是什么，主参考类选哪个。

## 7. 基础概率
先用外部视角给出 base rate。

## 8. 内部视角修正
列出上调因素、下调因素，以及调整幅度。

## 9. 当前概率
给出当前概率、概率区间、信心等级。

## 10. 反方观点
这次预测最可能错在哪里。

## 11. 更新触发器
什么证据会上调概率，什么证据会下调概率。

## 12. 行动阈值
如果这是决策问题，说明超过什么概率行动，低于什么概率暂缓。

## 13. 结算与记分
到期如何结算，如何计算 Brier Score。

## 14. Ledger Event
生成结构化事件，供脚本保存。
```

---

## 7. 中间选择：8 个 Gate

Skill 的核心不是直接回答，而是在中间做一系列选择。

### Gate 1：这是预测、决策，还是情绪？

```text
如果用户表达焦虑：
  先把焦虑转成可结算预测。

如果用户问“该不该”：
  先拆成多个预测，再给行动阈值。

如果用户问“为什么”：
  可能不是预测，而是解释或因果分析。
```

例子：

```text
我该不该搬去广州？
```

不是单个预测，应拆成：

```text
1. 搬去广州 6 个月后生活满意度是否 >= 7/10？
2. 3 个月内是否能找到月薪不低于当前 80% 的工作？
3. 1 个月内是否能找到预算内且通勤可接受的住处？
4. 6 个月内是否能建立稳定社交圈？
```

---

### Gate 2：能不能结算？

不能结算的问题必须重写。

```text
用户会喜欢这个产品吗？
```

改写为：

```text
上线后 30 天内，次日留存率是否超过 35%？
上线后 90 天内，付费转化率是否超过 5%？
上线后 14 天内，NPS 是否超过 30？
```

---

### Gate 3：是否需要费米化？

如果问题包含以下词，通常是云状问题：

```text
幸福、成功、喜欢、脱钩、崩盘、变好、有前途、会火、关系会不会好、能不能卷出来
```

默认做费米化。

---

### Gate 4：选择预测类型

```yaml
binary:
  description: 是否发生
  example: 到 2026-08-06，30 日留存率是否低于 25%？

multi_outcome:
  description: 多个互斥结果之一
  example: 未来三个月求职结果分别是什么概率？

numeric:
  description: 数值预测
  example: 未来三个月 MRR 中位数是多少？

decision_bundle:
  description: 一个决策由多个预测共同支持
  example: 要不要搬去广州、要不要辞职、要不要上线某功能。
```

默认优先转为 binary，因为最容易结算和训练。

---

### Gate 5：选择参考类

Skill 应强制输出三层参考类：

```yaml
reference_classes:
  broad:
    - 类似城市迁移者
  medium:
    - 从北京迁往广州的职场人
  narrow:
    - 同职业、同收入阶段、有内推资源的迁移者
primary_reference_class: medium
reason: 比 broad 更贴近，又不像 narrow 那样样本过少。
```

---

### Gate 6：生成先验概率

先用外部视角，不急着讲个人故事。

```yaml
base_rate:
  probability: 0.45
  confidence: low_to_medium
  reason: 类似迁城者半年内达到较高满意度并不罕见，但职业和社交变量影响较大。
```

---

### Gate 7：内部视角修正

```yaml
adjustments:
  upward:
    - factor: 有广州公司内推
      impact: +5% to +10%
    - factor: 房租压力可能下降
      impact: +3% to +6%
  downward:
    - factor: 气候适应风险
      impact: -3% to -8%
    - factor: 社交网络重建
      impact: -5% to -10%
final_probability: 0.62
probability_range: 55% - 68%
```

---

### Gate 8：预测与决策分离

预测回答：

```text
这件事发生概率是多少？
```

决策回答：

```text
在这个概率下，考虑成本、收益、可逆性、后悔和备选方案，要不要行动？
```

输出可采用：

```yaml
decision_threshold:
  act_if_above: 0.70
  test_if_between: [0.55, 0.70]
  pause_if_below: 0.55
```

---

## 8. 数据结构：Forecast Event

不使用 Excel，也不使用 Git 历史。预测过程通过结构化事件保存。

推荐 `events.jsonl`：每一行是一条事件。

```json
{"type":"forecast_created","id":"sf-2026-001","created_at":"2026-05-06","raw_question":"我去广州会幸福吗？"}
{"type":"question_scoped","id":"sf-2026-001","canonical_question":"到2026-12-31，我在广州连续居住4个月后，生活满意度是否达到7/10以上？","resolution_date":"2026-12-31"}
{"type":"probability_set","id":"sf-2026-001","p":0.62,"range":[0.55,0.68],"reason":"工作与居住维度较强，社交与气候适应不确定"}
{"type":"evidence_update","id":"sf-2026-001","p_from":0.62,"p_to":0.71,"evidence":"拿到两个广州公司的面试"}
{"type":"settled","id":"sf-2026-001","outcome":1}
{"type":"scored","id":"sf-2026-001","brier":0.0841}
```

说明：

- 这里的 event log 是预测系统自身的数据，不是 Git 历史。
- 不需要 commit。
- 不需要用户管理版本。
- 记录更新是为了预测结算和复盘，不是为了做代码版本管理。

---

## 9. 状态机

```text
DRAFT
  ↓
SCOPED
  ↓
DECOMPOSED
  ↓
ESTIMATED
  ↓
ACTIVE
  ↓
UPDATED
  ↓
SETTLED
  ↓
REVIEWED
```

| 状态 | Agent 做什么 | 脚本做什么 |
|---|---|---|
| DRAFT | 接收原始问题 | 创建 forecast id |
| SCOPED | 改写为可结算问题 | 校验 deadline / settlement criterion |
| DECOMPOSED | 做费米化拆解 | 保存子问题 |
| ESTIMATED | 给参考类、先验、内部修正 | 校验概率范围 |
| ACTIVE | 输出预测卡 | 写入 active forecasts |
| UPDATED | 根据新证据更新概率 | 追加 update event |
| SETTLED | 根据事实结算 | 计算 Brier Score |
| REVIEWED | 复盘偏差 | 生成 calibration report |

---

## 10. CLI / Script 设计

脚本不需要复杂，MVP 可只有一个 `sf.py`。

推荐命令：

```bash
sf new "我去广州会幸福吗？"
sf update sf-2026-001 --evidence "拿到两个广州公司的面试" --p 0.71
sf settle sf-2026-001 --outcome 1
sf score sf-2026-001
sf render sf-2026-001
sf review --recent 20
```

脚本职责：

```text
1. 生成 forecast id
2. 追加事件到 events.jsonl
3. 校验概率必须在 0 到 1 之间
4. 校验每个 active forecast 必须有截止日期和结算标准
5. 计算 Brier Score
6. 渲染 Markdown 预测卡
7. 生成 calibration summary
```

脚本不负责：

```text
1. 替用户选择参考类
2. 替用户做费米化
3. 判断证据强弱
4. 给最终概率背书
```

这些由 agent 完成。

---

## 11. `SKILL.md` 草案

```markdown
---
name: superforecast
summary: Turn vague concerns, decisions, and forecasts into resolvable, updatable, and scoreable probabilistic forecasts.
description: Use this skill when the user asks what might happen, whether something will succeed, how likely an outcome is, how to think about a risk, or wants to turn anxiety into a probability forecast. The skill creates forecast cards, update triggers, and settlement plans. It can also update, settle, score, and review forecasts.
---

You are the Superforecasting Skill.

Your purpose is to turn vague judgments into resolvable probabilistic forecasts.

Core principle:

Superforecasting = probabilization + testability.

Do not merely give an opinion. Produce a forecast workflow.

## Workflow

1. Classify the user input:
   - new forecast
   - update existing forecast
   - settle forecast
   - review forecast history
   - decision requiring multiple forecasts
   - concept coaching

2. If the question is vague, perform Fermi-izing:
   - turn the cloud-like question into 3-7 concrete sub-questions
   - each sub-question should be resolvable if possible

3. For each forecast, define:
   - canonical question
   - outcome type: binary, multi_outcome, numeric, or decision_bundle
   - resolution date
   - settlement criterion
   - data source or evidence source

4. Estimate probability:
   - start with external view / reference class
   - then adjust using internal view
   - give current probability and probability range
   - list upward and downward factors separately

5. Generate update triggers:
   - what evidence would raise probability
   - what evidence would lower probability
   - next review date

6. Separate forecast from decision:
   - forecast = probability of outcome
   - decision = action threshold given costs, benefits, reversibility, and alternatives

7. Output a Forecast Card.

8. If a deterministic script is available, use it only for:
   - validating fields
   - saving structured events
   - computing Brier scores
   - rendering reports

9. Do not rely on Git history.
   - No commits are required.
   - Forecast updates are stored as forecast artifacts, not Git history.

10. When settling binary forecasts:
   - outcome occurred = 1
   - outcome did not occur = 0
   - Brier Score = (p - outcome)^2

## Output format

Always prefer this structure:

# Superforecasting Forecast Card

## Original Question

## Resolvable Question

## Settlement Criterion

## Forecast Type

## Fermi-ized Subquestions

## Reference Classes

## Base Rate

## Internal Adjustments

## Current Probability

## Probability Range

## Why This Forecast Might Be Wrong

## Update Triggers

## Decision Threshold

## Settlement and Scoring Plan

## Ledger Event
```

---

## 12. MVP 实施方案

MVP 只做四个文件级能力：

```text
1. SKILL.md：定义 agent 行为
2. references/superforecasting_concepts.md：定义概念与术语
3. scripts/sf.py：处理事件保存、评分、渲染
4. artifacts/forecasts/events.jsonl：保存预测事件
```

MVP 的四个命令：

```text
new     新建预测卡
update  根据新证据更新预测
settle  结算预测
review  复盘预测表现
```

MVP 的完成标准：

```text
1. 能把云状问题改写成可结算问题
2. 能输出至少一个当前概率和概率区间
3. 能列出参考类、上调因素、下调因素
4. 能生成更新触发器
5. 能在结算时计算 Brier Score
6. 能生成一份简短复盘
```

---

## 13. 示例：广州迁居预测

用户输入：

```text
我去广州会幸福吗？
```

Skill 输出：

```yaml
mode: new
original_question: 我去广州会幸福吗？
forecast_type: decision_bundle
canonical_question: 到 2026-12-31，我在广州连续居住至少 4 个月后，生活满意度是否达到 7/10 以上？
resolution_date: 2026-12-31
settlement_criterion: 用户自评生活满意度 >= 7/10，且已在广州连续居住至少 4 个月。
current_probability: 0.62
probability_range: [0.55, 0.68]

fermiized_subquestions:
  - question: 3 个月内是否能找到月薪不低于当前 80% 的工作？
    probability: 0.65
  - question: 1 个月内是否能找到预算内且通勤可接受的住处？
    probability: 0.75
  - question: 6 个月内是否能建立稳定社交圈？
    probability: 0.45
  - question: 3 个月后是否适应广州气候和生活节奏？
    probability: 0.58
  - question: 6 个月后储蓄率是否不低于当前水平？
    probability: 0.70

reference_classes:
  broad: 类似城市迁移者
  medium: 从北京迁往广州的职场人
  narrow: 同职业、同收入阶段、有内推资源的迁移者
  primary: medium

upward_factors:
  - 有广州公司内推
  - 房租压力可能下降
  - 生活节奏可能更适合

downward_factors:
  - 社交网络需要重建
  - 气候适应存在风险
  - 职业机会仍未确认

update_triggers:
  upward:
    - 两周内拿到 2 个以上有效面试
    - 试住期间满意度高于 7/10
    - 确认广州住房成本显著低于北京
  downward:
    - 一个月内无有效面试
    - 目标岗位薪资普遍低于当前 70%
    - 试住期间明显不适应气候

decision_threshold:
  act_if_above: 0.70
  test_if_between: [0.55, 0.70]
  pause_if_below: 0.55
```

---

## 14. 非目标

本 skill 不做以下事情：

1. 不把预测伪装成确定性结论。
2. 不把“建议”冒充“预测”。
3. 不在没有截止日期和结算标准时强行报概率。
4. 不要求用户使用 Excel。
5. 不要求用户使用 Git commit 做历史。
6. 不追求伪精确；必要时给概率区间。
7. 不替代高风险领域的专业判断。

---

## 15. 最终产品文案

可以把这个 skill 对用户解释为：

> **把焦虑写成问题，把问题拆成变量，把变量变成概率，把概率交给现实检验。**

或者更短：

> **预测不是观点的延长线，而是自我校准的工艺。**
