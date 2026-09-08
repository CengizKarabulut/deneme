# 13 - MACD YenidenHareket — Nihai Karar

Tarih: 2026-09-08

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

A/B/C aynı yapısal SAT kontrol profili, aynı maliyet modeli ve her varyantın kendi sinyal zamanlarından oluşan dört kronolojik pencereyle karşılaştırıldı.

## Giriş aşaması özeti

| TF | En anlamlı sonuç | PF | E(R) | Fold | Karar |
|---|---|---:|---:|---:|---|
| 15m | tüm A/B/C negatif | < 1 | negatif | 0/4 | REJECT |
| 30m | tüm A/B/C negatif | < 1 | negatif | 0/4 | REJECT |
| 45m | tüm A/B/C negatif | < 1 | negatif | 0/4 | REJECT |
| 1H | tüm A/B/C negatif | < 1 | negatif | 0/4 | REJECT |
| 2H | B en yakını | 0.977 | -0.015 | 1/4 | REJECT |
| 4H | C | 1.158 | +0.084 | 3/4 | SAT research |
| 1D | C | 1.538 | +0.256 | 4/4 | güçlü |
| 1W | A | 3.021 | +0.707 | 4/4 | güçlü |
| 1M | A | 3.538 | +0.694 | 4/4 | küçük/dağılımı zayıf örneklem |

4H'de A'nın ham yapısal sonucu C'den daha yüksek toplam PF/E üretse de yalnız 2/4 pozitif dönemdi. C 3/4 idi ve MACD tabanlı SAT altında hem A'yı geçti hem 4/4'e ulaştı. Bu nedenle 4H final giriş C'dir.

1D'de C açık biçimde kazandı: yapısal kontrol altında 10.241 işlem, PF 1.538, +0.256R ve 4/4 pozitif dönem.

1W'de orijinal A en iyi toplam edge'i verdi. B ve C de 4/4 kaldı ancak toplam expectancy/PF daha düşüktü; orijinal sade kural korundu.

1M'de A güçlü görünse de final yapısal simülasyonda yalnız 152 işlem vardır ve kronolojik dönem dağılımı eşit değildir (bir fold yalnız yaklaşık 12 tamamlanmış işlem içerir). Bu nedenle production ACTIVE yapılmadı.

## 4H — ACTIVE_SECONDARY

Nihai giriş C:

- MACD Level > 0
- MACD Level > Signal
- Histogram[t] > Histogram[t-1] > Histogram[t-2]
- koşulun yalnız yeni başlayan epizodu sinyaldir

Ham yapısal giriş: 12.510 işlem, PF 1.158, +0.084R, 3/4 pozitif; worst-fold -0.107R.

MACD Level'ın Signal altına düşmesini hard-SAT yapmak yerine trailing'i sıkılaştırmak çok daha iyi çalıştı.

Final SAT:

- ilk stop: son 7 adet 4H swing low - 0.20 ATR
- fallback stop: 1.20 ATR
- ilk risk 0.60–2.60 ATR arasında sınırlandırılır
- TP1 = 1.0R, %30
- TP2 = 2.0R, %30
- TP3 = 3.0R, %20
- runner = %20
- TP2 sonrası normal trailing = 2.0 ATR
- MACD Level < Signal olursa trailing = 1.0 ATR olur ve tekrar gevşemez
- MACD zayıflaması tight trailing'i TP2'den önce de aktive edebilir
- teknik hard exit yok
- maksimum taşıma = 40 adet 4H bar
- TP1 sonrası break-even yok

Tight-trail plateau taramasında 1.8 ATR'den 0.8 ATR'ye kadar sıkılaştırıldıkça tarihsel PF, expectancy ve worst-fold monoton iyileşti. 0.8 ATR tarihsel olarak daha yüksek sonuç vermesine rağmen production'da sınır optimumunu kovalamamak ve whipsaw riskini azaltmak için 1.0 ATR doğal alt sınır olarak seçildi.

Final: **16.604 işlem, PF 2.437, +0.327R, %57.75 kazanma, 4/4 pozitif, worst-fold +0.270R.**

Ham giriş 3/4 iken MACD tabanlı risk yönetimiyle 4/4'e çıktığı için 4H PRIMARY değil, **ACTIVE_SECONDARY** tutulur.

## 1D — ACTIVE

Nihai giriş C aynıdır.

Ham yapısal giriş: 10.241 işlem, PF 1.538, +0.256R, 4/4 pozitif; worst-fold +0.116R.

Final SAT:

- ilk stop: son 7 günlük swing low - 0.20 ATR
- fallback stop: 1.25 ATR
- TP1 = 1.0R, %30
- TP2 = 2.0R, %30
- TP3 = 3.0R, %20
- runner = %20
- TP2 sonrası normal trailing = 2.2 ATR
- MACD Level < Signal olursa trailing = 1.0 ATR olur ve tekrar gevşemez
- MACD zayıflaması tight trailing'i TP2'den önce de aktive edebilir
- teknik hard exit yok
- maksimum taşıma = 40 günlük bar
- TP1 sonrası break-even yok

1D tight-trail plateau da 1.8 → 0.8 ATR boyunca monoton iyileşti. 0.8 ATR'de PF 3.477 / +0.464R görülmesine rağmen aynı anti-overfit/whipsaw gerekçesiyle production alt sınırı 1.0 ATR'de tutuldu.

Final: **13.621 işlem, PF 3.022, +0.419R, %59.46 kazanma, 4/4 pozitif, worst-fold +0.330R.**

## 1W — ACTIVE

Nihai giriş A — orijinal:

- MACD Level > 0
- MACD Level fresh crosses above Signal

Haftalıkta MACD<Signal tabanlı tight/hard exit toplam expectancy'yi düşürdü. Sade yapısal yönetim kazandı.

Final SAT:

- ilk stop: son 9 haftalık swing low - 0.15 ATR
- fallback stop: 1.30 ATR
- TP1 = 1.0R, %30
- TP2 = 2.0R, %30
- TP3 = 3.0R, %20
- runner = %20
- TP2 sonrası 2.3 ATR trailing
- teknik hard exit yok
- maksimum taşıma = 60 haftalık bar
- TP1 sonrası break-even yok

Dar komşulukta swing11/buffer0.20/trail2.1/1.1-2.2-3.3R profili +0.742R verdi; baseline +0.707R idi. Ancak worst-fold yalnız +0.006R iyileşti ve daha fazla parametre değişikliği gerektirdi. Materiality/complexity gate nedeniyle sade baseline korundu.

Final: **1.949 işlem, PF 3.021, +0.707R, %58.70 kazanma, 4/4 pozitif, worst-fold +0.270R.**

## 1M — RESEARCH_FORWARD_WATCH

Nihai araştırma girişi A — orijinal.

Yapısal baseline:

- swing 9
- buffer 0.15 ATR
- fallback stop 1.30 ATR
- TP1/TP2/TP3 = 1/2/3R
- trail 2.5 ATR
- max hold 36 aylık bar
- NO-BE

Final tarihsel sonuç: **152 işlem, PF 3.538, +0.694R, %61.18 kazanma, 4/4 pozitif, worst-fold +0.042R.**

Örneklem küçük ve fold dağılımı dengesiz olduğundan ACTIVE değildir; yeni aylık sinyallerle forward-watch tutulur.

## TP1 break-even final kontrolü

| TF | NO-BE E(R) | Entry-BE E(R) | Cost-BE E(R) | Karar |
|---|---:|---:|---:|---|
| 4H | +0.327 | +0.260 | +0.256 | NO-BE |
| 1D | +0.419 | +0.355 | +0.353 | NO-BE |
| 1W | +0.707 | +0.612 | +0.612 | NO-BE |
| 1M | +0.694 | +0.570 | +0.572 | NO-BE / research |

BE bazı timeframe'lerde kazanma oranını artırsa da expectancy ve worst-fold avantajını düşürdü. TP1 sonrası stop giriş veya maliyet seviyesine taşınmaz.

## Nihai timeframe kararları

- 15m / 30m / 45m / 1H / 2H: **REJECT**
- 4H: **ACTIVE_SECONDARY — C histogram reacceleration**
- 1D: **ACTIVE — C histogram reacceleration**
- 1W: **ACTIVE — A original MACD positive-zone bullish cross**
- 1M: **RESEARCH_FORWARD_WATCH — A original**

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

- Entry A/B/C başarılı koşu: `34171064525`
- SAT robustness: `34171281778`
- 1D tight plateau: `34171774133`
- 4H tight plateau: `34171925181`
- TP1 BE final: `34172047673`
