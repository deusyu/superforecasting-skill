# Worked Examples

Five reference cases the agent can pattern-match against. Each shows: input →
classification → workflow → output. Use these as templates, not as scripts.

---

## Example 1: Life decision (Guangzhou move)

**User input**: "我去广州会幸福吗？" / "Will I be happy if I move to Guangzhou?"

**Classification**: Mode 1 (new) + decision_bundle (cloud-like, needs
Fermi-ization, the underlying ask is "should I move").

**Workflow**:

1. Recognize this as cloud-like (Gate 3 trigger word: 幸福).
2. Rewrite the canonical question to be resolvable:
   `By 2026-12-31, after living in Guangzhou continuously for at least 4 months,
   will my self-reported life satisfaction be ≥ 7/10?`
3. Fermi-ize into 5 sub-forecasts (job, housing, social circle, climate, savings).
4. Reference class: medium = 北京→广州同职业迁移者.
5. Base rate: 0.45 (similar movers reach high satisfaction within 6 months,
   but social/career variables drive variance).
6. Internal view adjustments:
   - +5–10% (Guangzhou referrals available)
   - +3–6% (rent pressure likely lower)
   - -3–8% (climate adaptation risk)
   - -5–10% (social network rebuild)
7. Final: 0.62, range [0.55, 0.68].
8. Decision threshold: act if ≥0.70, test if 0.55–0.70, pause if <0.55.

**Script invocation sequence**:

```bash
sf new "我去广州会幸福吗？"
# → sf-2026-001
sf scope sf-2026-001 \
  --canonical "By 2026-12-31, after 4+ months in Guangzhou, will self-reported life satisfaction be ≥ 7/10?" \
  --resolution-date 2026-12-31 \
  --criterion "Self-rated satisfaction ≥ 7/10 after 4 continuous months residence" \
  --outcome-type decision_bundle
sf decompose sf-2026-001 \
  -s "Find a job at ≥80% current salary within 3mo|0.65" \
  -s "Find affordable & commutable housing within 1mo|0.75" \
  -s "Build a stable social circle within 6mo|0.45" \
  -s "Adapt to climate & pace within 3mo|0.58" \
  -s "Maintain savings rate at ≥ current within 6mo|0.70"
sf set-prob sf-2026-001 --p 0.62 --range 0.55 0.68 \
  --reference-class "Beijing→Guangzhou same-profession movers" \
  --base-rate 0.45 \
  --reason "Job and housing dimensions strong; social and climate uncertain"
sf render sf-2026-001
```

---

## Example 2: Product judgement

**User input**: "用户会喜欢这个新功能吗？" / "Will users like this new feature?"

**Classification**: Mode 1 + binary, but vague — needs Gate 2 rewrite.

**Workflow**:

1. The word "喜欢" / "like" is not directly resolvable.
2. Replace with measurable proxies:
   `By 2026-08-01 (30 days post-launch), will weekly active usage rate of feature X exceed 20%?`
3. Optionally Fermi-ize into activation rate, retention, repeat usage,
   conversion-to-paid, qualitative interview signal.
4. Reference class: similar feature launches in this product (medium).
5. Base rate from past 5 feature launches (e.g. 0.35 hit the 20% bar).
6. Adjustments based on the specific feature.

**Script invocation**:

```bash
sf new "用户会喜欢这个新功能吗？"
sf scope sf-2026-NNN \
  --canonical "By 2026-08-01, will feature X weekly active usage rate exceed 20%?" \
  --resolution-date 2026-08-01 \
  --criterion "Weekly active rate among eligible users ≥ 20% per analytics dashboard" \
  --data-source "Mixpanel feature_x_weekly_active dashboard"
sf set-prob sf-2026-NNN --p 0.40 --range 0.30 0.50 \
  --reference-class "Past 5 feature launches in this product" \
  --base-rate 0.35 \
  --reason "Better onboarding than past launches but unfamiliar UX pattern"
```

---

## Example 3: Business risk (contract)

**User input**: "客户会不会毁约？" / "Will the client cancel the contract?"

**Classification**: Mode 1 + binary, short-horizon, high-stakes.

**Workflow**:

1. Pin a tight deadline because the user wants action signal.
2. Canonical: `By 2026-05-08 18:00, will the client formally cancel the current contract?`
3. Sub-questions only if needed (budget, payment process, contract terms,
   communication frequency, alternative suppliers).
4. For short-horizon binary, base rate from similar accounts (e.g. 0.15
   cancel pre-deadline).
5. Internal adjustments based on recent communication signals.

```bash
sf new "客户会不会毁约？"
sf scope sf-2026-NNN \
  --canonical "By 2026-05-08 18:00, will client X formally cancel the contract?" \
  --resolution-date 2026-05-08 \
  --criterion "Written cancellation notice received via email or signed letter"
sf set-prob sf-2026-NNN --p 0.25 --range 0.18 0.35 \
  --reference-class "Enterprise clients in renewal cycle" \
  --base-rate 0.15 \
  --reason "Signals of internal budget pressure raise risk above base"
```

---

## Example 4: Learning goal (exam)

**User input**: "我下次模考数学能上 120 吗？" / "Can I score 120+ on next math mock?"

**Classification**: Mode 1 + binary, sharp resolution.

**Workflow**:

1. Already nearly resolvable; just pin the date.
2. Canonical: `On the 2026-06-15 mock exam, will math score be ≥ 120?`
3. Reference class: own last 3 mock scores + class average difficulty curve.
4. Base rate: own historical hit rate at 120+ (e.g. 0.40).
5. Adjust for recent prep, error pattern, exam difficulty signals.

```bash
sf new "我下次模考数学能上 120 吗？"
sf scope sf-2026-NNN \
  --canonical "On the 2026-06-15 mock exam, will math score be ≥ 120?" \
  --resolution-date 2026-06-15 \
  --criterion "Official mock exam math score ≥ 120 / 150"
sf set-prob sf-2026-NNN --p 0.55 --range 0.45 0.65 \
  --reference-class "Last 6 mocks under similar difficulty" \
  --base-rate 0.40 \
  --reason "Recent targeted review on weak topics; difficulty trending easier"
```

---

## Example 5: Update flow (mid-cycle evidence)

**User input**: "update sf-2026-001：今天拿到了两个广州公司的面试" /
"update sf-2026-001: got two interviews with Guangzhou companies today"

**Classification**: Mode 2 (update).

**Workflow**:

1. Read current state via `sf show sf-2026-001`.
2. Classify evidence:
   - Direction: upward (interviews ≠ offers, but raise the job sub-forecast).
   - Strength: moderate (concrete signal in the right direction, not yet decisive).
3. Estimate adjustment: +5% to +10% on the job sub-forecast translates to
   ~+3% to +5% on the bundled forecast.
4. Run:

```bash
sf update sf-2026-001 \
  --evidence "Got 2 Guangzhou company interviews today" \
  --p 0.66 \
  --strength moderate
```

5. Optionally re-render the card.

---

## Example 6: Settlement and learning note

**User input**: "settle sf-2026-001 — moved and satisfaction is 8/10"

**Classification**: Mode 3 (settle).

```bash
sf settle sf-2026-001 --outcome 1
# → outcome=1, final_p=0.66, Brier=0.1156
```

Learning note (the agent should produce, not the script):

> Final p of 0.66 → outcome 1 → Brier 0.1156. The forecast was directionally
> right but on the conservative side. Looking back, the social-circle
> sub-forecast was overweighted as a downward factor — referrals + work team
> filled that channel faster than the base rate predicted. Next time, when
> referrals are confirmed, push social-circle sub-prob up by 10–15%.

This learning is what the next forecast benefits from, not the Brier number
itself.
