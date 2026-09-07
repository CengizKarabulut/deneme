# 7 - BB Daralması — Nihai Karar

Tarih: 2026-09-07

## Orijinal tarama

- Bollinger Bands(20,2) Upper-Lower farkı %0-%10
- Hacim > Ortalama Hacim(10)
- MACD(12,26,9) Level, Signal'ı yukarı keser
- MACD Level > 0

Araştırmada BB genişliği standartlaştırıldı:

`BB Width % = 100 * (Upper - Lower) / Basis`

Hacim bütün timeframe'lerde:

`Volume[t] > mean(Volume[t-1] ... Volume[t-10])`

Mevcut bar hacim ortalamasına dahil değildir; her timeframe kendi barlarını kullanır.

## Test edilen squeeze tanımları

- `abs10`: BB Width <= %10
- `abs5`: BB Width <= %5
- `relative20`: mevcut BB Width, mevcut bar hariç önceki 120 BB Width gözleminin %20 persentilinin altında/eşit
- `release20`: önceki bar `relative20` squeeze içindeydi ve mevcut barda BB Width önceki bara göre genişlemeye başladı

MACD tetikleri:

- `cross`: fresh bullish crossover
- `hist_rise2`: Histogram `H[t] > H[t-1] > H[t-2]`; yalnız yeni başlayan epizot sinyaldir

Bütün girişlerde ayrıca MACD Level > 0 şartı vardır.

## İlk giriş kalitesi — 15m–1M

Her giriş aynı yapısal SAT altında, kendi sinyal zaman çizelgesinden türetilen dört kronolojik pencerede test edildi.

| TF | En iyi/temsilî model | İşlem | PF | E(R) | Pozitif fold | Karar |
|---|---|---:|---:|---:|---:|---|
| 15m | abs10 + histogram | 42,832 | 0.315 | -0.774 | 0/4 | REJECT |
| 30m | abs10 + crossover | 12,039 | 0.447 | -0.510 | 0/4 | REJECT |
| 45m | abs10 + histogram | 35,939 | 0.599 | -0.320 | 0/4 | REJECT |
| 1H | abs10 + crossover | 5,253 | 0.616 | -0.302 | 0/4 | REJECT |
| 2H | release20 + crossover | 4,728 | 0.978 | -0.014 | 2/4 | REJECT |
| 4H | relative20 + crossover | 1,729 | 1.476 | +0.231 | 3/4 | PROMISING |
| 1D | abs10 + histogram | 2,716 | 1.715 | +0.335 | 4/4 | STRONG |
| 1W | release20 + histogram | 1,630 | 2.646 | +0.617 | 4/4 | VERY STRONG |
| 1M | release20 + histogram | 82 | 2.077 | +0.407 | 3/4 | RESEARCH |

### Günlükte neden abs5+crossover seçilmedi?

Ham sıralamada `abs5 + crossover` 84 işlemde PF 2.218 ve +0.508R ile en yüksek rakamı verdi. Ancak örneklem yalnız 84 işlemdi. Aynı günlükte `abs10 + histogram` 2,716 işlemde PF 1.715, +0.335R ve 4/4 pozitiflik verdi. Tek bir dar parametre tepesini seçmek yerine daha geniş örneklemli ve orijinal tarama fikrine daha yakın olan `abs10 + histogram` production adayı olarak donduruldu.

## Nihai timeframe kararları

- 15m / 30m / 45m / 1H / 2H: **REJECT**
- 4H: **ACTIVE_SECONDARY**
- 1D: **ACTIVE**
- 1W: **ACTIVE**
- 1M: **RESEARCH_FORWARD_WATCH**

## 4H — ACTIVE_SECONDARY

### Giriş

- `BB Width <= önceki 120 bar BB Width dağılımının %20 persentili`
- MACD fresh bullish crossover
- MACD Level > 0
- `Volume[t] > önceki 10 adet 4H barın ortalama hacmi`

### SAT

- İlk stop: son 7 adet 4H barın swing low'u - 0.20 ATR(14)
- İlk risk 0.60–2.60 ATR arasında sınırlandırılır
- TP1 = 1R, %30
- TP2 = 2R, %30
- TP3 = 3R, %20
- Runner = %20
- TP2 sonrası normal trailing = 2.0 ATR
- Kapanış BB Basis'in altına inerse trailing 1.5 ATR'ye sıkılaşır; sıkı mod geri gevşemez
- Kapanış BB Basis altında VE MACD < Signal ise kalan pozisyon teknik olarak kapatılır
- Maksimum taşıma = 40 adet 4H bar
- TP1 sonrası break-even yok

Nihai sade profil: **1,967 işlem, PF 1.530, +0.183R, 4/4 pozitif, en kötü fold +0.003R.** En kötü fold marjı ince olduğu için PRIMARY değil SECONDARY olarak tutulur.

Dar parametre taraması 9 swing / 0.25 ATR / 1.8 ATR trail ile PF 1.582, +0.192R üretse de iyileşme materyal eşiğini geçmedi; daha sade baseline korundu.

## 1D — ACTIVE

### Giriş

- BB Width <= %10
- MACD Level > 0
- Histogram `H[t] > H[t-1] > H[t-2]`
- Bu histogram koşulunun yalnız yeni başlayan epizodu sinyaldir
- `Volume[t] > önceki 10 günlük barın ortalama hacmi`

### SAT

- İlk stop: son 7 günlük bar swing low - 0.20 ATR
- TP1/TP2/TP3 = 1R / 2R / 3R
- Dağılım = %30 / %30 / %20 + %20 runner
- TP2 sonrası 2.2 ATR trailing
- BB/MACD hard-SAT yok
- Maksimum taşıma = 40 günlük bar
- TP1 sonrası break-even yok

Nihai: **2,716 işlem, PF 1.715, +0.335R, %47.79 kazanma, 4/4 pozitif, en kötü fold +0.127R.**

Dar parametre taraması +0.023R iyileşme sağladı fakat önceden kullanılan materyal-değişim eşiğini aşmadı; sade 7 / 0.20 / 1-2-3R profili korundu.

## 1W — ACTIVE

### Giriş

- Önceki haftalık bar `relative20` squeeze içindeydi
- Mevcut haftada BB Width önceki haftaya göre genişlemeye başlıyor (`release20`)
- MACD Level > 0
- Histogram `H[t] > H[t-1] > H[t-2]`; yalnız yeni epizot sinyaldir
- `Volume[t] > önceki 10 haftalık barın ortalama hacmi`

### SAT

- İlk stop: son 9 haftalık bar swing low - 0.20 ATR
- TP1/TP2/TP3 = 1.1R / 2.2R / 3.3R
- Dağılım = %30 / %30 / %20 + %20 runner
- TP2 sonrası 2.3 ATR trailing
- Hard BB/MACD SAT yok
- Maksimum taşıma = 60 haftalık bar
- TP1 sonrası break-even yok

Nihai: **1,597 işlem, PF 2.680, +0.657R, %54.10 kazanma, 4/4 pozitif, en kötü fold +0.334R.**

Burada dar SAT değişikliği anlamlı kabul edildi: baseline 1,630 işlemde PF 2.646 / +0.617R / en kötü +0.303R iken nihai profil +0.039R expectancy ve +0.031R en-kötü-fold iyileşmesi sağladı.

## 1M — RESEARCH_FORWARD_WATCH

Giriş:

- `release20` squeeze-release
- MACD Level > 0
- Histogram iki bar güçleniyor; yeni epizot
- Volume > önceki 10 aylık bar ortalaması

Referans SAT:

- 9 bar swing low - 0.15 ATR
- 1R / 2R / 3R
- TP2 sonrası 2.5 ATR trail
- maksimum 36 bar
- BE yok

Sonuç: **82 işlem, PF 2.077, +0.407R, 3/4 pozitif, en kötü fold -0.132R.** Örneklem küçük ve bir dönem negatif olduğu için production'a alınmaz.

## TP1 break-even nihai kontrolü

| TF | NO-BE E(R) | Entry-BE E(R) | Cost-BE E(R) | Karar |
|---|---:|---:|---:|---|
| 4H | +0.183 | +0.164 | +0.161 | NO-BE |
| 1D | +0.335 | +0.280 | +0.284 | NO-BE |
| 1W | +0.657 | +0.587 | +0.588 | NO-BE |
| 1M | +0.407 | +0.253 | +0.255 | NO-BE |

BE kazanma oranını yükseltiyor fakat expectancy'yi düşürüyor; bu nedenle TP1 sonrası stop giriş/maliyet seviyesine taşınmaz.

## Uygulama semantiği

- Sinyal yalnız tamamlanmış barda hesaplanır.
- İşlem referansı bir sonraki bar açılışıdır.
- Komisyon: 10 bps her yön.
- Slippage: 10 bps her yön.
- Aynı OHLC barında stop ve hedef birlikte görünürse STOP önceliklidir.
- İlk risk 0.60–2.60 ATR arasında sınırlandırılır.
- Devam eden histogram koşulu her barda yeni sinyal üretmez; yalnız False→True epizot başlangıcı sinyaldir.
- Geçmiş veri artık gözlenmiştir; bundan sonraki gerçek bağımsız doğrulama gelecekte oluşacak yeni barlardır.

Araştırma run ID'leri:

- Entry stage: `34157171006`
- SAT robustness: `34157449047`
- İlk BE A/B: `34157884289`
- Nihai materyal-gate sonrası BE: `34158149944`
