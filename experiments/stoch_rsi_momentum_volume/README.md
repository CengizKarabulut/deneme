# Stoch RSI / Momentum Kesişim / Hacim Artışı — Araştırma Kaydı

## BASE v1

Bu tarama timeframe-bağımsız olarak aşağıdaki mantıkla test edilir:

```text
Momentum(10)[t] > 0
AND Momentum(10)[t-1] <= 0
AND StochRSI(3,3,14,14) K > D
AND Volume[t] > mean(Volume[t-1], ..., Volume[t-10])
```

### Hacim tanımı

`10 gün` sabit değildir. Her timeframe kendi barlarıyla hesaplanır:

- 15m: mevcut 15m bar hacmi > önceki 10 adet 15m barın ortalaması
- 30m: mevcut 30m bar hacmi > önceki 10 adet 30m barın ortalaması
- 45m: mevcut 45m bar hacmi > önceki 10 adet 45m barın ortalaması
- 1H/2H/4H: aynı mantık
- 1D: mevcut günlük bar hacmi > önceki 10 günlük barın ortalaması
- 1W: mevcut haftalık bar hacmi > önceki 10 haftalık barın ortalaması
- 1M: mevcut aylık bar hacmi > önceki 10 aylık barın ortalaması

Mevcut bar referans ortalamaya dahil edilmez.

## Kontrol giriş varyantları

A — Orijinal:
- StochRSI K, D'yi bu mumda yukarı keser
- MOM(10), 0'ı bu mumda yukarı keser
- hacim filtresi

B — Stoch tetik:
- StochRSI K, D'yi bu mumda yukarı keser
- MOM(10) > 0
- hacim filtresi

C — BASE / Momentum tetik:
- MOM(10), 0'ı bu mumda yukarı keser
- StochRSI K > D
- hacim filtresi

Her varyant yalnız False -> True olayının ilk tamamlanmış barında sinyal üretir. Backtest girişi sonraki bar açılışıdır.

## Test evreni

15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W, 1M.

Önce giriş kalitesi ölçülür; ardından timeframe'e özel SAT aileleri walk-forward olarak test edilir.
