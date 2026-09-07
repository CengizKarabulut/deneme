# 11 - Stoc.RSI & RSI & BB & MACD — LOCKED

Durum: **LOCKED**

Nihai production adayi **B modelidir**:

- RSI(14) > 30
- Close, BB(20) Basis'i fresh yukari keser
- StochRSI(3,3,14,14) K > D
- MACD(12,26,9) Level > Signal
- RVOL20 > 1.50

Orijinal A modeli ayni barda StochRSI, BB Basis ve MACD fresh bullish crossover ister. A haftalikta guclu kalmis olsa da B daha genis orneklem, daha yuksek expectancy ve daha iyi rejim dayanimi vermistir.

## Nihai timeframe kararlari

- 15m / 30m / 45m / 1H / 2H: **REJECT**
- 4H: **ACTIVE_SECONDARY**
- 1D: **ACTIVE**
- 1W: **ACTIVE**
- 1M: **INSUFFICIENT_SAMPLE / RESEARCH**

## Nihai SAT ozet

### 4H

- 9-bar swing low - 0.25 ATR
- TP: 1.1R / 2.2R / 3.3R
- normal trail: 1.8 ATR
- Close < BB Basis sonrasi sticky tight trail: 1.0 ATR
- max hold: 40 bar
- NO-BE

### 1D

- 7-bar swing low - 0.25 ATR
- TP: 1.1R / 2.2R / 3.3R
- normal trail: 2.0 ATR
- Close < BB Basis sonrasi sticky tight trail: 1.0 ATR
- max hold: 60 bar
- NO-BE

### 1W

- 11-bar swing low - 0.20 ATR
- TP: 1.1R / 2.2R / 3.3R
- TP2 sonrasi 2.3 ATR trail
- max hold: 80 bar
- NO-BE

Detayli insan-okunur karar: `reports/final-decision.md`

Makine-okunur production spesifikasyonu: `locked-spec.json`

Gecmis veri gozlenmistir; gercek bagimsiz dogrulama gelecekte olusacak yeni barlardir.
