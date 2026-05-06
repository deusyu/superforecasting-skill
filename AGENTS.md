# AGENTS.md

## Project

superforecasting-skill is a Codex / Claude Code Skill that turns vague concerns, decisions, and forecasts into resolvable, updatable, Brier-scored probabilistic predictions. Published on GitHub as `deusyu/superforecasting-skill`.

## Structure

- `SKILL.md` — Skill definition, the orchestration logic that Codex / Claude Code / OpenClaw follows
- `scripts/sf.py` — Zero-dependency Python CLI engine: state machine, ID/date/probability validation, Brier scoring, Markdown card rendering, calibration aggregation
- `references/workflow.md` — Five input modes + eight gates in operational detail
- `references/superforecasting_concepts.md` — Terminology and principles glossary
- `references/examples.md` — Six worked cases (life decision, product, business risk, exam, update flow, settlement)
- `references/scoring.md` — Brier interpretation, calibration bands, evidence-strength buckets
- `schemas/forecast_event.schema.json` — `events.jsonl` line format (8 event types, oneOf discriminator on `type`)
- `schemas/forecast_card.schema.json` — `sf render` input format (14-section card)
- `docs/skill_design.md` — Original design rationale (background reading, Chinese)
- `docs/concept_understanding.md` — Conceptual foundation (background reading, Chinese)

## Testing changes

Use a throwaway forecast against the global ledger to verify the full pipeline:

```bash
SF=scripts/sf.py
ID=$(python3 $SF new "smoke test")
python3 $SF scope $ID \
    --canonical "By 2099-12-31, will the smoke test resolve YES?" \
    --resolution-date 2099-12-31 \
    --criterion "test marker"
python3 $SF set-prob $ID --p 0.50 --range 0.40 0.60 --reason "smoke"
python3 $SF update $ID --evidence "test evidence" --p 0.65 --strength moderate
python3 $SF settle $ID --outcome 1
python3 $SF render $ID
python3 $SF list
python3 $SF review --recent 1
```

Verify: state machine accepts the legal sequence, rejects illegal transitions, Brier computed correctly (`(0.65 - 1)² = 0.1225`), markdown card renders to `~/.superforecast/forecasts/rendered/<id>.md`, calibration report written to `~/.superforecast/reports/calibration_YYYYMMDD.md`.

To clean test data afterward, edit `~/.superforecast/forecasts/events.jsonl` and `active.json` directly, or rebuild from scratch:

```bash
> ~/.superforecast/forecasts/events.jsonl
echo '{}' > ~/.superforecast/forecasts/active.json
rm -f ~/.superforecast/forecasts/rendered/*.md
rm -f ~/.superforecast/reports/*.md
```

## Conventions

- ID format `sf-YYYY-NNN` only — no other naming schemes
- `events.jsonl` is the single source of truth — `active.json` and rendered cards are derived and disposable
- SKILL.md frontmatter must stay single-line per field (OpenClaw parser requirement)
- Script paths in SKILL.md use `{baseDir}/scripts/sf.py`, not hardcoded `~/.claude/...` or `~/.codex/...`
- Subagent instructions in SKILL.md must be platform-neutral (work on Codex, Claude Code, OpenClaw)
- README changes must be synced to both README.md and README.zh-CN.md
- The state machine `DRAFT → SCOPED → ACTIVE → UPDATED* → SETTLED → SCORED` is canonical; any new event type must declare its allowed source states in `sf.py`'s `TRANSITIONS` table
- Brier Score is for binary forecasts only; non-binary types live in the ledger but get reviewed qualitatively
- The script is the single writer to the ledger — agent never hand-edits `events.jsonl` or `active.json`

## Do not

- Do not introduce platform-specific tool names (Agent, sessions_spawn, etc.) in `allowed-tools` as the only option — keep the whitelist cross-platform
- Do not hardcode `~/.claude/skills/superforecast/...` or `~/.codex/skills/superforecast/...` paths in SKILL.md — use `{baseDir}` so the skill works regardless of installation location
- Do not add `pip install` dependencies to `sf.py` — zero-dependency Python 3.10+ standard library is a hard project constraint (it's why install is one `git clone`)
- Do not bypass the state machine. If a workflow seems to need an illegal transition, the workflow is wrong, not the state machine. The two most common smells are "let me just edit the ledger to fix X" (no — fix the upstream agent prompt) and "let me re-scope a settled forecast" (no — settle it 0 and create a new one)
- Do not write `Co-Authored-By` trailers in commits (per global git conventions)
- Do not personalize examples in `references/examples.md` with anything that could leak personal information; keep them abstract (Guangzhou move, product retention, etc.)
- Do not auto-score multi_outcome / numeric / decision_bundle forecasts — the script will refuse, and that's intentional
