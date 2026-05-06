# Rainman Superforecast

English | [中文](README.zh-CN.md)

Claude Code / Codex skill that turns vague concerns ("should I", "will it work out", "how likely") into resolvable, updatable, Brier-scored probabilistic forecasts — and persists them as a calibration ledger you can train against over time.

> Inspired by Philip Tetlock's *Superforecasting* and the Good Judgment Project. The book gives the methodology (probabilization, reference classes, Bayesian updating, Brier scoring); this project turns that methodology into an enforceable workflow — an LLM agent that walks you through the eight gates, plus a deterministic Python engine that persists state, validates probability ranges, enforces a state machine, and scores you over time. The goal is not "AI predicts the future" but "AI engineers your forecasting process so the human keeps judgment ownership."

---

## How It Works

```
User input ("should I leave Beijing?", "will the deal close?", anxiety)
  │
  ▼
[Mode classification]  new / update / settle / review / coach
  │
  ▼ (Mode = new)
[Gate 1] Forecast vs decision vs emotion
[Gate 2] Resolvable? — rewrite if not
[Gate 3] Cloud-like? — Fermi-ize into 3-7 sub-questions
[Gate 4] Type: binary (default) / multi_outcome / numeric / decision_bundle
[Gate 5] Three reference classes (broad / medium / narrow)
[Gate 6] External-view base rate (state base BEFORE personal facts)
[Gate 7] Internal-view adjustments (upward/downward × impact bands)
[Gate 8] Forecast vs decision threshold (act / test / pause)
  │
  ▼
[State machine] sf.py persists every step
  ∅ → DRAFT → SCOPED → ACTIVE → UPDATED* → SETTLED → SCORED (auto Brier)
  │
  ▼
~/.superforecast/forecasts/   ← global ledger, shared across projects
~/.superforecast/reports/     ← calibration reviews

Render → 14-section Markdown forecast card
```

The skill enforces three engineering constraints that prevent the most common forecast failures: **no probability without a deadline + criterion**, **no rewriting after settlement**, **no scoring without binary outcome**. Together they block open-ended predictions and after-the-fact reinterpretation — the two ways most people's "judgment" never actually improves.

## Features

- **Eight-gate forecast workflow** — every new forecast walks through resolvability, Fermi-ization, three-layer reference class, base rate, internal adjustments, decision threshold
- **State machine** — `DRAFT → SCOPED → ACTIVE → UPDATED* → SETTLED → SCORED`, illegal transitions rejected with clear errors
- **Append-only event ledger** — `events.jsonl` is the source of truth; `active.json` and rendered cards are derived
- **Brier-scored calibration** — automatic `(p − outcome)²` on settle, per-band calibration report on review
- **Update with evidence strength buckets** — strong (±10–20%) / moderate (±5–10%) / weak (±2–5%), prevents mechanical updating
- **Decision ≠ forecast** — outputs `act_if_above` / `test_if_between` / `pause_if_below` thresholds, never verdicts
- **Global ledger** — `~/.superforecast/` shared across all projects and runtimes (Claude Code + Codex see the same history)
- **Zero dependencies** — Python 3.10+ standard library only, no `pip install`

## Prerequisites

- **Claude Code CLI** or **Codex CLI** — installed and authenticated
- **Python 3.10+** — standard library only, no extras needed

## Quick Start

### 1. Install the skill

**Option A: Git clone (recommended)**

```bash
git clone https://github.com/deusyu/superforecasting-skill.git ~/.claude/skills/superforecast
```

For Codex:

```bash
git clone https://github.com/deusyu/superforecasting-skill.git ~/.codex/skills/superforecast
```

**Option B: Symlink an existing checkout**

```bash
git clone https://github.com/deusyu/superforecasting-skill.git
ln -s "$(pwd)/superforecasting-skill" ~/.claude/skills/superforecast
ln -s "$(pwd)/superforecasting-skill" ~/.codex/skills/superforecast
```

Both runtimes share the same skill content and the same global ledger at `~/.superforecast/`.

### 2. Make a forecast

In Claude Code, just say what's on your mind:

```
我担心三个月后产品留存不行
should I move from Beijing to Shanghai?
how likely is it that we ship by end of Q2?
```

The skill auto-triggers, walks you through the eight gates, asks for the missing context (resolution date, settlement criterion, reference class anchor), and writes the forecast card.

### 3. Find your outputs

| Path | What's there |
|------|-------------|
| `~/.superforecast/forecasts/events.jsonl` | Append-only event log (source of truth) |
| `~/.superforecast/forecasts/active.json` | Snapshot of every forecast's current state |
| `~/.superforecast/forecasts/rendered/<id>.md` | Markdown forecast cards (14-section template) |
| `~/.superforecast/reports/calibration_*.md` | Calibration review reports |

## Pipeline Details

### Step 1: Classify the input mode

| Mode | Trigger | Writes ledger? |
|------|---------|----------------|
| `new` | "should I", "will X", anxiety about a future outcome | ✅ |
| `update` | New evidence, "the situation changed" | ✅ |
| `settle` | Outcome happened / didn't, deadline passed | ✅ |
| `review` | "How am I doing", calibration check | ✅ (aggregate) |
| `coach` | "Teach me", "what is X" | ❌ |

### Step 2: Run the eight gates (Mode `new`)

The gates are a decision tree, not a checklist. Each gate's output feeds the next:

1. **Forecast / decision / emotion** — anxiety reframes to a forecast; should-I splits into multiple sub-forecasts + decision threshold
2. **Resolvable?** — must have a deadline AND a third-party-verifiable criterion, else rewrite
3. **Cloud-like?** — fuzzy words like "happy / succeed / work out" trigger Fermi-ization into 3–7 sub-questions
4. **Type** — `binary` (default), `multi_outcome`, `numeric`, or `decision_bundle`
5. **Three reference classes** — broad / medium / narrow, default primary = medium
6. **External-view base rate** — state base from primary reference class **before** introducing personal facts (this is the single most-violated rule)
7. **Internal-view adjustments** — upward/downward factors with explicit impact bands (`+5% to +10%`)
8. **Decision threshold** — `act_if_above` / `test_if_between` / `pause_if_below`, never verdicts

Full gate-by-gate operational detail in [`references/workflow.md`](references/workflow.md).

### Step 3: State machine

```
∅ ──forecast_created──▶ DRAFT ──question_scoped──▶ SCOPED
                                                    │
                                       decomposed (side-branch, no state change)
                                                    │
                                                    │ probability_set
                                                    ▼
                                                 ACTIVE ◀──┐
                                                    │     │ evidence_update
                                                    ▼     │
                                                 UPDATED ─┘
                                                    │ settled
                                                    ▼
                                                 SETTLED ──scored (auto)──▶ SCORED
```

Three constraints the script enforces:

1. **No `set-prob` without `scope`** — every probability must be bound to a deadline + criterion
2. **No `update` or `settle` before `ACTIVE`** — no probability = nothing to update or settle
3. **No rewriting after `SETTLED`** — post-hoc revision is rejected

These block the two most common forecast failure modes: open-ended predictions and after-the-fact reinterpretation.

### Step 4: LLM ↔ script boundary

| LLM (agent) handles | Script (`sf.py`) handles |
|---------------------|--------------------------|
| Mode classification | ID / date / probability format validation |
| Eight gates | State machine transition enforcement |
| Reference class selection | Persisting events to `events.jsonl` |
| Fermi decomposition | Computing Brier Score |
| Evidence strength judgment | Rendering Markdown cards |
| Decision threshold setting | Aggregating calibration reports |
| Narrative + reverse-argument + triggers | Maintaining `active.json` snapshot |

**Principle**: semantic judgment → LLM. Deterministic validation / computation / persistence → script. The script refuses to make semantic decisions on the agent's behalf — it will not pick a reference class, judge evidence strength, or rubber-stamp a probability.

### Step 5: Brier scoring & calibration review

For binary forecasts: `Brier = (final_probability − outcome)²`, range `[0, 1]`, lower is better.

`sf review --recent N` aggregates settled forecasts into probability bands and reports gaps:

```
- < 20%   : ~10% should occur
- 20–40%  : ~30% should occur
- 40–60%  : ~50% should occur
- 60–80%  : ~70% should occur
- ≥ 80%   : ~90% should occur
```

`gap > 0` = underconfident; `gap < 0` = overconfident; `|gap| < 0.05` with `n ≥ 10` = well-calibrated in that band. Fence-sitting (≥ 40% of forecasts in the 40–60% band) gets flagged separately.

Full Brier interpretation, evidence-strength buckets, and review-writing guidance in [`references/scoring.md`](references/scoring.md).

## Project Structure

| File | Purpose |
|------|---------|
| `SKILL.md` | Skill definition — workflow, output format, hard constraints, script integration |
| `scripts/sf.py` | Zero-dependency Python CLI engine — state machine, validation, Brier, render |
| `references/workflow.md` | Five input modes + eight gates in operational detail |
| `references/superforecasting_concepts.md` | Terminology and principles glossary |
| `references/examples.md` | Six worked cases (life, product, business, exam, update, settle) |
| `references/scoring.md` | Brier interpretation, calibration bands, evidence-strength buckets |
| `schemas/forecast_event.schema.json` | `events.jsonl` line format (8 event types, oneOf) |
| `schemas/forecast_card.schema.json` | Render input format (14-section card) |
| `docs/skill_design.md` | Original design rationale |
| `docs/concept_understanding.md` | Conceptual foundation document |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `illegal transition: state X, allowed sources [...]` | A workflow step was skipped. The error message names the allowed source states — backtrack to one of those. |
| `forecast not found: sf-YYYY-NNN` | Run `sf list` to see available ids. The id format is `sf-YYYY-NNN`. |
| `<id> has no current probability; run sf set-prob first` | Trying to `update` or `settle` a forecast that's never had `set-prob`. Set an initial probability first. |
| `<id> has no probability set; cannot settle` | Same as above for `settle`. |
| `--outcome must be 0 or 1` | `settle` only accepts binary outcomes. For non-binary forecasts, settle the binary main-resolution sub-forecast separately. |
| `--range must take exactly 2 values: LOW HIGH` | Pass two space-separated floats: `--range 0.30 0.50`. |
| `invalid range: [0.5, 0.3]` | Lower bound must be ≤ upper bound. |
| Skill doesn't auto-trigger in Claude Code | Verify the symlink: `ls -L ~/.claude/skills/superforecast/SKILL.md`. Use one of the trigger keywords (probability/forecast/should I/概率/应不应该). |
| Lost the ledger | `events.jsonl` is the source of truth. If you have it, `active.json` and rendered cards regenerate from it. Back up only this one file. |

## Roadmap

The MVP covers single-user binary forecasting with manual update/settle. Future work is grouped by independence:

### Phase 1 — Multi-outcome scoring (planned)

Generalize Brier to multi-class: `Σ (p_i − I(outcome=i))² / number_of_classes`. Update `sf settle` to accept `--outcome-class` for `multi_outcome` forecasts. Numeric forecasts use absolute or quantile error; record manually until consensus on the right metric.

### Phase 2 — Time-bound triggers (planned, independent)

Today the skill emits update triggers as text in the forecast card. Phase 2 adds `sf trigger add <id> --on-date YYYY-MM-DD --message "..."` so the agent can re-surface forecasts at the right time. Optional integration with system reminders / cron.

### Phase 3 — Cross-forecast portfolio review (planned, depends on Phase 1)

When multiple forecasts cover the same decision (the "leave Beijing" example below cycled through 3 parallel forecasts), the review step should compare them as a portfolio: which path has the highest concentration / lowest variance, where the costs/reversibility differ, what to settle vs. retain. Today the agent does this in narrative; Phase 3 makes it a first-class CLI command.

### Design principles

- **Scripts do bookkeeping; LLMs do semantic judgment.** State, schemas, dedup, hashing, IO, scoring are deterministic Python. Mode classification, reference-class selection, evidence-strength buckets, decision thresholds are LLM calls.
- **Single writer for shared state.** Only `sf.py` writes the ledger. The agent never hand-edits `events.jsonl` or `active.json`.
- **Engineer the failure modes out.** No probability without a deadline. No rewriting after settlement. No scoring without binary outcome. The state machine is the enforcement mechanism.
- **Forecast ≠ decision.** The skill outputs probability + thresholds; the user owns the action.

## Star History

If you find this project helpful, please consider giving it a Star ⭐!

[![Star History Chart](https://api.star-history.com/svg?repos=deusyu/superforecasting-skill&type=Date)](https://star-history.com/#deusyu/superforecasting-skill&Date)

## Sponsor

If this project saves you time or helps you make a better-calibrated decision, consider sponsoring to keep it maintained and improved.

[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-pink?logo=github)](https://github.com/sponsors/deusyu)

## License

[MIT](LICENSE)
