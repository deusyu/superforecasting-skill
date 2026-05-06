# Scoring & Calibration

How to evaluate forecast quality and translate `sf review` output into actionable
feedback. Read this when handling Mode 3 (settle) and Mode 4 (review).

---

## Brier Score

For binary forecasts:

```
Brier = (predicted_probability - actual_outcome)²
```

`actual_outcome` ∈ {0, 1}. Range of Brier: [0, 1]. Lower = better.

| p | outcome | Brier | interpretation |
|---|---|---|---|
| 0.95 | 1 | 0.0025 | confident and right — excellent |
| 0.70 | 1 | 0.09   | moderately confident, right — good |
| 0.50 | either | 0.25 | uninformative baseline |
| 0.70 | 0 | 0.49   | confident but wrong — large penalty |
| 0.95 | 0 | 0.9025 | confident and wrong — maximum penalty |

The asymmetry matters: confident-and-wrong is punished much more than
confident-and-right is rewarded relative to a 50% guess. This is what makes
Brier a good calibration training signal.

---

## Single-forecast Brier ≠ forecast quality

A 70% forecast that fails (Brier 0.49) is not necessarily a bad forecast — 30%
of 70%-forecasts SHOULD fail. Single Brier scores are noisy. Quality only
emerges over a batch.

When discussing a single settled forecast, focus on:

1. Was the resolution criterion fair (or did the forecast lose on a technicality)?
2. Was there evidence available before the deadline that the agent missed?
3. Did any sub-forecast deviate sharply from its prediction, and why?

Do NOT moralize about a single Brier above 0.25.

---

## Calibration: the long-run check

Group settled forecasts by stated probability band:

```
< 20%   : ~10% should occur
20–40%  : ~30% should occur
40–60%  : ~50% should occur
60–80%  : ~70% should occur
≥ 80%   : ~90% should occur
```

`sf review` produces this breakdown. Read each band:

- `gap > 0` → underconfident (events happen more than you predict)
- `gap < 0` → overconfident (events happen less than you predict)
- |gap| < 0.05 with n ≥ 10 → well-calibrated in this band

Patterns to watch for:

| Pattern | What it means | What to do |
|---|---|---|
| 70% band gap = -0.10 | Overconfident at high probability | Trim peak forecasts by 5–10% |
| 30% band gap = +0.15 | Underestimate low-probability events | Lift floor forecasts by 5–10% |
| Most predictions in 40–60% | Fence-sitting / low resolution | Force commitment on clearer cases |
| Wild swings between bands | Erratic; possibly hindsight-driven | Slow down updates; require explicit triggers |

---

## Resolution: distinguishing the unsure from the confident

A forecaster who says 50% on every question is "calibrated" trivially — they
match the population mean — but useless. Resolution measures the spread of
your stated probabilities. If your forecasts cluster in 40–60%, you have low
resolution.

`sf review` flags fence-sitting when ≥40% of forecasts fall in the 40–60% band.
When that happens, ask: *was I genuinely uncertain on each, or was I avoiding
commitment?*

The cure is not to be more extreme; it is to ask "what evidence would push me
above 60% or below 40%?" — and if you can name it, look for it.

---

## Evidence strength bands (for `sf update --strength`)

When updating a probability mid-flight, classify the evidence:

| Strength | Magnitude | Examples |
|---|---|---|
| `strong` upward | +10% to +20% | Decision-maker directly confirms; structural condition met |
| `moderate` upward | +5% to +10% | Multiple independent signals consistent with outcome |
| `weak` upward | +2% to +5% | Single signal, plausibly noise |
| `neutral` | 0% | Information confirms current view, doesn't shift it |
| `weak` downward | -2% to -5% | Single contrary signal |
| `moderate` downward | -5% to -10% | Multiple contrary signals |
| `strong` downward | -10% to -20% | Decisive contrary evidence (cancellation, missed milestone) |

Multiple updates compound but should not double-count. If two pieces of
evidence are correlated, treat them as one moderate signal, not two strong ones.

Refuse to update without an explicit evidence string. "I just feel less
optimistic" is not evidence — it is mood. Find the underlying observation, or
do not update.

---

## What to write in a Mode-4 review

After running `sf review`, produce 3–5 plain-language observations. A good
review note answers:

1. **What's the average Brier?** (and is it better or worse than 0.25?)
2. **Which probability band is most miscalibrated?** (with the gap number)
3. **Is there fence-sitting?** (% in the 40–60% band)
4. **What category of forecasts performed best/worst?** (e.g. work, health, market)
5. **One concrete behavior change** for the next batch.

Avoid:

- Re-litigating individual settled forecasts.
- Claiming a single high Brier "proves" anything.
- Vague advice like "be more careful" — name the specific band or category.

---

## When to NOT compute Brier

The script will refuse to settle non-binary forecasts (numeric, multi_outcome,
decision_bundle) automatically. For those:

- **Numeric**: use absolute error or quantile-based scoring; record manually.
- **Multi-outcome**: use multi-class Brier
  (`Σ (p_i - I(outcome=i))² / number_of_classes`); record manually.
- **Decision bundle**: settle each sub-forecast individually as binary.

For now (MVP), restrict scored evaluation to binary forecasts. Other types can
still live in the ledger and be reviewed qualitatively.
