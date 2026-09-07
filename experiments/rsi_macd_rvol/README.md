# RSI & MACD - RVOL

Tarama #4 araştırma alanı. Araştırma tamamlandı ve nihai kurallar kilitlendi.

## Orijinal fikir

```text
50 <= RSI(14) < 70
AND MACD(12,26,9) bullish crossover
AND RVOL20 > 1.50
```

## Araştırma matrisi

RSI bantları: 50–65, 50–70, 55–70.

MACD tetikleri:

- `A_cross`: MACD Level, Signal'ı yukarı keser
- `B_hist_rise2`: Histogram `H[t] > H[t-1] > H[t-2]`
- `C_hist_rise2_neg`: Aynı histogram yükselişi, fakat `H[t] < 0`
- `D_hist_pos_rise`: `H[t] > 0` ve `H[t] > H[t-1]`

Tüm modellerde:

```text
RVOL20 = Volume[t] / mean(Volume[t-1] ... Volume[t-20])
RVOL20 > 1.50
```

Mevcut bar ortalamaya dahil değildir ve her timeframe kendi barlarını kullanır. Tamamlanmış bar kullanılır; giriş referansı sonraki bar açılışıdır; look-ahead yoktur ve maliyetler dahildir.

## Kilitli karar

- 15m / 30m / 45m / 1H / 2H: `REJECT`
- 4H: `ACTIVE_SECONDARY` — RSI55–70 + MACD bullish crossover + RVOL20>1.5, adaptif SAT
- 1D: `ACTIVE` — RSI50–65 + histogram iki bar güçleniyor + RVOL20>1.5
- 1W: `ACTIVE` — RSI50–65 + MACD bullish crossover + RVOL20>1.5
- 1M: `RESEARCH_FORWARD_WATCH` — RSI55–70 + pozitif/yükselen histogram + RVOL20>1.5
- Tüm aday timeframe'lerde TP1 sonrası break-even: `YOK`

Nihai insan-okunur rapor: `reports/final-decision.md`

Makine-okunur production/research spesifikasyonu: `locked-spec.json`
