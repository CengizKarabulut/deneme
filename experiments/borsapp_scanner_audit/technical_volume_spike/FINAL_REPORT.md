# technical.volume_spike — Final Audit Report

## Scope
Timeframes: 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W.
Universe: all BIST symbols present in each historical SQLite store.
Stages: production-parity baseline, chronological holdout, matched control, turnover contamination test, same-clock-slot RVOL test, final validation.

## Core finding
The scanner is useful as a neutral abnormal-activity / volatility-expansion event, not as a directional bullish or bearish signal.

## Timeframe conclusion
- 15m–1D: matched-control tests show positive forward movement / range edge.
- 1W: the same rule does not preserve the same edge beyond the shortest horizon; weekly should not use the same production rule without a dedicated redesign.

## RVOL threshold
Production RVOL >= 3.0 is a defensible trigger with a large sample and stable holdout behavior.
Higher RVOL levels produce progressively larger forward movement in most 15m–1D tests, so RVOL should also be retained as severity information rather than only a boolean pass/fail field.
Suggested severity bands for research / reporting:
- >=3.0 significant
- >=4.0 strong
- >=5.0 extreme
These are descriptive activity tiers, not directional trade signals.

## Liquidity filter
The production average-turnover calculation includes the current spike bar. This allows a material subset of events to pass the liquidity threshold only because the event itself creates turnover.
At RVOL >= 3, this effect is largest intraday and smaller on higher timeframes.
Final validation did not show that these rescued events are uniformly low quality; many are at least as volatile as the established-liquidity group.
Therefore:
- previous-only turnover is the cleaner ex-ante liquidity measure for the base scanner;
- current-bar-rescued events should not simply be discarded from research;
- if retained operationally, they should be explicitly labeled as event-created / newly emerged liquidity rather than treated as established liquidity.

## Intraday seasonality
Same-clock-slot RVOL generally improves matched-control absolute-movement edge on intraday holdout samples, especially around 1H–4H, but also increases event counts substantially.
Therefore slot-normalized RVOL is validated as useful information but should first be added as an intraday confirmation / severity metric rather than replacing standard RVOL as the sole trigger.

## Proposed production design (analysis only; no borsapp production files changed)
Base event for 15m–1D:
1. closed bars only;
2. close >= minimum price;
3. previous-only 20-bar average turnover >= liquidity threshold;
4. standard RVOL >= 3.0;
5. direction remains NEUTRAL;
6. expose standard RVOL severity tier;
7. expose same-clock-slot RVOL on intraday timeframes as confirmation / context;
8. optionally publish a separate event-created-liquidity flag when current-inclusive turnover passes but previous-only turnover does not.

Weekly:
- do not apply the same rule as a production-equivalent signal; retain as research-only until a weekly-specific rule is designed.

## Status
Audit complete. No production code was modified.
