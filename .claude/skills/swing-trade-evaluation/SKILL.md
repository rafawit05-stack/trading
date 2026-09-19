---
name: swing-trade-evaluation
description: Analytical framework for scoring and vetting swing-trade candidates (US & DE/EU equities). Combines a structured criteria catalogue with Minervini-style trend/VCP discipline and risk-first position management. Use to evaluate a watchlist the user supplies, not to auto-generate "buy" signals. Produces a ranked shortlist plus a risk plan for the user's own decision.
tags: swing-trading, technical-analysis, screening, risk-management, evaluation, stocks, decision-support
---

# Swing-Trade Evaluation Framework

**Analysis, not financial advice.** This framework scores and pressure-tests candidates the user brings; it does not predict outcomes and does not decide trades. The human sets thresholds, reviews the shortlist, and pulls the trigger. Frame every output as analysis.

## Scope

- Universe: US and DE/EU listed equities.
- Two intended horizons — keep them separate (see "Timeframe" below).
- Data assumed: OHLCV, fundamentals, news/sentiment, options data.

## Timeframe (resolve before scoring)

The criteria catalogue mixed a 2–10 day hold with 200-SMA and 6-month relative-strength filters. Those are incompatible unless you split roles:

- **Regime filters (slow):** market above 50/200-day, sector relative strength, VIX/breadth, quarterly fundamentals. These gate whether to trade, on a weekly cadence.
- **Setup + entry/exit (fast):** daily 20-EMA/50-SMA structure, ATR, pattern, pivot, volume. These decide what and when.
- Enforce a max holding period (e.g. time-stop at 10 sessions) so the exit matches the stated horizon. If you genuinely want a 2–10 day edge, treat the 200-SMA only as a regime gate, never as an entry signal.

## Two playbooks — never one blended score

Breakout-continuation and pullback/mean-reversion are different, sometimes opposite, strategies. Score a candidate under exactly one playbook at a time.

**Playbook A — Breakout / Continuation.** Enter on a decisive close above a defined pivot in a confirmed uptrend, on volume expansion. Rewards strength.

**Playbook B — Pullback in Uptrend.** Enter on a controlled pullback to rising support (20-EMA / 50-SMA / prior breakout level) within an intact uptrend, on volume dry-up then a reversal candle. Rewards a discount inside strength — not deep RSI<30 reversals in weak names.

## Structure: hard gates, then scored factors

Multicollinearity was the biggest flaw in the source catalogue: five trend indicators and four momentum indicators triple-count the same signal. Fix: one primary + one confirmation per concept. Everything else is context, not extra points.

### Hard gates (all must pass, or reject — no score can override)

```
G1  Regime: index (S&P 500 / DAX) above its 200-day MA           [long bias]
G2  Trend:  price > 50-SMA and 50-SMA > 200-SMA, 50-SMA sloping up
G3  Rel.strength: 3-month performance > benchmark
G4  Liquidity (per market, see thresholds)
G5  No hard red flag (section "Exclusions")
G6  R:R at the planned entry/stop/target >= 2.0 AFTER costs
```

A gate that cannot be verified (missing/insufficient data) is **UNKNOWN**, never treated as PASS — see Implementation notes below.

### Scored factors (weights come from the backtest, not from guessing)

One primary indicator per concept, plus at most one confirmation:

```
Concept        Primary (score)              Confirmation (bonus only)
-----------    --------------------------   --------------------------
Trend qual.    ADX(14) in 20–40             Ichimoku: price above cloud
Momentum       RSI(14) > 50 (A) / 40–50     MACD signal cross / hist. flip
               pullback (B)
Volume         Breakout vol >= 1.5x 20d avg OBV confirms direction
Volatility     ATR% in tradable band        Bollinger squeeze pre-break
Pattern        Playbook-specific setup      Clean retest of broken level
Location       Within 25% of 52-wk high     Fib 38.2–61.8% zone (B only)
Fundamentals   EPS/revenue YoY positive     Upward estimate revisions
```

Do NOT also add Stochastic, ROC, HH/HL counts, round numbers as separate scored points — they correlate with the above and inflate false confidence. Keep them as optional human-eyeball context only.

### Concrete thresholds (per market — one size does not fit US + EU)

```
                         US (large/mid)        DE/EU (large/mid)
Min avg daily volume     > 750k shares         > 100k shares
Min avg daily turnover   > $10M                > €5M
Max bid/ask spread       < 0.15%               < 0.30%
Min market cap           > $1B (screen), > $300M floor  |  > €500M / €200M floor
ATR% tradable band       2–6%                  2–6% (tighten to 1.5–5% for large EU)
```

Small caps in either market: tighten liquidity, widen spread tolerance, and size down — slippage, not the chart, is usually what kills these trades.

## Risk & position management (keep strict — this is the real edge)

```
- Risk per trade:        max 1% of capital (2% only for A+ setups)
- Stop:                  max(structure stop, entry - 1.5*ATR); place so normal
                         noise doesn't trigger, loss still bounded
- Position size:         risk_dollars / (entry - stop)
- R:R:                   >= 2:1 after commissions AND spread/slippage
- Targets:               T1 = 2R (scale out), T2 = 3R or structure
- Time stop:             exit if thesis hasn't worked in N sessions (horizon)
- Invalidation exit:     defined technical/fundamental condition that says
                         "the reason I entered is gone" — independent of stop
- Correlation limit:     cap simultaneous positions per sector / factor
- Portfolio:             diversify across positions; no capital concentration
- Overnight/gap risk:    for short holds, account for gap risk; avoid holding
                         through earnings unless the event IS the thesis
```

## Exclusions (hard red flags — auto-reject)

```
- Pending capital raise / dilution or unsettled takeover
- Penny-stock character / illiquid
- Post-IPO lock-up expiry approaching
- Delisting or active regulatory problem
- Pure meme / short-squeeze dynamic with no fundamental base (per risk profile)
- Earnings inside the planned hold (unless deliberately chosen as catalyst)
```

News/sentiment: treat as a soft context factor, not a hard gate. Negative news often creates the very pullback Playbook B wants to buy; an absolute "no negative news" filter throws out good entries. Score sentiment; don't veto on it.

## Turning this into a system (do it in this order)

1. Translate each gate and scored factor into one computable rule with an explicit threshold and a unit test.
2. Score candidates: gates first (binary), then the weighted factor score within one playbook.
3. Derive weights from a walk-forward backtest, not a priori. Warnings that make or break validity:
   - Out-of-sample / walk-forward only; in-sample results are marketing.
   - Include commissions, spread, and slippage in every simulated fill.
   - Survivorship-bias-free universe (dead/delisted names included).
   - Enough trades for significance; report expectancy, not just win rate.
   - Guard against overfitting: this many parameters will fit noise. Prefer fewer factors with stable behaviour over a high in-sample score.
4. Output a ranked shortlist with the full trade plan (entry, stop, size, targets, invalidation) for human review. The system proposes; the person decides and executes.

## Checklist (per candidate, one playbook)

```
□ Playbook chosen (A breakout OR B pullback) — not both
□ G1–G6 all pass
□ Primary indicators aligned; confirmation present
□ Per-market liquidity & spread OK
□ Stop, size, targets, invalidation, time-stop written BEFORE entry
□ R:R >= 2:1 after costs
□ No red flag; earnings clear of hold window
□ Recorded in a written log for later review
```

## Implementation in this repo

This framework is implemented as computable rules in `swing_trade/` (see `README.md`
for CLI usage). Run it against a watchlist CSV (`watchlist.example.csv` shows the
format) via:

```bash
python -m swing_trade watchlist.csv
```

When asked to evaluate a watchlist, prefer running that CLI over eyeballing charts —
it implements every gate and scored factor above as auditable code with unit tests
(`tests/`), not as free-form LLM judgment.

### Gaps found in the framework text and how the code resolves them

- **Stop formula is under-specified.** `max(structure_stop, entry - 1.5*ATR)` bounds
  the loss but says nothing about a structure stop that sits *closer* than that to
  entry (which then violates "normal noise doesn't trigger"). The implementation adds
  a 0.5×ATR floor: a stop tighter than that is widened to the floor, and the
  adjustment is recorded on the trade plan.
- **Volume rule doesn't fit Playbook B.** The concept table only states the breakout
  rule (>= 1.5x 20-day volume), but the Playbook B description explicitly wants a
  volume *dry-up* during the pullback, not expansion. The implementation scores
  Playbook A and B volume with two different rules (expansion vs. dry-up + pickup on
  the reversal day).
- **News/Sentiment has no computable rule.** It's called out in prose as a soft,
  scored (not gated) factor but is missing from the concept table entirely. The
  implementation only includes it when a `sentiment_score` is explicitly supplied in
  the watchlist (e.g. from a manual read or a separate research pass) — it is never
  fabricated as a neutral default.
- **"Large EU" ATR-band tightening has no numeric cutoff.** The implementation uses
  market cap >= €5B as the cutoff for the tightened 1.5–5% band; treat this as a
  documented assumption, not part of the original spec.
- **UNKNOWN vs PASS.** Any gate the code cannot verify (missing/insufficient data) is
  reported as UNKNOWN and is never treated as a pass — such candidates are shown
  separately under "manuelle Pruefung noetig", not mixed into the confirmed ranking.
- **Weights are equal by default**, clearly labeled as a placeholder in every report,
  per this framework's own requirement that real weights come from a walk-forward
  backtest — override with `--weights` once one exists.
- **Qualitative exclusions remain manual.** Dilution, delisting, lock-up expiry, and
  meme/squeeze character are not detectable from OHLCV/fundamentals alone; only a
  manually supplied `red_flag` and an earnings-date/hold-window check are automated.
  The rest stays on the per-candidate checklist for human review.
