# Workflow Reference

Detailed playbook for the Superforecasting Skill agent. Read this when you need to
decide *what* to do given a user's input. SKILL.md gives the high-level steps;
this file expands each step into procedures and decision rules.

---

## Five Input Modes

Classify every user input into one of these modes before doing anything else.

### Mode 1: `new` — create a forecast

Triggers: user expresses anxiety, asks "will X happen", "should I", "how likely",
or names a future event of personal/professional consequence.

Required outputs:

1. Echo back the raw question.
2. If vague or cloud-like, run Gate 1–3 (see below).
3. Run `python scripts/sf.py new "<raw question>"` to allocate an id.
4. Run `sf scope <id> --canonical "..." --resolution-date YYYY-MM-DD --criterion "..."`.
5. (Optional) `sf decompose <id> -s "subq1|0.65" -s "subq2|0.7"` if Fermi-ized.
6. `sf set-prob <id> --p 0.62 --range 0.55 0.68 --ref-broad "..." --ref-medium "..." --ref-narrow "..." --ref-primary medium --base-rate 0.45 --base-rate-confidence medium --base-rate-reason "..." --up "factor|+5pp to +10pp" --down "factor|-3pp to -5pp" --reason "..."`.
7. `sf why-wrong <id> -r "..." -r "..."` — at least one reverse-side reason (Card §10).
8. `sf triggers <id> --up "..." --down "..." --next-review YYYY-MM-DD` — forward-looking triggers (Card §11).
9. (Decision-shaped only) `sf decision <id> --pause-below 0.55 --test-between 0.55 0.70 --act-above 0.70 --reason "..."` — thresholds (Card §12).
10. `sf render <id>` to produce the markdown card.
11. Read the rendered card path back to the user and ask if anything should be
    adjusted before activating.

### Mode 2: `update` — update an existing forecast

Triggers: user references a forecast id (`sf-2026-NNN`), or says "the situation
has changed", "new evidence", "I just learned X".

Required outputs:

1. Identify the forecast id (ask if ambiguous).
2. Read current probability via `sf show <id>`.
3. Classify evidence direction (upward / downward / neutral) and strength
   (strong / moderate / weak — see scoring.md).
4. Propose a new probability with reasoning grounded in the strength bucket.
5. Run `sf update <id> --evidence "..." --p <new_p> --strength <bucket>`.
6. Re-render the card if the user wants the updated card.

### Mode 3: `settle` — record final outcome

Triggers: user says "it happened", "it didn't happen", "settle sf-XXX", or the
resolution date has passed.

Required outputs:

1. Confirm the canonical question has resolved unambiguously.
2. Run `sf settle <id> --outcome 0` or `--outcome 1`. The script auto-scores.
3. Show the Brier Score and a one-sentence learning note (avoid blame; focus on
   what evidence was missed or overweighted).

### Mode 4: `review` — calibration retrospective

Triggers: "review my forecasts", "how am I doing", "calibration check", end of
month/quarter.

Required outputs:

1. Run `sf review --recent 20` (or `--since YYYY-MM-DD`).
2. Read the report file and translate it into 3–5 plain-language observations.
3. Highlight the largest gaps between predicted and observed rates per band.
4. Suggest one concrete behavior change for the next batch of forecasts.

### Mode 5: `coach` — concept teaching

Triggers: user asks "what is X", "how do I do Y", "teach me", or seems stuck on
a concept (Fermi-ization, reference class, base rate).

Required outputs:

- Walk through the concept using the user's own example.
- Do NOT write to the ledger unless the user explicitly says "save this".
- Reference superforecasting_concepts.md for definitions; reference examples.md
  for worked cases.

---

## Eight Gates (apply within Mode 1)

Run these in order. Each gate is a yes/no decision that shapes the next step.

### Gate 1: Forecast, decision, or emotion?

- **Anxiety** ("I'm worried that...") → reframe as a forecast first, then return
  to the emotional content separately.
- **Should-I question** → split into multiple forecasts + a decision threshold.
- **Why-question** → may not be a forecast at all; offer to discuss explanation
  vs. prediction.

### Gate 2: Is it resolvable?

A question is resolvable if a third party could read it on the resolution date
and unambiguously declare YES or NO. If not, rewrite. Common rewrites:

| Vague | Resolvable |
|---|---|
| "Will users like this feature?" | "Will week-1 retention exceed 35% by 2026-08-01?" |
| "Will I be happy in Guangzhou?" | "After 4 months in Guangzhou, will my self-reported life satisfaction be ≥7/10?" |
| "Will the deal close?" | "Will the contract be countersigned before 2026-06-30?" |

### Gate 3: Cloud-like? Needs Fermi-ization?

Trigger words for cloud-like: 幸福、成功、喜欢、脱钩、崩盘、变好、有前途、会火、
关系会不会好、能不能卷出来 (and English equivalents: succeed, work out, take off,
go well, be happy, be a hit). Default: Fermi-ize into 3–7 concrete sub-forecasts.

### Gate 4: Forecast type?

Default to `binary` (easiest to settle and score). Use:

- `multi_outcome` only when the outcome space has 3–5 mutually exclusive states
  with non-trivial probabilities each.
- `numeric` for "what value" questions where bands matter (e.g. MRR median).
- `decision_bundle` for "should I" questions that need multiple supporting
  forecasts and a decision threshold.

### Gate 5: Reference class

Always produce three layers — broad / medium / narrow — and choose `medium` as
primary unless you have explicit reason to prefer broad (small-narrow-sample) or
narrow (highly specific situation with rich data).

### Gate 6: Base rate (external view first)

State the base rate from the primary reference class BEFORE introducing any
internal-view facts. Resist the urge to immediately personalize.

### Gate 7: Internal view adjustments

List upward and downward factors separately. Each factor gets an estimated
impact band (e.g. `+5% to +10%`). Sum the midpoints to get the adjusted
probability. The probability range should reflect the spread of the sums.

### Gate 8: Forecast vs. decision

Forecast answers: *what is the probability?*
Decision answers: *given the probability and the costs, do I act?*

Always emit both when the user's input is decision-shaped:

```
decision_threshold:
  act_if_above: 0.70
  test_if_between: [0.55, 0.70]
  pause_if_below: 0.55
```

The thresholds depend on action cost, reversibility, and downside size — not on
the probability alone. Document the reasoning.

---

## Script Boundary

| The agent (LLM) does | The script (sf.py) does |
|---|---|
| Choose reference classes | Validate id format, dates, probability ranges |
| Fermi-ize cloud questions | Persist events to events.jsonl |
| Judge evidence strength | Enforce state machine transitions |
| Decide final probability | Compute Brier Score |
| Write narrative reasoning | Render markdown card |
| Set decision thresholds | Aggregate calibration report |

If a step requires semantic judgment, do NOT delegate to the script. If a step
requires deterministic field validation or persistence, do NOT do it inline in
the prompt — call the script.

---

## State Machine (mirrors sf.py)

```
DRAFT → SCOPED → ACTIVE → UPDATED* → SETTLED → SCORED
              ↘ DECOMPOSED (optional, doesn't change main state)
```

A forecast must reach SCOPED before `set-prob`, and ACTIVE before `update` or
`settle`. The script will reject illegal transitions with a clear error
message — read it and fix the workflow rather than retrying.
