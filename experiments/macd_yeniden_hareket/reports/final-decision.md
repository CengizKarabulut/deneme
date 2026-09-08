# 13 - MACD YenidenHareket — Nihai Karar

Tarih: 2026-09-08  
Durum: **LOCKED**

## Giriş adayları

### A — Orijinal
- MACD(12,26,9) Level > 0
- MACD Level, Signal'ı fresh bullish keser

### B — Güçlü pozitif bölge
- MACD Level > 0
- MACD Signal > 0
- MACD Level, Signal'ı fresh bullish keser

### C — Yeniden ivmelenme
- MACD Level > 0
- MACD Level > Signal
- Histogram[t] > Histogram[t-1] > Histogram[t-2]
- yalnız yeni başlayan histogram-ivme epizodu sinyal sayılır

A/B/C aynı yapısal SAT kontrol profili, aynı maliyet modeli ve her varyantın kendi sinyal zamanlarından oluşan dört kronolojik pencereyle karşılaştırıldı. B, A'ya karşı anlamlı ve kalıcı bir ek avantaj üretmediği için final kurallarda kullanılmıyor.

## Nihai timeframe kararları

| TF | Final giriş | Statü | Final PF | E(R) | Kazanma | Fold |
|---|---|---|---:|---:|---:|---:|
| 15m | — | REJECT | — | negatif | — | 0/4 |
| 30m | — | REJECT | — | negatif | — | 0/4 |
| 45m | — | REJECT | — | negatif | — | 0/4 |
| 1H | — | REJECT | — | negatif | — | 0/4 |
| 2H | B en yakın aday | REJECT | 0.977 | -0.015 | — | 1/4 |
| 4H | C | ACTIVE_SECONDARY | 3.453 | +0.446R | %66.65 | 4/4 |
| 1D | C | ACTIVE | 4.296 | +0.536R | %69.18 | 4/4 |
| 1W | A | ACTIVE | 3.021 | +0.707R | %58.70 | 4/4 |
| 1M | A | RESEARCH_FORWARD_WATCH | 3.538 | +0.694R | %61.18 | 4/4 |

4H ham yapısal girişte 12.510 işlem, PF 1.158, +0.084R ve 3/4 pozitif dönem verdi. MACD tabanlı adaptif yönetimle 4/4'e çıktığı için PRIMARY yerine **ACTIVE_SECONDARY** tutulur.

1D'de C yapısal kontrol altında zaten 10.241 işlem, PF 1.538, +0.256R ve 4/4 pozitif dönem üretti; adaptif risk yönetimi bunu daha da güçlendirdi.

1W'de orijinal A en sade ve en sağlam seçim kaldı. 1M de pozitif görünse de yalnız 152 tamamlanmış işlem ve dengesiz kronolojik dağılım nedeniyle production'a alınmadı.

## 4H — ACTIVE_SECONDARY

Final giriş: **C — positive histogram reacceleration**.

Final SAT:
- ilk stop: son 7 adet 4H swing low - 0.20 ATR
- fallback stop: 1.20 ATR
- ilk risk 0.60–2.60 ATR arasında sınırlandırılır
- TP1 = 1.0R, %30
- TP2 = 2.0R, %30
- TP3 = 3.0R, %20
- runner = %20
- TP2 sonrası normal trailing = 2.0 ATR
- MACD Level < Signal olduğunda sticky tight trailing = **0.5 ATR**
- tight trailing TP2'den önce de aktive olabilir ve tekrar gevşemez
- teknik hard exit yok
- maksimum taşıma = 40 adet 4H bar
- TP1 sonrası break-even yok

Genişletilmiş tight-trail taramasında 0.4–1.0 ATR aralığındaki bütün adaylar 4/4 pozitif kaldı ve sıkılaştıkça tarihsel sonuç iyileşti. 0.4 ATR sınır optimumunu kovalamamak için komşu ve daha muhafazakâr **0.5 ATR** kilitlendi.

Final NO-BE: **16.687 işlem, PF 3.453, +0.446R, medyan +0.384R, %66.65 kazanma, 4/4 pozitif, worst-fold +0.390R.**

## 1D — ACTIVE

Final giriş: **C — positive histogram reacceleration**.

Final SAT:
- ilk stop: son 7 günlük swing low - 0.20 ATR
- fallback stop: 1.25 ATR
- TP1 / TP2 / TP3 = 1.0R / 2.0R / 3.0R
- dağılım %30 / %30 / %20 + %20 runner
- TP2 sonrası normal trailing = 2.2 ATR
- MACD Level < Signal olduğunda sticky tight trailing = **0.5 ATR**
- teknik hard exit yok
- maksimum taşıma = 40 günlük bar
- TP1 sonrası break-even yok

1D'de de 0.4–1.0 ATR alt plateau 4/4 pozitif kaldı. Aynı anti-overfit gerekçesiyle sınırdaki 0.4 yerine **0.5 ATR** kilitlendi.

Final NO-BE: **13.705 işlem, PF 4.296, +0.536R, medyan +0.435R, %69.18 kazanma, 4/4 pozitif, worst-fold +0.448R.**

## 1W — ACTIVE

Final giriş: **A — original positive-zone bullish MACD cross**.

Final SAT:
- ilk stop: son 9 haftalık swing low - 0.15 ATR
- fallback stop: 1.30 ATR
- TP1 / TP2 / TP3 = 1.0R / 2.0R / 3.0R
- dağılım %30 / %30 / %20 + %20 runner
- TP2 sonrası 2.3 ATR trailing
- teknik hard exit / MACD tighten yok
- maksimum taşıma = 60 haftalık bar
- TP1 sonrası break-even yok

Final NO-BE: **1.949 işlem, PF 3.021, +0.707R, medyan +1.262R, %58.70 kazanma, 4/4 pozitif, worst-fold +0.270R.**

## 1M — RESEARCH_FORWARD_WATCH

Final araştırma girişi: **A — original**.

Yapısal profil: swing 9, buffer 0.15 ATR, fallback 1.30 ATR, 1/2/3R hedefler, TP2 sonrası 2.5 ATR trail, maksimum 36 aylık bar, NO-BE.

Final tarihsel sonuç: **152 işlem, PF 3.538, +0.694R, medyan +0.900R, %61.18 kazanma, 4/4 pozitif, worst-fold +0.042R.**

Örneklem küçük ve fold dağılımı dengesiz olduğundan ACTIVE değildir; yeni aylık sinyallerle forward-watch tutulur.

## TP1 break-even final kontrolü

| TF | NO-BE E(R) | Entry-BE E(R) | Cost-BE E(R) | Karar |
|---|---:|---:|---:|---|
| 4H | +0.446 | +0.361 | +0.355 | NO-BE |
| 1D | +0.536 | +0.456 | +0.452 | NO-BE |
| 1W | +0.707 | +0.612 | +0.612 | NO-BE |
| 1M | +0.694 | +0.570 | +0.572 | NO-BE / research |

BE kazanma oranını bazı timeframe'lerde yükseltse de expectancy'yi düşürdü. Bu nedenle TP1 sonrası kalan pozisyon giriş veya maliyet seviyesine taşınmıyor.

## Ortak uygulama semantiği

- MACD parametreleri 12,26,9
- sinyal yalnız tamamlanmış barda hesaplanır
- giriş referansı bir sonraki bar açılışıdır
- A fresh cross: MACD[t] > Signal[t] ve MACD[t-1] <= Signal[t-1], ayrıca MACD[t] > 0
- C: MACD>0, MACD>Signal, H[t]>H[t-1]>H[t-2]; yalnız koşulun yeni başladığı bar sinyaldir
- aynı sembolde açık pozisyon varken yeni sinyal yeni işlem başlatmaz
- komisyon 10 bps her yön
- slippage 10 bps her yön
- aynı OHLC barında stop ve hedef birlikte görünürse STOP önce
- geçmiş veri gözlenmiştir; gerçek bağımsız doğrulama gelecekte oluşacak yeni barlardır

## Run ID'leri

- Entry A/B/C: `34171064525`
- SAT robustness: `34171281778`
- İlk 1D tight plateau: `34171774133`
- İlk 4H tight plateau: `34171925181`
- Genişletilmiş 4H lower plateau: `34172568338`
- Genişletilmiş 1D lower plateau: `34172574886`
- İlk TP1 BE kontrolü: `34172047673`
- Final 0.5 ATR TP1 BE kontrolü: `34172922392`
