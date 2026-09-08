# 14 - MACD DipDönüşü — Nihai Karar

Tarih: 2026-09-08  
Durum: **LOCKED**

## Giriş adayları

### A — Saf Dip Dönüşü
- MACD(12,26,9) Level < 0
- MACD Level fresh bullish crosses Signal
- RVOL filtresi yok

### B — Orijinal
- MACD Level < 0
- MACD Level fresh bullish crosses Signal
- RVOL20 > 1.20

### C — Güçlü Hacim
- MACD Level < 0
- MACD Level fresh bullish crosses Signal
- RVOL20 > 1.50

RVOL20 = Volume[t] / mean(Volume[t-1] ... Volume[t-20]); mevcut bar ortalamaya dahil edilmez.

## Giriş aşaması özeti

| TF | En anlamlı giriş | PF | E(R) | Fold | Karar |
|---|---|---:|---:|---:|---|
| 15m | C | <1 | negatif | 0/4 | REJECT |
| 30m | C | <1 | negatif | 0/4 | REJECT |
| 45m | C | <1 | negatif | 0/4 | REJECT |
| 1H | A/C | <1 | negatif | 0/4 | REJECT |
| 2H | C | 0.911 | -0.059 | 1/4 | REJECT |
| 4H | C | 1.202 | +0.104 | 3/4 | SAT research |
| 1D | A | 1.414 | +0.205 | 3/4 | SAT research |
| 1W | C | 2.719 | +0.652 | 4/4 | güçlü; A da güçlü |
| 1M | A | 10.200 | +1.254 | 3/4 | çok küçük örneklem |

RVOL etkisi timeframe'e göre değişti. 4H'de RVOL>1.50 kaliteyi artırdı. 1D'de RVOL filtresi toplam edge'i düşürdü. 1W'de RVOL>1.50 küçük bir sayısal iyileşme sağladı ancak örneklemi yaklaşık üçte bire düşürdü; materiality/sample-size gate nedeniyle sade A korundu.

## 4H — ACTIVE_SECONDARY

Final giriş: **C — MACD<0 bullish cross + RVOL20>1.50**.

Ham yapısal kontrol: **4.220 işlem, PF 1.202, +0.104R, 3/4 pozitif, worst-fold -0.166R.**

En iyi SAT ailesi `fail_tighten` oldu: MACD yeniden Signal altına düşerken MACD hâlâ negatif bölgedeyse işlem doğrudan kapatılmaz; trailing sıkılaştırılır ve tekrar gevşemez.

Final profil:
- ilk stop: son 7 adet 4H swing low - 0.20 ATR
- fallback stop: 1.20 ATR
- ilk risk 0.60–2.60 ATR arasında sınırlandırılır
- TP1 = 1.0R, %30
- TP2 = 2.0R, %30
- TP3 = 3.0R, %20
- runner = %20
- TP2 sonrası normal trail = 2.0 ATR
- MACD<Signal ve MACD<0 olduğunda sticky tight trail = **0.8 ATR**
- tight trail TP2'den önce de aktive olabilir
- teknik hard exit yok
- max hold = 40 adet 4H bar
- TP1 sonrası BE yok

Tight plateau 0.6–1.6 ATR aralığında 4/4 pozitif kaldı ve sıkılaştıkça tarihsel sonuç iyileşti. 0.6 sınır optimumunu kovalamamak için 0.8 ATR kilitlendi.

Final NO-BE: **4.498 işlem, PF 2.163, +0.360R, %58.14 kazanma, 4/4 pozitif, worst-fold +0.156R.**

Ham giriş 3/4 iken risk yönetimiyle 4/4'e çıktığı için **ACTIVE_SECONDARY**.

## 1D — ACTIVE_SECONDARY

Final giriş: **A — RVOL filtresiz saf dip dönüşü**.

Ham yapısal kontrol: **8.797 işlem, PF 1.414, +0.205R, 3/4 pozitif, worst-fold -0.105R.**

RVOL1.5 C aynı SAT ailesinde daha yüksek worst-fold verdi ancak daha az işlem ve daha düşük toplam expectancy üretti. A daha geniş örneklem ve daha yüksek toplam edge nedeniyle final seçildi.

Final profil:
- ilk stop: son 7 günlük swing low - 0.20 ATR
- fallback stop: 1.25 ATR
- TP1/TP2/TP3 = 1.0/2.0/3.0R
- dağılım %30/%30/%20 + %20 runner
- TP2 sonrası normal trail = 2.2 ATR
- MACD<Signal ve MACD<0 olduğunda sticky tight trail = **0.8 ATR**
- teknik hard exit yok
- max hold = 40 gün
- TP1 sonrası BE yok

Tight plateau 0.6–1.8 ATR boyunca 4/4 pozitif kaldı ve sıkılaştıkça sonuç iyileşti; 0.8 ATR alt sınırın bir adım içinde donduruldu.

Final NO-BE: **10.060 işlem, PF 2.387, +0.421R, %57.49 kazanma, 4/4 pozitif, worst-fold +0.170R.**

Ham giriş 3/4 olduğu için **ACTIVE_SECONDARY**.

## 1W — ACTIVE

Final giriş: **A — RVOL filtresiz saf dip dönüşü**.

Ham yapısal kontrol: **2.456 işlem, PF 2.628, +0.625R, 4/4 pozitif, worst-fold +0.255R.**

RVOL1.5 C sayısal olarak biraz daha yüksek sonuç verdi ancak yaklaşık üçte bir örneklem kullandı. Fark materiality gate'i geçmedi; sade A korundu.

Final profil:
- ilk stop: son 11 haftalık swing low - 0.15 ATR
- fallback stop: 1.30 ATR
- TP1/TP2/TP3 = 1.1/2.2/3.3R
- dağılım %30/%30/%20 + %20 runner
- TP2 sonrası normal trail = 2.3 ATR
- MACD<Signal ve MACD<0 olduğunda sticky tight trail = **1.2 ATR**
- teknik hard exit yok
- max hold = 60 hafta
- TP1 sonrası BE yok

1.0–2.2 ATR tight plateau 4/4 pozitif kaldı; sınır optimumunu kovalamamak için 1.2 ATR seçildi.

Final NO-BE: **2.890 işlem, PF 3.590, +0.687R, %60.52 kazanma, 4/4 pozitif, worst-fold +0.404R.**

Giriş kendi başına da 4/4 olduğundan **ACTIVE**.

## 1M — RESEARCH_FORWARD_WATCH

Final araştırma girişi A.

Yapısal profil: swing9, buffer0.15 ATR, fallback1.30 ATR, 1/2/3R, TP2 sonrası 2.5 ATR trail, max hold36 ay, NO-BE.

Tarihsel sonuç: **57 işlem, PF 10.200, +1.254R, %77.19 kazanma, 3/4; worst-fold 0.0R.**

Örneklem aşırı küçük ve kronolojik dağılım yetersizdir; production'a alınmaz.

## TP1 break-even final kontrolü

| TF | NO-BE E(R) | Entry-BE | Cost-BE | Karar |
|---|---:|---:|---:|---|
| 4H | +0.360 | +0.242 | +0.241 | NO-BE |
| 1D | +0.421 | +0.311 | +0.310 | NO-BE |
| 1W | +0.687 | +0.539 | +0.540 | NO-BE |
| 1M | +1.254 | +0.992 | +0.994 | NO-BE / research |

BE kazanma oranını artırsa bile expectancy ve worst-fold kalitesini düşürdü.

## Nihai karar

- 15m / 30m / 45m / 1H / 2H: **REJECT**
- 4H: **ACTIVE_SECONDARY — C / RVOL20>1.50**
- 1D: **ACTIVE_SECONDARY — A / RVOL yok**
- 1W: **ACTIVE — A / RVOL yok**
- 1M: **RESEARCH_FORWARD_WATCH**

## Ortak uygulama semantiği

- MACD parametreleri 12,26,9
- fresh bullish cross: MACD[t] > Signal[t] ve MACD[t-1] <= Signal[t-1]
- sinyal barında MACD[t] < 0
- yalnız tamamlanmış bar
- giriş referansı t+1 open
- aynı sembolde açık pozisyon varken yeni sinyal yeni işlem başlatmaz
- komisyon 10 bps / yön
- slippage 10 bps / yön
- aynı OHLC barında stop ve hedef görünürse STOP önce
- geçmiş veri gözlenmiştir; gerçek bağımsız doğrulama gelecekte oluşacak yeni barlardır

## Run ID'leri

- Entry A/B/C: `34194904986`
- SAT robustness: `34195285546`
- Tight plateau: `34195779015`
- TP1 BE: `34196187458`
