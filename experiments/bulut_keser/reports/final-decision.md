# 9 - BulutKeser — Nihai Karar

Tarih: 2026-09-08

## Orijinal tarama

- ADX(14): 20–40
- Bollinger Bands(20,2): Lower < Close < Upper
- RVOL20 > 1.20
- Ichimoku(9,26,52,26): Tenkan / Conversion Line, Kijun / Base Line'ı aşağıdan yukarı yeni keser

## Ichimoku / Kumo hesaplama semantiği

Tenkan = son 9 bar yüksek/düşük orta noktası.
Kijun = son 26 bar yüksek/düşük orta noktası.
Senkou A raw = (Tenkan + Kijun) / 2.
Senkou B raw = son 52 bar yüksek/düşük orta noktası.

Ichimoku grafiğinde Senkou A/B 26 bar ileri çizildiği için mevcut bardaki görünür Kumo, 26 bar önce hesaplanan raw span değerlerinden oluşur. Araştırmada `raw_span.shift(26)` kullanılmıştır. Bu nedenle geleceğe bakış / look-ahead yoktur.

Kumo top = max(displayed Senkou A, displayed Senkou B)
Kumo bottom = min(displayed Senkou A, displayed Senkou B)

## 1. aşama — Kumo üstü / içi / altı

Orijinal ADX, BB ve RVOL koşulları sabit tutuldu. Yalnız bullish Tenkan/Kijun cross barındaki Close'un mevcut Kumo'ya göre konumu ayrıldı.

### Ana sonuçlar

| TF | En anlamlı Kumo sınıfı | İşlem | PF | E(R) | Pozitif fold | Yorum |
|---|---|---:|---:|---:|---:|---|
| 15m | — | — | <1 | negatif | 0/4 | REJECT |
| 30m | — | — | <1 | negatif | 0/4 | REJECT |
| 45m | — | — | <1 | negatif | 0/4 | REJECT |
| 1H | Kumo içi | — | <1 | negatif | 0/4 | REJECT |
| 2H | Kumo içi | — | 0.886 | -0.077 | 1/4 | REJECT |
| 4H | Kumo içi | 388 | 1.116 | +0.064 | 2/4 | Research adayı |
| 1D | **Kumo altı** | 595 | **1.314** | **+0.166** | **4/4** | Güçlü erken-dönüş karakteri |
| 1W | **Kumo üstü** | 245 | **3.174** | **+0.751** | **4/4** | Güçlü trend-devam karakteri |
| 1M | — | yetersiz | — | — | — | INSUFFICIENT |

Haftalıkta Kumo filtresiz orijinal de 538 işlemde PF 3.670 / +0.881R / 4/4 üretmiştir; fakat worst-fold yalnız +0.022R iken Kumo-üstü modelde +0.074R olmuştur. Kumo üstü daha seçici fakat daha rejim-dayanıklı aday olarak tutulmuştur.

En önemli bulgu: Ichimoku sinyal gücü timeframe'e göre aynı yönde davranmamaktadır. Günlükte en güçlü sinyal Kumo altında oluşan erken toparlanma; haftalıkta ise Kumo üstünde oluşan trend-devam sinyalidir.

## 2. aşama — ADX / Bollinger / RVOL robustness

Kumo kararı dondurulduktan sonra yalnız şu filtreler karşılaştırıldı:

- ADX: 20–40 / >20 / 20–35
- BB: Lower<Close<Upper / Basis<Close<Upper / BB filtresi yok
- RVOL20: >1.20 / >1.50

### 1D kazanan giriş

- Tenkan fresh crosses above Kijun
- Close < Kumo bottom
- 20 <= ADX14 <= 35
- BB Basis < Close < BB Upper
- RVOL20 > 1.50

321 yapısal-kontrol işleminde PF 1.726 / +0.332R / 4/4 pozitif / worst-fold +0.211R.

### 1W kazanan giriş

- Tenkan fresh crosses above Kijun
- Close > Kumo top
- 20 <= ADX14 <= 35
- Bollinger filtresi yok
- RVOL20 > 1.50

419 yapısal-kontrol işleminde PF 3.713 / +0.868R / 4/4 pozitif / worst-fold +0.229R.

### 4H research girişi

- Tenkan fresh crosses above Kijun
- Close Kumo içinde
- ADX14 > 20
- BB Lower < Close < BB Upper
- RVOL20 > 1.20

Ham giriş yalnız 2/4 dönem pozitiftir; production kalitesi SAT yönetimiyle oluştuğu için PRIMARY yapılmaz.

## 3. aşama — Ichimoku SAT robustness

Test edilen çıkış aileleri:

- Yapısal swing + TP + ATR trailing
- Tenkan'ın Kijun'u aşağı kesmesi hard-SAT
- Close < Kijun hard-SAT
- Kijun/Kumo kaybında trailing sıkılaştırma
- adaptif Ichimoku çıkışı
- haftalıkta Kumo bottom kaybı hard-SAT

### 4H — ACTIVE_SECONDARY

Ichimoku burada SAT tarafında anlamlı katkı sağlamıştır.

Nihai giriş:

- Tenkan fresh crosses above Kijun
- Close Kumo içinde
- ADX14 > 20
- BB Lower < Close < BB Upper
- RVOL20 > 1.20

Nihai SAT:

- İlk stop: son 9 adet 4H bar swing low - 0.25 ATR(14)
- İlk risk 0.60–2.60 ATR arasında sınırlandırılır
- TP1 = 1.1R, %30
- TP2 = 2.2R, %30
- TP3 = 3.3R, %20
- Runner = %20
- TP2 sonrası normal trailing = 1.8 ATR
- Close < Kijun olursa trailing 1.2 ATR'ye sıkılaşır ve tekrar gevşemez
- Ichimoku hard-SAT yok
- Maksimum taşıma = 60 adet 4H bar
- TP1 sonrası break-even yok

Nihai sonuç: **415 işlem, PF 1.889, +0.240R, %47.23 kazanma, 4/4 pozitif, worst-fold +0.145R.**

Ham girişin 2/4'ten SAT ile 4/4'e taşınması nedeniyle bu timeframe **ACTIVE_SECONDARY** olarak sınıflandırılır; edge'in önemli kısmı risk yönetimine bağlıdır.

### 1D — ACTIVE

Ichimoku hard çıkışları günlükte edge'i düşürdü; yapısal SAT kazandı.

Nihai giriş:

- Tenkan fresh crosses above Kijun
- Close < Kumo bottom
- 20 <= ADX14 <= 35
- BB Basis < Close < BB Upper
- RVOL20 > 1.50

Nihai SAT:

- İlk stop: son 9 günlük bar swing low - 0.20 ATR
- TP1 = 1.1R, %30
- TP2 = 2.2R, %30
- TP3 = 3.3R, %20
- Runner = %20
- TP2 sonrası 2.0 ATR trailing
- Ichimoku hard-SAT yok
- Maksimum taşıma = 40 günlük bar
- TP1 sonrası break-even yok

Nihai sonuç: **320 işlem, PF 1.927, +0.408R, %50.94 kazanma, 4/4 pozitif, worst-fold +0.260R.**

Bu model klasik 'bulut üstü güçlü Ichimoku' sinyali değildir. Kumo altında fakat Bollinger'ın pozitif yarısında yeni Tenkan/Kijun kesişimi ile oluşan **erken toparlanma** modelidir.

### 1W — ACTIVE

Haftalıkta Ichimoku hard/trailing çıkışları toplam expectancy'yi düşürdüğü için final aile yapısaldır.

Nihai giriş:

- Tenkan fresh crosses above Kijun
- Close > Kumo top
- 20 <= ADX14 <= 35
- Bollinger filtresi yok
- RVOL20 > 1.50

Nihai SAT dar robustness sonucu:

- İlk stop: son 11 haftalık bar swing low - 0.20 ATR
- TP1 = 1.1R, %30
- TP2 = 2.2R, %30
- TP3 = 3.3R, %20
- Runner = %20
- TP2 sonrası 2.5 ATR trailing
- Ichimoku hard-SAT yok
- Maksimum taşıma = 80 haftalık bar
- TP1 sonrası break-even yok

Nihai sonuç: **401 işlem, PF 4.102, +0.993R, %63.59 kazanma, 4/4 pozitif, worst-fold +0.386R.**

Referans yapısal profil 419 işlemde PF 3.718 / +0.869R / worst-fold +0.232R idi. Dar yapısal komşulukta bulunan nihai profil hem expectancy hem PF hem de worst-fold tarafında anlamlı iyileşme sağladığı için kabul edilmiştir.

## TP1 break-even nihai kontrolü

| TF | NO-BE E(R) | Entry-BE E(R) | Cost-BE E(R) | Karar |
|---|---:|---:|---:|---|
| 4H | +0.240 | +0.194 | +0.184 | NO-BE |
| 1D | +0.408 | +0.366 | +0.358 | NO-BE |
| 1W | +0.993 | +0.837 | +0.836 | NO-BE |

Haftalıkta BE kazanma oranını yaklaşık %63.6'dan %72.7'ye yükseltse de expectancy'yi ciddi biçimde düşürmektedir. TP1 sonrası stop giriş/maliyet seviyesine taşınmaz.

## Nihai timeframe kararları

- 15m / 30m / 45m / 1H / 2H: **REJECT**
- 4H: **ACTIVE_SECONDARY**
- 1D: **ACTIVE**
- 1W: **ACTIVE**
- 1M: **INSUFFICIENT_SAMPLE / RESEARCH**

## Uygulama semantiği

- Sinyal yalnız tamamlanmış barda hesaplanır.
- İşlem referansı bir sonraki bar açılışıdır.
- Komisyon: 10 bps her yön.
- Slippage: 10 bps her yön.
- Aynı OHLC barında stop ve hedef birlikte görünürse STOP önceliklidir.
- İlk risk 0.60–2.60 ATR arasında sınırlandırılır.
- RVOL20 mevcut bar hariç önceki 20 aynı-timeframe barın ortalamasına göre hesaplanır.
- Aynı sembolde açık pozisyon varken yeni sinyal yeni işlem başlatmaz.
- Geçmiş veri artık gözlenmiştir; gerçek bağımsız doğrulama bundan sonra oluşacak yeni barlardır.

Araştırma run ID'leri:

- Kumo position stage: `34160686639`
- Filter robustness: `34160894762`
- Ichimoku SAT robustness: `34161108810`
- 1W structural final: `34161285218`
- İlk BE A/B (4H/1D doğrulama): `34161458031`
- 1W optimized-profile BE final: `34161660133`
