# 8 - TavanTarama — Nihai Karar

Tarih: 2026-09-07

## Orijinal tarama

- DMI(14) +DI > -DI
- +DI, ADX(14)'i yukarı keser
- RSI(14) 30-70
- StochRSI(3,3,14,14) K, D'yi yukarı keser
- RVOL20 > 1.20

## DMI tetikleyici karşılaştırması

İki ana yöntem aynı veri, maliyet ve yapısal SAT altında doğrudan karşılaştırıldı:

**A — Orijinal**

`+DI > -DI AND +DI[t] > ADX[t] AND +DI[t-1] <= ADX[t-1]`

**B — Alternatif**

`+DI[t] > -DI[t] AND +DI[t-1] <= -DI[t-1] AND ADX[t] > ADX[t-1]`

Kontrollü filtreler:

- RSI: 30-70 / 40-70 / 50-70
- StochRSI: fresh K>D crossover veya yalnız K>D teyidi
- RVOL20: >1.20 veya >1.50

RVOL20 = `Volume[t] / mean(Volume[t-1]..Volume[t-20])`; mevcut bar ortalamaya dahil değildir ve her timeframe kendi barlarını kullanır.

## 15m–1M giriş aşaması

| TF | En iyi giriş | İşlem | PF | E(R) | Pozitif fold | Karar |
|---|---|---:|---:|---:|---:|---|
| 15m | Orijinal, RSI50-70, Stoch teyit, RV1.2 | 10,024 | 0.257 | -0.868 | 0/4 | REJECT |
| 30m | Orijinal, RSI30-70, Stoch cross, RV1.5 | 4,787 | 0.445 | -0.510 | 0/4 | REJECT |
| 45m | Orijinal, RSI50-70, Stoch cross, RV1.5 | 4,730 | 0.610 | -0.310 | 0/4 | REJECT |
| 1H | Orijinal, RSI30-70, Stoch cross, RV1.5 | 2,298 | 0.616 | -0.298 | 0/4 | REJECT |
| 2H | Orijinal, RSI50-70, Stoch cross, RV1.2 | 4,395 | 0.904 | -0.063 | 1/4 | REJECT |
| 4H | Orijinal, RSI50-70, Stoch teyit, RV1.2 | 4,727 | 1.123 | +0.065 | 3/4 | PROMISING |
| 1D | Orijinal, RSI50-70, Stoch cross, RV1.5 | 970 | 1.426 | +0.213 | 4/4 | STRONG |
| 1W | Orijinal, RSI40-70, Stoch cross, RV1.5 | 373 | 2.911 | +0.715 | 4/4 | STRONG |
| 1M | Orijinal, RSI30-70, Stoch teyit, RV1.2 | 56 | 4.744 | +0.867 | 3/4 | RESEARCH |

## Orijinal vs alternatif — önemli TF'ler

Baseline doğrudan karşılaştırma:

| TF | Orijinal PF / E(R) / fold | Alternatif PF / E(R) / fold | Karar |
|---|---|---|---|
| 4H | 1.105 / +0.058 / 2/4 | 1.174 / +0.092 / 3/4 | İlk aşama karışık; SAT sonrası tekrar karşılaştırıldı |
| 1D | 1.335 / +0.171 / 4/4 | 1.236 / +0.124 / 3/4 | Orijinal |
| 1W | 2.583 / +0.645 / 4/4 | 2.466 / +0.547 / 4/4 | Orijinal |

### 4H neden yine orijinal seçildi?

4H'de iki yöntem de ayrıca SAT robustness'a alındı.

- Alternatif final: 879 işlem, PF 1.676, +0.193R, 3/4 pozitif, en kötü fold -0.104R.
- Orijinal final: 5,496 işlem, PF 1.409, +0.108R, 3/4 pozitif, en kötü fold -0.006R.

Alternatif toplam rakamda daha yüksek görünse de örneklemi çok daha küçük ve negatif fold'u belirgin şekilde daha kötü. Orijinal neredeyse 4/4 sınırında ve çok daha geniş örneklemli. Bu yüzden 4H research/secondary referansı olarak orijinal seçildi; yine de 4H production ACTIVE yapılmadı.

## Nihai timeframe kararları

- 15m / 30m / 45m / 1H / 2H: **REJECT**
- 4H: **RESEARCH_SECONDARY**
- 1D: **ACTIVE**
- 1W: **ACTIVE**
- 1M: **RESEARCH_FORWARD_WATCH**

## 1D — ACTIVE

### Giriş

- +DI > -DI
- +DI, ADX'i aşağıdan yukarı yeni keser
- RSI14: 50 <= RSI < 70
- StochRSI K, D'yi yukarı yeni keser
- RVOL20 > 1.50

### SAT

ADX düşüşü hard-SAT değil, risk yönetimi olarak kullanılır.

- İlk stop: son 9 günlük bar swing low - 0.25 ATR(14)
- İlk risk 0.60–2.60 ATR arasında sınırlandırılır
- TP1 = 1.1R, %30
- TP2 = 2.2R, %30
- TP3 = 3.3R, %20
- Runner = %20
- Normal trailing: TP2 sonrası 2.0 ATR
- ADX iki ardışık bar düşerse (`ADX[t] < ADX[t-1] < ADX[t-2]`) trailing 1.5 ATR'ye sıkılaşır ve yeniden gevşemez
- DMI/ADX hard-SAT yok
- Maksimum taşıma = 40 günlük bar
- TP1 sonrası break-even yok

Nihai: **1,030 işlem, PF 1.766, +0.215R, %45.73 kazanma, 4/4 pozitif, en kötü fold +0.131R.**

## 1W — ACTIVE

Giriş aşamasında fresh Stoch crossover en yüksek worst-fold skorunu verdi; ancak daha geniş örneklemli `K>D` teyit varyantı da güçlü bir plato oluşturdu. Production için daha geniş örneklemli ve daha sade teyit varyantı donduruldu:

### Giriş

- +DI > -DI
- +DI, ADX'i aşağıdan yukarı yeni keser
- RSI14: 40 <= RSI < 70
- StochRSI K > D (kesişim şartı değil, teyit)
- RVOL20 > 1.50

### SAT

DMI/ADX teknik çıkışları haftalıkta performansı düşürdü; yapısal SAT kazandı.

- İlk stop: son 11 haftalık bar swing low - 0.15 ATR
- TP1 = 1.1R, %30
- TP2 = 2.2R, %30
- TP3 = 3.3R, %20
- Runner = %20
- TP2 sonrası 2.1 ATR trailing
- Hard DMI/ADX SAT yok
- Maksimum taşıma = 80 haftalık bar
- TP1 sonrası break-even yok

Nihai: **1,104 işlem, PF 3.301, +0.839R, %58.88 kazanma, 4/4 pozitif, en kötü fold +0.257R.**

## 4H — RESEARCH_SECONDARY

### Referans giriş

- +DI > -DI
- +DI, ADX'i aşağıdan yukarı yeni keser
- RSI14: 50 <= RSI < 70
- StochRSI K > D
- RVOL20 > 1.20

### Referans SAT

- Son 9 adet 4H bar swing low - 0.25 ATR
- TP1/TP2/TP3 = 1.1R / 2.2R / 3.3R
- TP2 sonrası normal trail 1.8 ATR
- ADX iki ardışık bar düşerse trail 1.3 ATR'ye sıkılaşır
- Maksimum taşıma 60 bar
- BE yok

Sonuç: **5,496 işlem, PF 1.409, +0.108R, 3/4 pozitif, en kötü fold -0.006R.** Neredeyse kararlı fakat hâlâ bir kronolojik dönem negatiftir; ACTIVE yapılmaz.

## 1M — RESEARCH_FORWARD_WATCH

Referans giriş:

- Orijinal +DI→ADX tetikleyicisi
- RSI30-70
- StochRSI K>D teyidi
- RVOL20 > 1.20

56 işlemde PF 4.744 / +0.867R görünse de yalnız 3/4 dönem pozitif ve en kötü fold yaklaşık -0.771R'dir. Örneklem ve rejim kararlılığı yetersiz olduğundan production'a alınmaz.

## TP1 break-even nihai kontrolü

| TF | NO-BE E(R) | Entry-BE E(R) | Cost-BE E(R) | Karar |
|---|---:|---:|---:|---|
| 4H research | +0.108 | +0.084 | +0.083 | NO-BE |
| 1D | +0.215 | +0.180 | +0.177 | NO-BE |
| 1W | +0.839 | +0.701 | +0.699 | NO-BE |

BE kazanma oranını artırsa da expectancy'yi düşürür; TP1 sonrası stop giriş/maliyet seviyesine taşınmaz.

## Uygulama semantiği

- Sinyal yalnız tamamlanmış barda hesaplanır.
- İşlem referansı bir sonraki bar açılışıdır.
- Komisyon: 10 bps her yön.
- Slippage: 10 bps her yön.
- Aynı OHLC barda stop ve hedef birlikte görünürse STOP önceliklidir.
- İlk risk 0.60–2.60 ATR arasında sınırlandırılır.
- Fresh crossover koşulları yalnız kesişim barında sinyal üretir.
- Geçmiş veri artık gözlenmiştir; bundan sonraki gerçek bağımsız doğrulama gelecekte oluşacak yeni barlardır.

Araştırma run ID'leri:

- Entry stage: `34159048200`
- SAT robustness: `34159383049`
- TP1 BE A/B: `34159832908`
