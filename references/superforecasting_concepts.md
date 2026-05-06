# Superforecasting Concepts

Distilled definitions and principles. Consult when you need to explain a
concept, justify a workflow choice, or coach the user.

---

## Core formula

```
Superforecasting = probabilization + testability
```

Probabilization: replace "will it happen" with "what is the probability".
Testability: bind every probability to an event, deadline, and resolution
criterion so it can be settled and scored.

---

## What it is NOT

1. Not divination. It does not claim to see the future.
2. Not opinion. "I think it will happen" is not a forecast.
3. Not consolation. It does not exist to make the user feel better.
4. Not one-shot. Forecasts are dynamic and update with evidence.
5. Not model worship. Reference classes + Bayesian updating beat most models.

---

## The four required elements of a resolvable question

1. **Specific event** — what exactly?
2. **Deadline** — by when?
3. **Resolution criterion** — what counts as YES, what counts as NO?
4. **Data source** — what authority resolves the question?

| Bad | Good |
|---|---|
| Will this product be popular? | By 2026-08-01, will day-1 retention exceed 35% per the in-app analytics dashboard? |
| Will I be happy in Guangzhou? | By 2026-12-31, after living in Guangzhou for 4+ months, will my self-reported life satisfaction be ≥7/10? |

---

## Fermi-ization

Cloud-like questions (fuzzy boundary, untestable directly) must be decomposed
into 3–7 operationalized sub-questions. Each sub-question should itself be
resolvable if possible.

Example:

```
Will US-China decouple? (cloud-like)
↓
- In the next 6 months, will a tariff bill on category X pass?
- In the next year, will trade volume in core technology Y drop >10%?
- In the next year, will either side add new export controls on Z?
```

The point: *uncertainty, once named and decomposed, becomes engineering rather
than emotion.*

---

## External view (reference class first)

Before introducing personal narrative, ask: *how have similar things gone
historically?* Pick three layers:

```yaml
broad: all relevant historical cases
medium: cases close to this situation in 2–3 key dimensions
narrow: cases matching the specifics tightly (may have small sample)
primary: usually `medium`
```

Cite the primary reference class explicitly when reporting the base rate.

---

## Internal view (adjust after the base rate)

Once you have the base rate, list:

- Upward factors (each with estimated +X% to +Y% impact)
- Downward factors (each with estimated -X% to -Y% impact)

Sum midpoints to get the adjusted probability. Use the spread to derive the
probability range.

Key discipline: *do not let the personal story override the base rate — adjust
from it, do not replace it.*

---

## Bayesian updating

Forecasts are not one-shot. New evidence changes the probability. Use evidence
strength bands (see scoring.md):

```
strong upward: +10% to +20%
moderate upward: +5% to +10%
weak upward: +2% to +5%
neutral: 0%
weak downward: -2% to -5%
moderate downward: -5% to -10%
strong downward: -10% to -20%
```

Adjust based on:

1. Reliability of the evidence
2. Recency
3. Independence from prior evidence
4. Real causal link to the outcome
5. How close the prior already is to 0 or 1

Avoid mechanical updating. Justify each adjustment.

---

## Calibration vs. resolution

**Calibration**: do your stated probabilities match long-run frequencies?
If you say 70% on 100 forecasts, ~70 should happen. Less = overconfident.
More = underconfident.

**Resolution**: do you separate high-confidence from low-confidence cases?
Always saying 50% is "safe" but useless. Good forecasters dare to say 15%, 25%,
70%, 85% when evidence supports it.

The two trade off. Calibration without resolution = predicting averages.
Resolution without calibration = bold but wrong. Both matter.

---

## Brier Score (binary forecasts)

```
Brier = (predicted_probability - actual_outcome)²
```

Where `actual_outcome` is 1 if the event occurred, 0 if not.

| Predicted p | Outcome | Brier |
|---|---|---|
| 0.70 | 1 | 0.09 |
| 0.70 | 0 | 0.49 |
| 0.50 | either | 0.25 |
| 0.95 | 1 | 0.0025 |
| 0.95 | 0 | 0.9025 |

Lower is better. Brier penalizes overconfidence and rewards calibrated
confidence. A constant 0.5 gives 0.25 every time — beat that.

---

## Forecast vs. decision (must be separated)

Forecast: *what is the probability?*
Decision: *given the probability and the costs, do I act?*

A 62% probability does NOT automatically mean "do it". Decision also depends on:

1. Action cost
2. Reversibility
3. Downside loss
4. Available alternatives
5. Regret cost
6. Risk tolerance

The skill outputs a decision threshold, not a verdict:

```yaml
decision_threshold:
  act_if_above: 0.70
  test_if_between: [0.55, 0.70]
  pause_if_below: 0.55
```

The user makes the final call.

---

## Where AI fits

AI is good at:

- Spotting that a question is too vague
- Generating Fermi-ized decompositions
- Proposing candidate reference classes
- Marshalling pro/con evidence
- Maintaining the forecast card and ledger
- Computing Brier Score
- Producing review summaries

The human keeps:

- Defining the question that actually matters
- Judging whether the resolution criterion is fair
- Choosing the most relevant reference class
- Weighing surprising evidence
- Setting decision thresholds
- Owning the final decision

AI = process engineer for forecasting. Human = judgment owner.

---

## Glossary

| Term | Meaning |
|---|---|
| Probabilization | Replacing fuzzy words with explicit probabilities |
| Testability | Resolvable by deadline against a known criterion |
| Cloud-like question | Fuzzy boundary, cannot be directly judged |
| Fermi-ization | Decomposing a cloud question into operational sub-questions |
| Reference class | Set of similar historical cases |
| External view | "How have similar cases gone?" |
| Internal view | "What's specific about this case?" |
| Prior | Initial probability, usually from base rate |
| Bayesian updating | Adjusting probability when new evidence arrives |
| Calibration | Long-run match between stated probabilities and actual frequencies |
| Resolution | Ability to distinguish high-probability from low-probability cases |
| Brier Score | Squared loss for probabilistic forecasts |
| Decision threshold | Probability above which action is taken |
| Forecast card | Structured output of a single forecast |
| Forecast ledger | Persistent record of forecasts, updates, outcomes |
