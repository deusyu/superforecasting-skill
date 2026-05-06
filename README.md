# Superforecasting Skill

> **Turn vague concerns, decisions, and forecasts into resolvable, updatable, scoreable probabilistic predictions.**

A Claude Code / Codex skill that converts cloud-like questions ("should I", "will it work out", "how likely") into a forecast workflow with explicit probabilities, deadlines, settlement criteria, and Brier-scored calibration over time.

> Superforecasting = **probabilization + testability**.

---

## Core Design

### 1. Five Input Modes

| Mode | Trigger | Writes ledger? |
|---|---|---|
| `new` | "Should I", "will X happen", anxiety about a future outcome | ✅ |
| `update` | New evidence, "the situation changed" | ✅ |
| `settle` | Outcome happened / didn't, deadline passed | ✅ |
| `review` | "How am I doing", calibration check | ✅ (aggregate) |
| `coach` | "Teach me", "what is X" | ❌ |

### 2. Eight Gates (Mode `new` decision tree)

```
[1] Forecast / decision / emotion?
       ↓
[2] Resolvable? (deadline + criterion required)  → if not, rewrite
       ↓
[3] Cloud-like? (fuzzy words like "happy/succeed/work out")  → if yes, Fermi-ize into 3-7 sub-questions
       ↓
[4] Type? binary (default) / multi_outcome / numeric / decision_bundle
       ↓
[5] Three reference classes (broad / medium / narrow), default primary = medium
       ↓
[6] External-view base rate (state base BEFORE personal facts)
       ↓
[7] Internal-view adjustment (upward/downward factors with impact bands)
       ↓
[8] Forecast vs decision (output thresholds, not verdicts)
```

### 3. State Machine

```
                 (no forecast)
                       │ forecast_created
                       ▼
                    DRAFT  ─── question_scoped ───▶  SCOPED
                                                      │
                                          decomposed (side-branch, no state change)
                                                      │
                                                      │ probability_set
                                                      ▼
                                                   ACTIVE  ◀──┐
                                                      │       │ evidence_update
                                                      ▼       │
                                                   UPDATED  ──┘
                                                      │ settled
                                                      ▼
                                                   SETTLED  ── scored (auto) ──▶  SCORED
```

The state machine enforces three core constraints engineering-style:

1. **No `set-prob` without scoping** (every probability needs a deadline + criterion)
2. **No `update` or `settle` before active** (no probability = nothing to update)
3. **No rewriting after `settled`** (post-hoc revision is rejected)

This blocks the two most common forecast failure modes: open-ended predictions and after-the-fact reinterpretation.

### 4. LLM ↔ Script Boundary

| LLM (agent) handles | Script (`sf.py`) handles |
|---|---|
| Mode classification | ID / date / probability format validation |
| Eight Gates | State machine transition enforcement |
| Reference class selection | Persisting events to `events.jsonl` |
| Fermi decomposition | Computing Brier Score |
| Evidence strength judgment | Rendering Markdown cards |
| Decision threshold setting | Aggregating calibration reports |
| Narrative / counter-arguments / triggers | Maintaining `active.json` snapshot |

**Principle**: semantic judgment → LLM. Deterministic validation / computation / persistence → script. The script refuses to make semantic decisions on the agent's behalf.

---

## Install

### Claude Code

```bash
git clone https://github.com/deusyu/superforecasting-skill.git
ln -s "$(pwd)/superforecasting-skill" ~/.claude/skills/superforecast
```

### Codex

```bash
ln -s "$(pwd)/superforecasting-skill" ~/.codex/skills/superforecast
```

Both runtimes share the same skill content, the same script, and the same global ledger at `~/.superforecast/`.

The skill auto-triggers on inputs matching its description (Chinese: 概率/预测/应不应该/会不会/焦虑/风险; English: probability, forecast, predict, what's the chance, should I, will X happen).

---

## Quickstart

```bash
SF=scripts/sf.py

python3 $SF new "Will it rain tomorrow in Shenzhen?"
# → sf-2026-001

python3 $SF scope sf-2026-001 \
    --canonical "By 2026-05-07 23:59, will Shenzhen receive ≥1mm of rain?" \
    --resolution-date 2026-05-07 \
    --criterion "China Meteorological Administration Shenzhen station record" \
    --data-source "weather.cma.cn"

python3 $SF set-prob sf-2026-001 --p 0.40 --range 0.30 0.50 \
    --reference-class "May rainfall, Shenzhen 2015-2024" \
    --base-rate 0.45 \
    --reason "Slightly under base because morning forecast clear"

python3 $SF update sf-2026-001 \
    --evidence "Cloud cover building in afternoon" \
    --p 0.65 --strength moderate

python3 $SF settle sf-2026-001 --outcome 1
# → Brier = (0.65 - 1)² = 0.1225

python3 $SF render sf-2026-001
# → ~/.superforecast/forecasts/rendered/sf-2026-001.md

python3 $SF review --recent 20
# → ~/.superforecast/reports/calibration_YYYYMMDD.md
```

Full command reference: `python3 scripts/sf.py --help`.

---

## Ledger Layout

```
~/.superforecast/
├── forecasts/
│   ├── events.jsonl     # append-only event log (source of truth)
│   ├── active.json      # snapshot of each forecast's current state
│   └── rendered/        # markdown forecast cards
└── reports/             # calibration review reports
```

`events.jsonl` is the source of truth — `active.json` and rendered cards can be regenerated from it. Back this one file up if you care about your history.

---

## Requirements

- Python 3.10+ (standard library only, no `pip install`)

---

## Repo Layout

```
superforecasting-skill/
├── SKILL.md                        # agent behavior, workflow, output format
├── README.md                       # this file
├── LICENSE
├── references/                     # workflow gates, concepts, examples, scoring
├── schemas/                        # JSON Schemas for events and cards
├── scripts/sf.py                   # zero-dependency CLI engine
└── docs/                           # design rationale (background reading)
    ├── skill_design.md
    └── concept_understanding.md
```

---

## License

MIT — see [LICENSE](LICENSE).
