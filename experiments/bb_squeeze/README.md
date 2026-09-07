# 7 - BB Daralması

Araştırma alanı. Production kodu değildir.

## Orijinal fikir

- Bollinger Bands(20,2) dar: Upper-Lower farkı %0-%10
- Volume[t] > önceki 10 aynı-timeframe bar ortalaması
- MACD(12,26,9) bullish crossover
- MACD Level > 0

## Araştırma matrisi

BB Width standardizasyonu:

`BB Width % = 100 * (Upper - Lower) / Basis`

Sıkışma modelleri:

- `abs10`: BB Width <= %10
- `abs5`: BB Width <= %5
- `relative20`: BB Width, önceki 120 barın en dar %20'lik bölgesinde
- `release20`: önceki bar relative20 squeeze içindeydi ve bu bar BB Width genişlemeye başladı

MACD tetikleri:

- `cross`: fresh bullish crossover ve MACD Level > 0
- `hist_rise2`: histogram iki bar üst üste güçleniyor ve MACD Level > 0; yalnız yeni başlayan epizot sinyaldir

Hacim:

`Volume[t] > mean(Volume[t-1] ... Volume[t-10])`

Mevcut bar ortalamaya dahil değildir. Her timeframe kendi barlarını kullanır.

İlk aşama 15m-1M aralığında tüm giriş modellerini aynı yapısal SAT ile karşılaştırır. Güçlü timeframe'ler daha sonra SAT robustness + TP1 BE/no-BE testine alınır.
