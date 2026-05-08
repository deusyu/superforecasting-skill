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

SIDE_BRANCH_STATES = [STATE_SCOPED, STATE_ACTIVE, STATE_UPDATED]

TRANSITIONS = {
    "forecast_created": {"from": [None], "to": STATE_DRAFT},
    "question_scoped": {"from": [STATE_DRAFT, STATE_SCOPED], "to": STATE_SCOPED},
    "decomposed": {"from": SIDE_BRANCH_STATES, "to": None},
    "probability_set": {"from": SIDE_BRANCH_STATES, "to": STATE_ACTIVE},
    "evidence_update": {"from": [STATE_ACTIVE, STATE_UPDATED], "to": STATE_UPDATED},
    "why_wrong_set": {"from": SIDE_BRANCH_STATES, "to": None},
    "update_triggers_set": {"from": SIDE_BRANCH_STATES, "to": None},
    "decision_threshold_set": {"from": SIDE_BRANCH_STATES, "to": None},
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


def validate_any_id(some_id: str) -> None:
    """Accept both forecast ids (sf-*) and review ids (review-*)."""
    if not re.match(r"^(sf|review)-\d{4}-\d{3,}$", some_id):
        die(f"invalid id: {some_id!r}. Expected sf-YYYY-NNN or review-YYYY-NNN")


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


def validate_p_in_range(p: float, low: float, high: float, p_field: str = "p") -> None:
    if not (low <= p <= high):
        die(
            f"incoherent {p_field}={p} for range [{low}, {high}]: {p_field} must lie inside the range. "
            f"Either widen --range, or correct --{p_field}."
        )


def _max_suffix(ids: list, prefix: str) -> int:
    """Return max numeric suffix among ids matching '<prefix>NNN'; 0 if none."""
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    best = 0
    for s in ids:
        m = pattern.match(s)
        if m:
            best = max(best, int(m.group(1)))
    return best


def next_id() -> str:
    year = datetime.now().year
    prefix = f"sf-{year}-"
    candidates = list(load_active().keys()) + [ev.get("id", "") for ev in load_events()]
    return f"{prefix}{_max_suffix(candidates, prefix) + 1:03d}"


def next_review_id() -> str:
    year = datetime.now().year
    prefix = f"review-{year}-"
    candidates = [ev.get("id", "") for ev in load_events()]
    return f"{prefix}{_max_suffix(candidates, prefix) + 1:03d}"


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


DEFAULT_SCORING_METHOD = {
    "binary": "Brier Score",
    "numeric": "manual numeric scoring",
    "multi_outcome": "manual multi-class scoring",
    "decision_bundle": "settle supporting binary forecasts individually",
}


def cmd_scope(args) -> None:
    validate_id(args.id)
    validate_date(args.resolution_date, "resolution-date")
    scoring_method = args.scoring_method or DEFAULT_SCORING_METHOD.get(args.outcome_type, "—")
    transition(args.id, "question_scoped")
    event = {
        "type": "question_scoped",
        "id": args.id,
        "timestamp": now_iso(),
        "canonical_question": args.canonical,
        "outcome_type": args.outcome_type,
        "resolution_date": args.resolution_date,
        "settlement_criterion": args.criterion,
        "scoring_method": scoring_method,
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
        scoring_method=scoring_method,
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


def parse_factor_impact(items: list | None, flag: str) -> list:
    """Parse repeatable 'factor|impact' strings into structured entries."""
    if not items:
        return []
    out = []
    for raw in items:
        parts = raw.rsplit("|", 1)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            die(f"--{flag} expects 'factor|impact' (e.g. '--{flag} \"strong demand|+5% to +10%\"'), got: {raw!r}")
        out.append({"factor": parts[0].strip(), "impact": parts[1].strip()})
    return out


def cmd_set_prob(args) -> None:
    validate_id(args.id)
    validate_probability(args.p, "p")
    if len(args.range) != 2:
        die("--range must take exactly 2 values: LOW HIGH")
    low, high = args.range
    validate_range(low, high)
    validate_p_in_range(args.p, low, high)

    any_ref_input = any([args.ref_broad, args.ref_medium, args.ref_narrow, args.reference_class])
    if args.ref_primary and not any_ref_input:
        die(
            "--ref-primary requires at least one of --ref-broad / --ref-medium / --ref-narrow "
            "(or legacy --reference-class). Otherwise the primary points to nothing."
        )

    reference_classes = {}
    if args.ref_broad:
        reference_classes["broad"] = args.ref_broad
    if args.ref_medium:
        reference_classes["medium"] = args.ref_medium
    if args.ref_narrow:
        reference_classes["narrow"] = args.ref_narrow
    if args.reference_class and "medium" not in reference_classes:
        reference_classes["medium"] = args.reference_class
    if reference_classes:
        primary = args.ref_primary or ("medium" if "medium" in reference_classes else next(iter(reference_classes)))
        if primary not in reference_classes:
            die(f"--ref-primary={primary!r} but no --ref-{primary} was provided")
        reference_classes["primary"] = primary

    if (args.base_rate_confidence or args.base_rate_reason) and args.base_rate is None:
        die(
            "--base-rate-confidence and --base-rate-reason require --base-rate. "
            "Provide a numeric base rate or drop the metadata flags."
        )
    base_rate_obj = None
    if args.base_rate is not None:
        validate_probability(args.base_rate, "base-rate")
        base_rate_obj = {"probability": args.base_rate}
        if args.base_rate_confidence:
            base_rate_obj["confidence"] = args.base_rate_confidence
        if args.base_rate_reason:
            base_rate_obj["reason"] = args.base_rate_reason

    upward = parse_factor_impact(args.up, "up")
    downward = parse_factor_impact(args.down, "down")
    internal_adjustments = {}
    if upward:
        internal_adjustments["upward"] = upward
    if downward:
        internal_adjustments["downward"] = downward

    transition(args.id, "probability_set")
    event = {
        "type": "probability_set",
        "id": args.id,
        "timestamp": now_iso(),
        "p": args.p,
        "range": [low, high],
        "reason": args.reason,
    }
    if reference_classes:
        event["reference_classes"] = reference_classes
        event["reference_class"] = reference_classes.get(reference_classes["primary"])
    if base_rate_obj:
        event["base_rate"] = base_rate_obj
    if internal_adjustments:
        event["internal_adjustments"] = internal_adjustments
    append_event(event)

    fields = {
        "current_probability": args.p,
        "probability_range": [low, high],
    }
    if reference_classes:
        fields["reference_classes"] = reference_classes
        fields["reference_class"] = reference_classes.get(reference_classes["primary"])
    if base_rate_obj:
        fields["base_rate"] = base_rate_obj
    if internal_adjustments:
        fields["internal_adjustments"] = internal_adjustments
    update_active(args.id, "probability_set", **fields)
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
        validate_p_in_range(args.p, args.range[0], args.range[1])
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


def cmd_why_wrong(args) -> None:
    validate_id(args.id)
    if not args.reason:
        die("at least one --reason required")
    reasons = [r.strip() for r in args.reason if r.strip()]
    if not reasons:
        die("--reason values must be non-empty")
    transition(args.id, "why_wrong_set")
    append_event({
        "type": "why_wrong_set",
        "id": args.id,
        "timestamp": now_iso(),
        "why_this_might_be_wrong": reasons,
    })
    update_active(args.id, "why_wrong_set", why_this_might_be_wrong=reasons)
    print(f"{args.id}: recorded {len(reasons)} reverse-side reason(s)")


def cmd_triggers(args) -> None:
    validate_id(args.id)
    upward = [t.strip() for t in (args.up or []) if t.strip()]
    downward = [t.strip() for t in (args.down or []) if t.strip()]
    if not upward and not downward and not args.next_review:
        die("provide at least one of --up, --down, or --next-review")
    triggers = {}
    if upward:
        triggers["upward"] = upward
    if downward:
        triggers["downward"] = downward
    if args.next_review:
        validate_date(args.next_review, "next-review")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if args.next_review < today:
            die(f"--next-review={args.next_review} is in the past (today UTC: {today}).")
        snapshot = load_active().get(args.id, {})
        resolution = snapshot.get("resolution_date")
        if resolution and args.next_review > resolution:
            die(
                f"--next-review={args.next_review} is after resolution_date={resolution}; "
                f"by then the forecast should be settled, not reviewed."
            )
        triggers["next_review_date"] = args.next_review
    transition(args.id, "update_triggers_set")
    append_event({
        "type": "update_triggers_set",
        "id": args.id,
        "timestamp": now_iso(),
        "update_triggers": triggers,
    })
    update_active(args.id, "update_triggers_set", update_triggers=triggers)
    desc = []
    if upward:
        desc.append(f"{len(upward)} upward")
    if downward:
        desc.append(f"{len(downward)} downward")
    if args.next_review:
        desc.append(f"next review {args.next_review}")
    print(f"{args.id}: triggers — {', '.join(desc)}")


def cmd_decision(args) -> None:
    validate_id(args.id)
    threshold = {}
    if args.act_above is not None:
        validate_probability(args.act_above, "act-above")
        threshold["act_if_above"] = args.act_above
    if args.test_between is not None:
        if len(args.test_between) != 2:
            die("--test-between must take exactly 2 values: LOW HIGH")
        validate_range(args.test_between[0], args.test_between[1])
        threshold["test_if_between"] = list(args.test_between)
    if args.pause_below is not None:
        validate_probability(args.pause_below, "pause-below")
        threshold["pause_if_below"] = args.pause_below
    if not threshold:
        die("provide at least one of --act-above, --test-between, --pause-below")

    anchors = []
    if "pause_if_below" in threshold:
        anchors.append(("pause_if_below", threshold["pause_if_below"]))
    if "test_if_between" in threshold:
        low, high = threshold["test_if_between"]
        anchors.append(("test_if_between[0]", low))
        anchors.append(("test_if_between[1]", high))
    if "act_if_above" in threshold:
        anchors.append(("act_if_above", threshold["act_if_above"]))
    for (name_a, val_a), (name_b, val_b) in zip(anchors, anchors[1:]):
        if val_a > val_b:
            die(
                f"decision thresholds overlap: {name_a}={val_a} must be <= {name_b}={val_b}. "
                f"Required ordering: pause_if_below <= test_if_between[0] <= test_if_between[1] <= act_if_above."
            )

    if args.reason:
        threshold["reason"] = args.reason
    transition(args.id, "decision_threshold_set")
    append_event({
        "type": "decision_threshold_set",
        "id": args.id,
        "timestamp": now_iso(),
        "decision_threshold": threshold,
    })
    update_active(args.id, "decision_threshold_set", decision_threshold=threshold)
    print(f"{args.id}: decision threshold recorded")


def cmd_settle(args) -> None:
    validate_id(args.id)
    if args.outcome not in (0, 1):
        die("--outcome must be 0 or 1")
    snapshot = transition(args.id, "settled")
    outcome_type = snapshot.get("outcome_type", "binary")
    if outcome_type != "binary":
        die(
            f"{args.id} has outcome_type={outcome_type!r}; `sf settle` only auto-scores binary forecasts. "
            f"For multi_outcome / numeric / decision_bundle, score manually per references/scoring.md "
            f"('When to NOT compute Brier'). Decision bundles should be split into binary sub-forecasts."
        )
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

    lines.append("## 6. Reference Class (broad / medium / narrow + primary)")
    rc = snapshot.get("reference_classes")
    if isinstance(rc, dict) and any(k in rc for k in ("broad", "medium", "narrow")):
        primary = rc.get("primary")
        for layer in ("broad", "medium", "narrow"):
            text = rc.get(layer)
            marker = " ← primary" if layer == primary else ""
            lines.append(f"- **{layer}**: {text or '_(not recorded)_'}{marker}")
    elif snapshot.get("reference_class"):
        lines.append(f"- **medium**: {snapshot['reference_class']} ← primary")
        lines.append("- **broad**: _(not recorded)_")
        lines.append("- **narrow**: _(not recorded)_")
    else:
        lines.append("_(not recorded)_")
    lines.append("")

    lines.append("## 7. Base Rate")
    br = snapshot.get("base_rate")
    if isinstance(br, dict):
        lines.append(f"- **Probability**: {br.get('probability', '—')}")
        if br.get("confidence"):
            lines.append(f"- **Confidence**: {br['confidence']}")
        if br.get("reason"):
            lines.append(f"- **Reason**: {br['reason']}")
    elif br is not None:
        lines.append(str(br))
    else:
        lines.append("_(not recorded)_")
    lines.append("")

    lines.append("## 8. Internal Adjustments (upward / downward with impact bands)")
    adj = snapshot.get("internal_adjustments") or {}
    upward = adj.get("upward") or []
    downward = adj.get("downward") or []
    if upward or downward:
        lines.append("**Upward**")
        if upward:
            for u in upward:
                lines.append(f"- {u['factor']} ({u['impact']})")
        else:
            lines.append("- _(none)_")
        lines.append("")
        lines.append("**Downward**")
        if downward:
            for d in downward:
                lines.append(f"- {d['factor']} ({d['impact']})")
        else:
            lines.append("- _(none)_")
    else:
        lines.append("_(not recorded)_")
    lines.append("")

    lines.append("## 9. Current Probability + Probability Range")
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

    lines.append("## 10. Why This Forecast Might Be Wrong")
    why = snapshot.get("why_this_might_be_wrong") or []
    if why:
        for r in why:
            lines.append(f"- {r}")
    else:
        lines.append("_(not recorded)_")
    lines.append("")

    lines.append("## 11. Update Triggers (upward / downward / next review date)")
    trig = snapshot.get("update_triggers") or {}
    trig_up = trig.get("upward") or []
    trig_down = trig.get("downward") or []
    next_review = trig.get("next_review_date")
    if trig_up or trig_down or next_review:
        if trig_up:
            lines.append("**Upward triggers**")
            for t in trig_up:
                lines.append(f"- {t}")
        if trig_down:
            lines.append("**Downward triggers**")
            for t in trig_down:
                lines.append(f"- {t}")
        if next_review:
            lines.append(f"**Next review**: {next_review}")
    else:
        lines.append("_(not recorded)_")
    lines.append("")

    lines.append("## 12. Decision Threshold")
    dt = snapshot.get("decision_threshold") or {}
    if dt:
        if dt.get("act_if_above") is not None:
            lines.append(f"- **act_if_above**: {dt['act_if_above']}")
        tib = dt.get("test_if_between")
        if tib:
            lines.append(f"- **test_if_between**: [{tib[0]}, {tib[1]}]")
        if dt.get("pause_if_below") is not None:
            lines.append(f"- **pause_if_below**: {dt['pause_if_below']}")
        if dt.get("reason"):
            lines.append(f"- **reason**: {dt['reason']}")
    else:
        lines.append("_(not decision-shaped, or thresholds not recorded)_")
    lines.append("")

    lines.append("## 13. Settlement & Scoring Plan")
    lines.append(f"- **Data source**: {snapshot.get('data_source') or '—'}")
    lines.append(f"- **Scoring method**: {snapshot.get('scoring_method') or '—'}")
    lines.append(f"- **Resolution date**: {snapshot.get('resolution_date', '—')}")
    if snapshot.get("outcome") is not None:
        lines.append("")
        lines.append("**Settled**:")
        lines.append(f"- Outcome: **{snapshot['outcome']}**")
        lines.append(f"- Final probability: {snapshot.get('final_probability')}")
        if snapshot.get("brier") is not None:
            lines.append(f"- Brier Score: **{snapshot['brier']}**")
        lines.append(f"- Settled at: {snapshot.get('settled_at')}")
    else:
        lines.append("")
        lines.append("_(not yet settled)_")
    lines.append("")

    lines.append("## 14. Ledger Event")
    lines.append(f"- **Forecast id**: `{fid}`")
    updates = [e for e in events if e["type"] == "evidence_update"]
    if updates:
        lines.append("")
        lines.append("**Evidence-update timeline**")
        for ev in updates:
            lines.append(
                f"- {ev['timestamp'][:10]}: {ev['p_from']} → {ev['p_to']} "
                f"({ev.get('direction', 'neutral')}) — {ev['evidence']}"
            )
    lines.append("")
    lines.append("**Full event log**")
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

    date_stamp = timestamp[:10].replace("-", "")
    suffix_re = re.compile(rf"^calibration_{date_stamp}_(\d+)\.md$")
    max_suffix = 0
    for p in REPORTS_DIR.glob(f"calibration_{date_stamp}_*.md"):
        m = suffix_re.match(p.name)
        if m:
            max_suffix = max(max_suffix, int(m.group(1)))
    report_name = f"calibration_{date_stamp}_{max_suffix + 1:03d}.md"
    out_path = REPORTS_DIR / report_name
    out_path.write_text("\n".join(report_lines) + "\n")

    review_id = next_review_id()
    append_event({
        "type": "reviewed",
        "id": review_id,
        "timestamp": timestamp,
        "scope": scope_str,
        "forecast_count": n,
        "average_brier": round(avg_brier, 6),
        "calibration_notes": [ln.lstrip("- ").strip() for ln in calibration_lines],
        "resolution_notes": [ln.lstrip("- ").strip() for ln in resolution_lines],
        "scored_forecast_ids": [ev["id"] for ev in scored_events],
        "report_path": report_name,
    })

    print(f"wrote {out_path}")
    print(f"average Brier: {avg_brier:.4f} over {n} forecasts")
    print(f"recorded {review_id}")


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
    validate_any_id(args.id)
    events = [e for e in load_events() if e.get("id") == args.id]
    snapshot = load_active().get(args.id, {})
    if not snapshot and not events:
        die(f"id not found: {args.id}. Run `sf list` for forecasts or grep events.jsonl for reviews.")
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
    sp.add_argument(
        "--scoring-method", default=None,
        help=(
            "scoring method recorded in the card; defaults derive from --outcome-type "
            "(binary→'Brier Score'; numeric→'manual numeric scoring'; "
            "multi_outcome→'manual multi-class scoring'; "
            "decision_bundle→'settle supporting binary forecasts individually')"
        ),
    )
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
    sp.add_argument("--reference-class", default=None,
                    help="legacy single reference class; treated as --ref-medium if provided")
    sp.add_argument("--ref-broad", default=None)
    sp.add_argument("--ref-medium", default=None)
    sp.add_argument("--ref-narrow", default=None)
    sp.add_argument("--ref-primary", choices=["broad", "medium", "narrow"], default=None)
    sp.add_argument("--base-rate", type=float, default=None)
    sp.add_argument(
        "--base-rate-confidence",
        choices=["low", "low_to_medium", "medium", "medium_to_high", "high"],
        default=None,
    )
    sp.add_argument("--base-rate-reason", default=None)
    sp.add_argument(
        "--up", action="append", default=None,
        help="repeatable upward adjustment 'factor|impact', e.g. 'strong demand|+5pp to +10pp'",
    )
    sp.add_argument(
        "--down", action="append", default=None,
        help="repeatable downward adjustment 'factor|impact', e.g. 'tight budget|-5pp to -10pp'",
    )
    sp.set_defaults(fn=cmd_set_prob)

    sp = sub.add_parser("update", help="update probability with new evidence")
    sp.add_argument("id")
    sp.add_argument("--evidence", required=True)
    sp.add_argument("--p", type=float, required=True)
    sp.add_argument("--range", type=float, nargs=2, default=None, metavar=("LOW", "HIGH"),
                    help="optionally widen/narrow the probability range alongside the update")
    sp.add_argument("--strength", choices=["strong", "moderate", "weak"], default=None)
    sp.set_defaults(fn=cmd_update)

    sp = sub.add_parser("why-wrong", help="record reverse-side reasons (Card section 10)")
    sp.add_argument("id")
    sp.add_argument(
        "--reason", "-r", action="append", required=True,
        help="repeatable; one short reason per flag (e.g. -r 'reference class is too narrow')",
    )
    sp.set_defaults(fn=cmd_why_wrong)

    sp = sub.add_parser("triggers", help="record forward-looking update triggers (Card section 11)")
    sp.add_argument("id")
    sp.add_argument(
        "--up", action="append", default=None,
        help="repeatable upward trigger (what would push p higher)",
    )
    sp.add_argument(
        "--down", action="append", default=None,
        help="repeatable downward trigger (what would push p lower)",
    )
    sp.add_argument("--next-review", default=None, help="YYYY-MM-DD")
    sp.set_defaults(fn=cmd_triggers)

    sp = sub.add_parser("decision", help="record decision thresholds (Card section 12)")
    sp.add_argument("id")
    sp.add_argument("--act-above", type=float, default=None)
    sp.add_argument("--test-between", type=float, nargs=2, default=None, metavar=("LOW", "HIGH"))
    sp.add_argument("--pause-below", type=float, default=None)
    sp.add_argument("--reason", default=None, help="why these thresholds (cost/reversibility)")
    sp.set_defaults(fn=cmd_decision)

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
