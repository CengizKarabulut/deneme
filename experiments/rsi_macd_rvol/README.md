# RSI & MACD - RVOL

Tarama #4 araştırma alanı.

## Orijinal fikir

```text
50 <= RSI(14) < 70
AND MACD(12,26,9) bullish crossover
AND RVOL20 > 1.50
```

## İlk araştırma matrisi

RSI bantları:
- 50–65
- 50–70
- 55–70

MACD tetikleri:
- `A_cross`: MACD Level, Signal'ı yukarı keser
- `B_hist_rise2`: Histogram `H[t] > H[t-1] > H[t-2]`
- `C_hist_rise2_neg`: Aynı histogram yükselişi, fakat `H[t] < 0`
- `D_hist_pos_rise`: `H[t] > 0` ve `H[t] > H[t-1]`

Tüm modellerde hacim:

```text
RVOL20 = Volume[t] / mean(Volume[t-1] ... Volume[t-20])
RVOL20 > 1.50
```

Mevcut bar ortalamaya dahil değildir ve her timeframe kendi barlarını kullanır.

SAT aileleri: yapısal kontrol, RSI<50, negatif/düşen histogram, MACD bearish cross, RSI+histogram birlikte bozulma, adaptif trailing.

Test aralığı: 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W, 1M. Tamamlanmış bar; giriş referansı sonraki bar açılışı; look-ahead yok; maliyetler dahil.
