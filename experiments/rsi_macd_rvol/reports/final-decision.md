# RSI & MACD - RVOL — Nihai Karar

Tarih: 2026-09-07

## Orijinal fikir

TradingView taraması:

- RSI(14) >= 50
- RSI(14) < 70
- MACD(12,26,9) bullish crossover
- Relative Volume > 1.50

Araştırmada RSI bandı 50-65 / 50-70 / 55-70 ve dört MACD tetik ailesi aynı yapısal SAT altında ayrı ayrı test edildi. RVOL20 her timeframe'in kendi önceki 20 bar hacim ortalamasına göre hesaplandı; mevcut bar ortalamaya dahil edilmedi.

## Giriş kalitesi sonucu

| TF | En iyi sabit giriş | İşlem | PF | E(R) | Pozitif fold | Karar |
|---|---|---:|---:|---:|---:|---|
| 15m | RSI55-70 + negatif histogram toparlanması | 5,594 | 0.324 | -0.744 | 0/4 | REJECT |
| 30m | RSI50-70 + negatif histogram toparlanması | 9,312 | 0.462 | -0.485 | 0/4 | REJECT |
| 45m | RSI50-65 + negatif histogram toparlanması | 8,231 | 0.623 | -0.294 | 0/4 | REJECT |
| 1H | RSI55-70 + negatif histogram toparlanması | 3,001 | 0.661 | -0.258 | 0/4 | REJECT |
| 2H | RSI55-70 + negatif histogram toparlanması | 5,235 | 0.961 | -0.025 | 1/4 | REJECT |
| 4H | RSI55-70 + MACD crossover | 3,845 | 1.264 | +0.132 | 3/4 | PROMISING |
| 1D | RSI50-65 + histogram H[t] > H[t-1] > H[t-2] | 8,668 | 1.366 | +0.183 | 4/4 | STRONG |
| 1W | RSI50-65 + MACD crossover | 1,090 | 3.245 | +0.757 | 4/4 | VERY STRONG |
| 1M | RSI55-70 + pozitif/yükselen histogram | 196 | 4.782 | +0.894 | 4/4 | STRONG, SMALL SAMPLE |

Sonuç: MACD histogramını her timeframe'e zorlamak doğru değil. 1D histogramı, 1W ve 4H ise klasik crossover'ı tercih ediyor.

## Nihai ACTIVE kurallar

### 4H — ACTIVE_SECONDARY

Giriş:

- 55 <= RSI14 < 70
- MACD fresh bullish crossover
- RVOL20 > 1.50

SAT:

- İlk stop: son 7 bar swing low - 0.20 ATR
- Risk mesafesi: 0.60-2.60 ATR aralığında sınırlandırılır
- TP1 1R (%30), TP2 2R (%30), TP3 3R (%20), runner %20
- TP2 sonrası normal trail: 2.0 ATR
- RSI14 < 50 veya histogram iki bar üst üste zayıflarsa trail 1.5 ATR'ye sıkılaşır ve sıkı mod geri gevşemez
- RSI14 < 50 VE histogram < 0 VE histogram düşüyorsa kalan pozisyon teknik olarak kapatılır
- Maksimum taşıma 40 adet 4H bar
- TP1 sonrası BE yok

Dar SAT doğrulaması: 4,603 işlem, PF 1.572, +0.145R, 4/4 pozitif; en kötü fold +0.103R. Bu nedenle 4H giriş tek başına 1D/1W kadar kuvvetli olmasa da sabit adaptif yönetimle ACTIVE_SECONDARY kabul edildi.

### 1D — ACTIVE

Giriş:

- 50 <= RSI14 < 65
- RVOL20 > 1.50
- Histogram H[t] > H[t-1] > H[t-2]
- Histogram koşulunun yeni başlayan epizodu sinyal sayılır; devam eden her bar yeni sinyal değildir

SAT:

- İlk stop: son 7 bar swing low - 0.20 ATR
- TP1/TP2/TP3: 1R / 2R / 3R
- Dağılım: %30 / %30 / %20 + %20 runner
- TP2 sonrası 2.2 ATR trailing
- Hard RSI/MACD SAT yok
- Maksimum taşıma 40 günlük bar
- TP1 sonrası BE yok

Nihai: 8,668 işlem, PF 1.366, +0.183R, 4/4 pozitif; en kötü fold +0.043R.

### 1W — ACTIVE

Giriş:

- 50 <= RSI14 < 65
- MACD fresh bullish crossover
- RVOL20 > 1.50

SAT dar optimizasyonda anlamlı biçimde iyileşti:

- İlk stop: son 11 haftalık bar swing low - 0.15 ATR
- TP1/TP2/TP3: 1.1R / 2.2R / 3.3R
- Dağılım: %30 / %30 / %20 + %20 runner
- TP2 sonrası 2.1 ATR trailing
- Hard RSI/MACD SAT yok
- Maksimum taşıma 60 haftalık bar
- TP1 sonrası BE yok

Baseline 1,090 işlemde PF 3.245 ve +0.757R idi. Nihai dar-komşuluk profilinde 1,069 işlem, PF 3.376, +0.810R ve 4/4 pozitiflik elde edildi; en kötü fold +0.373R.

## 1M — RESEARCH / FORWARD WATCH

Giriş:

- 55 <= RSI14 < 70
- RVOL20 > 1.50
- Histogram > 0 ve H[t] > H[t-1]
- Koşulun yeni başlayan epizodu sinyal sayılır

SAT:

- 9 bar swing low - 0.15 ATR
- 1R / 2R / 3R
- TP2 sonrası 2.5 ATR trailing
- Maksimum taşıma 36 aylık bar
- TP1 sonrası BE yok

Tarihsel rakamlar güçlü: 196 işlem, PF 4.782, +0.894R, 4/4 pozitif. Ancak örneklem küçük ve dengesizdir; ilk kronolojik fold yalnız 2 tamamlanmış işlem içeriyor. Bu nedenle production yerine forward-watch statüsünde tutulur.

## TP1 Break-even son kontrolü

| TF | NO-BE E(R) | Entry-BE E(R) | Cost-BE E(R) | Nihai |
|---|---:|---:|---:|---|
| 4H | +0.145 | +0.122 | +0.119 | NO-BE |
| 1D | +0.183 | +0.165 | +0.165 | NO-BE |
| 1W | +0.810 | +0.704 | +0.702 | NO-BE |
| 1M | +0.894 | +0.661 | +0.657 | NO-BE |

1D'de cost-BE en kötü fold'u çok az iyileştirse de toplam expectancy yaklaşık %10 düşüyor. Bu araştırmada kazanma oranını yükseltmek tek başına yeterli kabul edilmedi; edge korunması önceliklidir. Bu nedenle dört aday timeframe'in tamamında NO-BE kilitlendi.

## Uygulama semantiği

- Sinyal yalnız tamamlanmış mumda hesaplanır.
- İşlem referansı bir sonraki mum açılışıdır.
- Komisyon 10 bps ve slippage 10 bps her yön için modele dahildir.
- Aynı OHLC mumunda stop ve hedef birlikte görünürse stop önceliklidir.
- Mevcut hacim, aynı timeframe'in önceki 20 bar hacim ortalamasına bölünür; mevcut bar referans ortalamasına katılmaz.
- Geçmiş veri birçok kez gözlendiği için bundan sonraki gerçekten bağımsız doğrulama gelecekte oluşacak yeni barlardır.

## Nihai sınıflandırma

- 15m / 30m / 45m / 1H / 2H: REJECT
- 4H: ACTIVE_SECONDARY
- 1D: ACTIVE
- 1W: ACTIVE
- 1M: RESEARCH_FORWARD_WATCH

Araştırma run ID'leri: entry-stage `34153340439`, SAT robustness `34154013348`, TP1 BE A/B `34156110365`.
