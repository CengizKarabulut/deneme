# technical.squeeze_volume — Final Audit

## Scope

- Universe: all BIST symbols available in each historical SQLite artifact (about 584 symbols; usable count varies by history availability).
- Timeframes: 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W.
- Production baseline: `BB width percentile <= 20`, `RVOL >= 1.5`, price >= 1 TL, 20-bar average turnover >= 20M TL, closed bars only, neutral STATE.
- Chronological holdout: final 20% of production events.
- Robustness: fresh-vs-repeated state, same-squeeze low-volume matched controls, current-inclusive vs previous-only turnover, same-clock-slot RVOL for intraday, and inclusive vs previous-only BB percentile.

## Baseline — production rule, 5-bar holdout

| TF | Events | Fresh % | Median abs move | Range / ATR | Max BB-width ratio |
|---|---:|---:|---:|---:|---:|
| 15m | 2,365 | 66.2 | 0.57% | 2.75 | 1.29x |
| 30m | 3,696 | 76.6 | 0.83% | 2.35 | 1.19x |
| 45m | 4,288 | 77.1 | 1.04% | 2.29 | 1.17x |
| 1H | 3,033 | 80.7 | 1.14% | 2.28 | 1.17x |
| 2H | 5,168 | 78.4 | 1.85% | 2.32 | 1.19x |
| 4H | 4,714 | 81.3 | 2.19% | 2.22 | 1.15x |
| 1D | 3,395 | 71.9 | 4.10% | 2.41 | 1.22x |
| 1W | 1,261 | 69.5 | 8.40% | 2.41 | 1.15x |

## RVOL condition — matched-control result

Controls are low-volume bars inside the same squeeze state, matched by symbol, quarter, intraday clock slot, previous-turnover bucket and initial BB-rank bucket. The production RVOL condition generally adds positive 5-bar absolute-movement edge from 15m through 1D in both research and holdout. Holdout median absolute-move edge is approximately:

- 15m: +0.02 percentage points
- 30m: +0.01 pp
- 45m: +0.03 pp
- 1H: +0.08 pp
- 2H: +0.07 pp
- 4H: +0.03 pp
- 1D: +0.27 pp
- 1W: -0.36 pp

The weekly timeframe is the clear exception: `RVOL >= 1.5` does not show a robust incremental advantage over comparable low-volume weekly squeezes.

## Parameter sensitivity

- `BB rank <= 20` is a reasonable balance. Tightening to <=10 is not consistently superior across timeframes; loosening to <=30 increases event count without a stable quality improvement.
- Raising RVOL from 1.0 -> 1.5 -> 2.0 -> 3.0 generally raises movement/range quality, especially on 15m, 30m, 45m, 2H, 4H and 1D, while reducing sample size.
- Therefore RVOL is better treated as a severity dimension rather than replacing the base rule with one aggressively optimized threshold.

## State persistence

Fresh-state share is roughly 66%–81% depending on timeframe. Fresh-only results are close to all-state results, so repeated STATE observations are not the main source of the measured effect. For messaging/deduplication, fresh onset should still be preferred; for market-state tracking, persistence remains useful.

## Turnover implementation

Current-inclusive turnover versus previous-only turnover has high overlap (about 92.6%–98.5%). The current bar admits a small additional event set, with the largest impact intraday. Outcome quality is very similar between variants. Previous-only turnover remains methodologically cleaner because the event bar cannot create its own liquidity eligibility; the production implementation is not catastrophically distorted, but should be revised when production changes are eventually approved.

## Intraday clock-slot RVOL

Same-clock-slot RVOL selects a materially different intraday event set (Jaccard roughly 26%–44%). It improves some timeframes materially (notably 1H and in raw movement several others) but is not uniformly superior in matched holdout edge or ATR-normalized range. It should be retained as a research/confirmation feature, not substituted wholesale for standard RVOL.

## BB percentile self-inclusion

Production percentile includes the current BB width. A previous-only percentile adds only about 3%–4% more events; production events are essentially a stricter subset and overlap is ~96%–97%. This is not a meaningful source of look-ahead or instability, so there is no urgent reason to change the percentile definition.

## Final research recommendation

1. Retain `technical.squeeze_volume` as a neutral squeeze-plus-participation STATE scanner on 15m through 1D.
2. Keep `BB rank <= 20` as the baseline threshold.
3. Keep `RVOL >= 1.5` as the base participation requirement; expose RVOL >=2 and >=3 as higher-severity tiers rather than independent optimized scanners.
4. Prefer fresh onset for notification/deduplication while preserving ongoing STATE internally.
5. On a future production revision, prefer previous-only turnover for eligibility.
6. Keep same-slot RVOL as an auxiliary confirmation/severity feature until a broader cross-regime validation supports replacing standard RVOL.
7. Treat 1W separately: the RVOL filter does not demonstrate incremental matched-control edge, so weekly squeeze should remain research-only or be modeled as a pure squeeze state without requiring the same RVOL rule.
8. Direction remains NEUTRAL; this scanner identifies compression plus participation, not a reliable up/down forecast.

No production files were changed by this audit.
