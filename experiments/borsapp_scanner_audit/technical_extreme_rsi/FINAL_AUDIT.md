# technical.extreme_rsi — Final Audit

## Production baseline

- RSI <= 25: bullish reversal state
- RSI >= 75: bearish reversal state
- RVOL >= 1.0
- minimum price 1 TL
- average turnover >= 20M TL
- closed bars only
- audited on 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W

## Main finding

The scanner should **not** be used as a standalone directional reversal signal. RSI extremity identifies stretched momentum, but the direction implied by the production rule does not show stable out-of-sample reversal edge across the mandatory timeframe matrix.

### Production 25/75 + RVOL>=1 holdout, 5-bar directional results

| TF | Oversold bullish events | Hit rate | Median aligned return | Overbought bearish events | Hit rate | Median aligned return |
|---|---:|---:|---:|---:|---:|---:|
| 15m | 1,344 | 42.74% | 0.00% | 1,574 | 47.84% | 0.00% |
| 30m | 1,999 | 39.63% | -0.16% | 2,471 | 45.69% | 0.00% |
| 45m | 2,487 | 38.74% | -0.27% | 3,662 | 45.82% | 0.00% |
| 1H | 1,513 | 35.31% | -0.33% | 1,961 | 44.31% | 0.00% |
| 2H | 2,826 | 45.79% | -0.22% | 5,521 | 50.00% | +0.02% |
| 4H | 1,978 | 46.13% | -0.40% | 3,779 | 50.76% | +0.09% |
| 1D | 705 | 42.90% | -1.27% | 3,443 | 48.23% | -0.37% |
| 1W | 29 | 64.71% | +8.36% | 1,477 | 49.51% | -0.32% |

The 1W oversold sample is only 29 holdout events and therefore is not sufficient to override the broad cross-timeframe result.

## Threshold sensitivity

Testing symmetric threshold pairs 20/80, 25/75 and 30/70 did not produce a robust reversal edge. Tighter 20/80 thresholds reduce sample size without consistently improving directional accuracy. Wider 30/70 thresholds improve the bearish side modestly on some higher timeframes (roughly 50–52% on 4H/1D/1W), but the edge remains too small to justify a standalone directional signal.

## Trend-regime finding

The dominant failure mode is continuation of the prevailing trend while RSI remains extreme:

- oversold observations are mostly below EMA21/EMA55 and frequently continue lower;
- overbought observations are mostly above EMA21/EMA55 and frequently continue higher;
- therefore `extreme -> immediate reversal` is not a stable assumption.

On the production 25/75 rule, oversold-bullish 5-bar holdout hit rates inside downtrends are approximately 33–42% on 15m–1D. Overbought-bearish observations inside uptrends are mostly around 44–51%.

## Final technical decision

**REVISE / MERGE — do not retain as a standalone directional scanner.**

Recommended role in the future unified engine:

1. Keep RSI extremity as a **context / exhaustion feature**.
2. Require price-action confirmation before assigning reversal direction, e.g. failed break/reclaim, divergence, absorption, swing rejection, or structure change.
3. Consider merging the useful part of this scanner into `technical.exhaustion` rather than sending a separate event.
4. Preserve the raw RSI value and extremity severity for scoring, but do not translate `<=25` directly into bullish or `>=75` directly into bearish.
5. 1W oversold results require a much larger sample before any timeframe-specific exception is considered.

Production code was not modified by this audit.
