#!/usr/bin/env python3
"""sf — Superforecasting deterministic engine.

Persists forecast events, validates state transitions, computes Brier Score,
renders forecast cards. Does NOT make semantic judgments (reference class
selection, evidence weighting, final probability decisions) — those belong to
the LLM agent.

Ledger lives at ~/.superforecast/ and is shared across all projects.
Zero external dependencies (Python 3.10+ standard library only).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LEDGER_DIR = Path.home() / ".superforecast"
EVENTS_FILE = LEDGER_DIR / "forecasts" / "events.jsonl"
ACTIVE_FILE = LEDGER_DIR / "forecasts" / "active.json"
RENDERED_DIR = LEDGER_DIR / "forecasts" / "rendered"
REPORTS_DIR = LEDGER_DIR / "reports"

STATE_DRAFT = "DRAFT"
STATE_SCOPED = "SCOPED"
STATE_ACTIVE = "ACTIVE"
STATE_UPDATED = "UPDATED"
STATE_SETTLED = "SETTLED"
STATE_SCORED = "SCORED"
STATE_REVIEWED = "REVIEWED"

TRANSITIONS = {
    "forecast_created": {"from": [None], "to": STATE_DRAFT},
    "question_scoped": {"from": [STATE_DRAFT, STATE_SCOPED], "to": STATE_SCOPED},
    "decomposed": {"from": [STATE_SCOPED, STATE_ACTIVE, STATE_UPDATED], "to": None},
    "probability_set": {"from": [STATE_SCOPED, STATE_ACTIVE, STATE_UPDATED], "to": STATE_ACTIVE},
    "evidence_update": {"from": [STATE_ACTIVE, STATE_UPDATED], "to": STATE_UPDATED},
    "settled": {"from": [STATE_ACTIVE, STATE_UPDATED], "to": STATE_SETTLED},
    "scored": {"from": [STATE_SETTLED, STATE_SCORED], "to": STATE_SCORED},
}


# ---- ledger I/O ----

def ensure_ledger() -> None:
    RENDERED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (LEDGER_DIR / "forecasts").mkdir(parents=True, exist_ok=True)
    if not EVENTS_FILE.exists():
        EVENTS_FILE.touch()
    if not ACTIVE_FILE.exists():
        ACTIVE_FILE.write_text("{}\n")


def load_active() -> dict:
    ensure_ledger()
    raw = ACTIVE_FILE.read_text().strip() or "{}"
    return json.loads(raw)


def save_active(active: dict) -> None:
    ACTIVE_FILE.write_text(json.dumps(active, ensure_ascii=False, indent=2) + "\n")


def load_events() -> list:
    ensure_ledger()
    out = []
    for line in EVENTS_FILE.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def append_event(event: dict) -> None:
    ensure_ledger()
    with EVENTS_FILE.open("a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# ---- helpers ----

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def die(msg: str, code: int = 1) -> None:
    print(f"sf: error: {msg}", file=sys.stderr)
    sys.exit(code)


def validate_id(forecast_id: str) -> None:
    if not re.match(r"^sf-\d{4}-\d{3,}$", forecast_id):
        die(f"invalid forecast id: {forecast_id!r}. Expected format sf-YYYY-NNN")


def validate_date(date_str: str, field: str = "date") -> None:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        die(f"invalid {field}: {date_str!r}. Expected YYYY-MM-DD")


def validate_probability(p: float, field: str = "p") -> None:
    if not (0.0 <= p <= 1.0):
        die(f"invalid {field}: {p}. Must be between 0 and 1.")


def validate_range(low: float, high: float) -> None:
    validate_probability(low, "range[0]")
    validate_probability(high, "range[1]")
    if low > high:
        die(f"invalid range: [{low}, {high}]. Lower bound must be <= upper bound.")


def next_id() -> str:
    year = datetime.now().year
    prefix = f"sf-{year}-"
    seen = set()
    for fid in load_active().keys():
        if fid.startswith(prefix):
            seen.add(fid)
    for ev in load_events():
        fid = ev.get("id", "")
        if fid.startswith(prefix):
            seen.add(fid)
    return f"{prefix}{len(seen) + 1:03d}"


def get_forecast(forecast_id: str) -> dict:
    active = load_active()
    if forecast_id not in active:
        die(f"forecast not found: {forecast_id}. Run `sf list` to see available ids.")
    return active[forecast_id]


def transition(forecast_id: str, event_type: str) -> dict:
    """Validate state transition; return current snapshot (may be empty)."""
    snapshot = load_active().get(forecast_id, {})
    current_state = snapshot.get("state")
    rule = TRANSITIONS[event_type]
    if current_state not in rule["from"]:
        die(
            f"illegal transition: {forecast_id} is in state {current_state!r}, "
            f"cannot apply event {event_type!r} (allowed source states: {rule['from']})"
        )
    return snapshot


def update_active(forecast_id: str, event_type: str, **fields) -> None:
    active = load_active()
    snapshot = active.get(forecast_id, {"id": forecast_id})
    rule = TRANSITIONS[event_type]
    if rule["to"] is not None:
        snapshot["state"] = rule["to"]
    for k, v in fields.items():
        if v is not None:
            snapshot[k] = v
    snapshot["updated_at"] = now_iso()
    active[forecast_id] = snapshot
    save_active(active)


# ---- commands ----

def cmd_new(args) -> None:
    raw = args.question.strip()
    if not raw:
        die("question must not be empty")
    forecast_id = next_id()
    timestamp = now_iso()
    transition(forecast_id, "forecast_created")
    append_event({
        "type": "forecast_created",
        "id": forecast_id,
        "timestamp": timestamp,
        "raw_question": raw,
    })
    update_active(forecast_id, "forecast_created", raw_question=raw, created_at=timestamp)
    print(forecast_id)


def cmd_scope(args) -> None:
    validate_id(args.id)
    validate_date(args.resolution_date, "resolution-date")
    transition(args.id, "question_scoped")
    event = {
        "type": "question_scoped",
        "id": args.id,
        "timestamp": now_iso(),
        "canonical_question": args.canonical,
        "outcome_type": args.outcome_type,
        "resolution_date": args.resolution_date,
        "settlement_criterion": args.criterion,
    }
    if args.data_source:
        event["data_source"] = args.data_source
    append_event(event)
    update_active(
        args.id, "question_scoped",
        canonical_question=args.canonical,
        outcome_type=args.outcome_type,
        resolution_date=args.resolution_date,
        settlement_criterion=args.criterion,
        data_source=args.data_source,
    )
    print(f"scoped {args.id}: {args.canonical} (resolves {args.resolution_date})")


def cmd_decompose(args) -> None:
    validate_id(args.id)
    if not args.subquestion:
        die("at least one --subquestion required")
    subs = []
    for sq in args.subquestion:
        parts = sq.rsplit("|", 1)
        entry = {"question": parts[0].strip()}
        if len(parts) == 2:
            try:
                p = float(parts[1])
            except ValueError:
                die(f"invalid sub-question probability: {parts[1]!r}")
            validate_probability(p, "sub-question probability")
            entry["probability"] = p
        subs.append(entry)
    transition(args.id, "decomposed")
    append_event({
        "type": "decomposed",
        "id": args.id,
        "timestamp": now_iso(),
        "subquestions": subs,
    })
    update_active(args.id, "decomposed", subquestions=subs)
    print(f"decomposed {args.id} into {len(subs)} sub-questions")


def cmd_set_prob(args) -> None:
    validate_id(args.id)
    validate_probability(args.p, "p")
    if len(args.range) != 2:
        die("--range must take exactly 2 values: LOW HIGH")
    low, high = args.range
    validate_range(low, high)
    transition(args.id, "probability_set")
    event = {
        "type": "probability_set",
        "id": args.id,
        "timestamp": now_iso(),
        "p": args.p,
        "range": [low, high],
        "reason": args.reason,
    }
    if args.reference_class:
        event["reference_class"] = args.reference_class
    if args.base_rate is not None:
        validate_probability(args.base_rate, "base-rate")
        event["base_rate"] = args.base_rate
    append_event(event)
    update_active(
        args.id, "probability_set",
        current_probability=args.p,
        probability_range=[low, high],
        reference_class=args.reference_class,
        base_rate=args.base_rate,
    )
    print(f"{args.id}: p = {args.p} (range {low}–{high})")


def cmd_update(args) -> None:
    validate_id(args.id)
    validate_probability(args.p, "p")
    snapshot = transition(args.id, "evidence_update")
    p_from = snapshot.get("current_probability")
    if p_from is None:
        die(f"{args.id} has no current probability; run `sf set-prob` first")
    new_range = None
    if args.range:
        if len(args.range) != 2:
            die("--range must take exactly 2 values: LOW HIGH")
        validate_range(args.range[0], args.range[1])
        new_range = [args.range[0], args.range[1]]
    if args.p > p_from:
        direction = "upward"
    elif args.p < p_from:
        direction = "downward"
    else:
        direction = "neutral"
    event = {
        "type": "evidence_update",
        "id": args.id,
        "timestamp": now_iso(),
        "p_from": p_from,
        "p_to": args.p,
        "evidence": args.evidence,
        "direction": direction,
    }
    if args.strength:
        event["strength"] = args.strength
    if new_range:
        event["new_range"] = new_range
    append_event(event)
    fields = {"current_probability": args.p}
    if new_range:
        fields["probability_range"] = new_range
    update_active(args.id, "evidence_update", **fields)
    print(f"{args.id}: p {p_from} → {args.p} ({direction})")


def cmd_settle(args) -> None:
    validate_id(args.id)
    if args.outcome not in (0, 1):
        die("--outcome must be 0 or 1")
    snapshot = transition(args.id, "settled")
    final_p = snapshot.get("current_probability")
    if final_p is None:
        die(f"{args.id} has no probability set; cannot settle")
    timestamp = now_iso()
    append_event({
        "type": "settled",
        "id": args.id,
        "timestamp": timestamp,
        "outcome": args.outcome,
        "final_probability": final_p,
    })
    update_active(
        args.id, "settled",
        outcome=args.outcome,
        final_probability=final_p,
        settled_at=timestamp,
    )
    transition(args.id, "scored")
    brier = round((final_p - args.outcome) ** 2, 6)
    append_event({
        "type": "scored",
        "id": args.id,
        "timestamp": now_iso(),
        "brier": brier,
        "outcome": args.outcome,
        "final_probability": final_p,
    })
    update_active(args.id, "scored", brier=brier)
    print(f"{args.id}: outcome={args.outcome}, final_p={final_p}, Brier={brier}")


def cmd_score(args) -> None:
    """Recompute Brier (read-only, idempotent diagnostic)."""
    validate_id(args.id)
    snapshot = get_forecast(args.id)
    outcome = snapshot.get("outcome")
    final_p = snapshot.get("final_probability")
    if outcome is None or final_p is None:
        die(f"{args.id} is not settled yet; run `sf settle` first")
    brier = round((final_p - outcome) ** 2, 6)
    print(f"{args.id}: Brier = {brier} (final_p={final_p}, outcome={outcome})")


def cmd_render(args) -> None:
    validate_id(args.id)
    snapshot = get_forecast(args.id)
    events = [e for e in load_events() if e.get("id") == args.id]
    md = render_card(snapshot, events)
    out_path = RENDERED_DIR / f"{args.id}.md"
    out_path.write_text(md)
    print(f"wrote {out_path}")


def render_card(snapshot: dict, events: list) -> str:
    lines = []
    fid = snapshot.get("id", "?")
    lines.append(f"# Superforecasting Forecast Card · {fid}")
    lines.append("")
    lines.append(f"- **State**: {snapshot.get('state', 'UNKNOWN')}")
    lines.append(f"- **Created**: {snapshot.get('created_at', '—')}")
    lines.append(f"- **Resolution date**: {snapshot.get('resolution_date', '—')}")
    lines.append("")

    lines.append("## 1. Original Question")
    lines.append(snapshot.get("raw_question", "—"))
    lines.append("")

    lines.append("## 2. Resolvable Question")
    lines.append(snapshot.get("canonical_question") or "_(not yet scoped)_")
    lines.append("")

    lines.append("## 3. Settlement Criterion")
    lines.append(snapshot.get("settlement_criterion") or "—")
    if snapshot.get("data_source"):
        lines.append("")
        lines.append(f"*Data source: {snapshot['data_source']}*")
    lines.append("")

    lines.append("## 4. Forecast Type")
    lines.append(snapshot.get("outcome_type") or "—")
    lines.append("")

    lines.append("## 5. Fermi-ized Sub-questions")
    subs = snapshot.get("subquestions") or []
    if subs:
        for s in subs:
            p = s.get("probability")
            p_str = f" — p={p}" if p is not None else ""
            lines.append(f"- {s['question']}{p_str}")
    else:
        lines.append("_(none)_")
    lines.append("")

    lines.append("## 6. Reference Class")
    lines.append(snapshot.get("reference_class") or "_(not recorded)_")
    lines.append("")

    lines.append("## 7. Base Rate")
    br = snapshot.get("base_rate")
    lines.append(str(br) if br is not None else "_(not recorded)_")
    lines.append("")

    lines.append("## 8. Current Probability")
    p = snapshot.get("current_probability")
    rng = snapshot.get("probability_range")
    if p is not None:
        if rng and rng[0] <= p <= rng[1]:
            rng_str = f" (range {rng[0]}–{rng[1]})"
        elif rng:
            rng_str = f" _(initial range was {rng[0]}–{rng[1]}; current p has moved outside it)_"
        else:
            rng_str = ""
        lines.append(f"**{p}**{rng_str}")
    else:
        lines.append("_(not estimated)_")
    lines.append("")

    lines.append("## 9. Evidence Updates")
    updates = [e for e in events if e["type"] == "evidence_update"]
    if updates:
        for ev in updates:
            lines.append(
                f"- {ev['timestamp'][:10]}: {ev['p_from']} → {ev['p_to']} "
                f"({ev.get('direction', 'neutral')}) — {ev['evidence']}"
            )
    else:
        lines.append("_(no updates)_")
    lines.append("")

    lines.append("## 10. Settlement & Scoring")
    if snapshot.get("outcome") is not None:
        lines.append(f"- Outcome: **{snapshot['outcome']}**")
        lines.append(f"- Final probability: {snapshot.get('final_probability')}")
        lines.append(f"- Brier Score: **{snapshot.get('brier')}**")
        lines.append(f"- Settled at: {snapshot.get('settled_at')}")
    else:
        lines.append("_(not settled)_")
    lines.append("")

    lines.append("## 11. Event Log")
    lines.append("```")
    for ev in events:
        lines.append(json.dumps(ev, ensure_ascii=False))
    lines.append("```")

    return "\n".join(lines) + "\n"


def cmd_review(args) -> None:
    events = load_events()
    scored_events = [e for e in events if e["type"] == "scored"]
    if args.recent:
        scored_events = scored_events[-args.recent:]
    elif args.since:
        validate_date(args.since, "since")
        scored_events = [
            e for e in scored_events
            if e["timestamp"][:10] >= args.since
        ]
    if not scored_events:
        die("no scored forecasts found in scope")

    n = len(scored_events)
    avg_brier = sum(e["brier"] for e in scored_events) / n

    buckets = [
        (0.0, 0.2, [], "<20%"),
        (0.2, 0.4, [], "20–40%"),
        (0.4, 0.6, [], "40–60%"),
        (0.6, 0.8, [], "60–80%"),
        (0.8, 1.01, [], "≥80%"),
    ]
    for ev in scored_events:
        p = ev["final_probability"]
        outcome = ev["outcome"]
        for low, high, items, _ in buckets:
            if low <= p < high:
                items.append((p, outcome))
                break

    calibration_lines = []
    resolution_lines = []
    for low, high, items, label in buckets:
        if not items:
            continue
        n_b = len(items)
        avg_p = sum(p for p, _ in items) / n_b
        observed_rate = sum(o for _, o in items) / n_b
        gap = round(observed_rate - avg_p, 3)
        calibration_lines.append(
            f"- {label}: predicted avg={avg_p:.2f}, observed={observed_rate:.2f}, "
            f"gap={gap:+.2f} (n={n_b})"
        )
        if low <= 0.5 < high and n >= 4 and n_b / n >= 0.4:
            resolution_lines.append(
                f"- {n_b}/{n} predictions in {label} band — possible 'fence-sitting'"
            )

    timestamp = now_iso()
    scope_str = (
        f"recent {args.recent}" if args.recent
        else (f"since {args.since}" if args.since else "all")
    )

    report_lines = [
        f"# Calibration Review · {timestamp[:10]}",
        "",
        f"- **Scope**: {scope_str}",
        f"- **Forecasts**: {n}",
        f"- **Average Brier Score**: {avg_brier:.4f}",
        "",
        "## Calibration by probability band",
    ]
    report_lines.extend(calibration_lines or ["_(no data)_"])
    report_lines.append("")
    report_lines.append("## Resolution notes")
    report_lines.extend(resolution_lines or ["_(no fence-sitting detected)_"])
    report_lines.append("")
    report_lines.append("## Settled forecasts in scope")
    for ev in scored_events:
        report_lines.append(
            f"- {ev['id']} · p={ev['final_probability']} · "
            f"outcome={ev['outcome']} · Brier={ev['brier']}"
        )

    out_path = REPORTS_DIR / f"calibration_{timestamp[:10].replace('-', '')}.md"
    out_path.write_text("\n".join(report_lines) + "\n")
    print(f"wrote {out_path}")
    print(f"average Brier: {avg_brier:.4f} over {n} forecasts")


def cmd_list(args) -> None:
    active = load_active()
    items = list(active.values())
    if args.active:
        items = [s for s in items if s.get("state") in (STATE_ACTIVE, STATE_UPDATED)]
    elif args.settled:
        items = [s for s in items if s.get("state") in (STATE_SETTLED, STATE_SCORED, STATE_REVIEWED)]
    if not items:
        print("(no forecasts)")
        return
    for s in sorted(items, key=lambda x: x["id"]):
        p = s.get("current_probability", "—")
        rd = s.get("resolution_date", "—")
        state = s.get("state", "?")
        q = s.get("canonical_question") or s.get("raw_question", "")
        if len(q) > 60:
            q = q[:57] + "..."
        print(f"{s['id']}  [{state:<8}]  p={p}  resolves={rd}  {q}")


def cmd_show(args) -> None:
    validate_id(args.id)
    snapshot = get_forecast(args.id)
    events = [e for e in load_events() if e.get("id") == args.id]
    print(json.dumps({"snapshot": snapshot, "events": events}, ensure_ascii=False, indent=2))


# ---- argparse wiring ----

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sf",
        description=(
            "Superforecasting deterministic engine. "
            "Persists events, validates state, computes Brier Score."
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("new", help="register a new raw question")
    sp.add_argument("question")
    sp.set_defaults(fn=cmd_new)

    sp = sub.add_parser("scope", help="rewrite into a resolvable question")
    sp.add_argument("id")
    sp.add_argument("--canonical", required=True)
    sp.add_argument("--resolution-date", required=True, help="YYYY-MM-DD")
    sp.add_argument("--criterion", required=True)
    sp.add_argument(
        "--outcome-type", default="binary",
        choices=["binary", "multi_outcome", "numeric", "decision_bundle"],
    )
    sp.add_argument("--data-source", default=None)
    sp.set_defaults(fn=cmd_scope)

    sp = sub.add_parser("decompose", help="record Fermi-ized sub-questions")
    sp.add_argument("id")
    sp.add_argument(
        "--subquestion", "-s", action="append",
        help="sub-question text, optional |PROB suffix (e.g. 'find job in 3mo|0.65')",
    )
    sp.set_defaults(fn=cmd_decompose)

    sp = sub.add_parser("set-prob", help="set current probability with reasoning")
    sp.add_argument("id")
    sp.add_argument("--p", type=float, required=True)
    sp.add_argument("--range", type=float, nargs=2, required=True, metavar=("LOW", "HIGH"))
    sp.add_argument("--reason", required=True)
    sp.add_argument("--reference-class", default=None)
    sp.add_argument("--base-rate", type=float, default=None)
    sp.set_defaults(fn=cmd_set_prob)

    sp = sub.add_parser("update", help="update probability with new evidence")
    sp.add_argument("id")
    sp.add_argument("--evidence", required=True)
    sp.add_argument("--p", type=float, required=True)
    sp.add_argument("--range", type=float, nargs=2, default=None, metavar=("LOW", "HIGH"),
                    help="optionally widen/narrow the probability range alongside the update")
    sp.add_argument("--strength", choices=["strong", "moderate", "weak"], default=None)
    sp.set_defaults(fn=cmd_update)

    sp = sub.add_parser("settle", help="settle a binary forecast and score it")
    sp.add_argument("id")
    sp.add_argument("--outcome", type=int, required=True, choices=[0, 1])
    sp.set_defaults(fn=cmd_settle)

    sp = sub.add_parser("score", help="recompute Brier Score (diagnostic)")
    sp.add_argument("id")
    sp.set_defaults(fn=cmd_score)

    sp = sub.add_parser("render", help="render markdown forecast card")
    sp.add_argument("id")
    sp.set_defaults(fn=cmd_render)

    sp = sub.add_parser("review", help="aggregate calibration report")
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--recent", type=int, help="last N settled forecasts")
    g.add_argument("--since", help="YYYY-MM-DD")
    sp.set_defaults(fn=cmd_review)

    sp = sub.add_parser("list", help="list forecasts")
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--active", action="store_true")
    g.add_argument("--settled", action="store_true")
    sp.set_defaults(fn=cmd_list)

    sp = sub.add_parser("show", help="dump a forecast's full event log")
    sp.add_argument("id")
    sp.set_defaults(fn=cmd_show)

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
