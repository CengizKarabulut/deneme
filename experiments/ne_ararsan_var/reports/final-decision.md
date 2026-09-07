# NE ARARSAN VAR — Nihai Araştırma Kararı

Tarih: 2026-09-07

Bu belge, taramanın production adayı olarak hangi zaman dilimlerinde ve hangi kurallarla kullanılacağını sabitler.

## Production kararı

- **1D: ACTIVE / validated historical robustness candidate**
- **1W: ACTIVE / validated historical robustness candidate**
- **4H: RESEARCH / early-warning only; production sinyali değil**
- **2H: RESEARCH**
- **15m / 30m / 45m / 1H: REJECT for this scan family**
- **1M: RESEARCH / insufficient sample**

## 1D ve 1W ortak AL kuralı

```text
Close > EMA5 > EMA8 > EMA13
AND 30 < RSI(14) < 60
AND RVOL(20) > 1.50
AND MACD_HIST[t] > MACD_HIST[t-1] > MACD_HIST[t-2]
```

Kullanılmayan filtreler:

```text
CCI: YOK
StochRSI: YOK
MACD crossover zorunluluğu: YOK
Histogram > 0 / < 0 zorunluluğu: YOK
```

Histogram işareti yalnız bağlam olarak raporlanabilir:
- H < 0 ve yükseliyor: erken momentum toparlanması
- H > 0 ve yükseliyor: teyitli momentum güçlenmesi

Sinyal yalnız koşulun False -> True olduğu ilk tamamlanmış mumda oluşur. Backtest yürütmesinde giriş bir sonraki mum açılışıdır.

## 1D SAT

- İlk stop: son 7 mum swing low - 0.20 ATR(14)
- TP1: +1R -> %30
- TP2: +2R -> %30
- TP3: +3R -> %20
- Runner: %20
- TP1 sonrası otomatik break-even: YOK
- TP2 sonrası trailing: 2.3 ATR
- Maksimum taşıma: 40 mum
- Histogram hard-SAT: YOK

Robustness: işaret-serbest / CCI-yok sürüm 5,320 işlem, PF 1.512, expectancy +0.242R, 4/4 pozitif kronolojik pencere.

## 1W SAT

- İlk stop: son 9 mum swing low - 0.15 ATR(14)
- TP1: +1R -> %30
- TP2: +2R -> %30
- TP3: +3R -> %20
- Runner: %20
- TP1 sonrası otomatik break-even: YOK
- TP2 sonrası trailing: 2.3 ATR
- Maksimum taşıma: 80 mum
- Histogram hard-SAT: YOK

Robustness: işaret-serbest / CCI-yok sürüm 1,964 işlem, PF 3.163, expectancy +0.743R, 4/4 pozitif kronolojik pencere.

## 4H son karşılaştırma

Sadeleştirilmiş ortak iskelet üzerinde CCI ve StochRSI olmadan dört sabit MACD tetikleyicisi karşılaştırıldı. SAT bütün adaylarda sabit tutuldu:

- 9 mum swing low - 0.15 ATR
- 1R / 2R / 3R (%30 / %30 / %20)
- %20 runner
- TP2 sonrası 1.7 ATR trailing
- maksimum 40 mum

### MACD bullish crossover

- 1,025 işlem
- PF 1.459
- expectancy +0.222R
- kazanma %48.0
- pozitif kronolojik pencere: 2/4
- fold expectancy: -0.035R / +0.441R / +0.431R / -0.143R

### Negatif histogram yükselişi

- 734 işlem
- PF 1.296
- expectancy +0.152R
- pozitif kronolojik pencere: 2/4
- fold expectancy: -0.099R / +0.404R / +0.106R / -0.114R

Histogram işaret-serbest ve pozitif histogram varyantları da yalnız 2/4 pozitif pencere üretti.

### 4H kararı

Crossover toplam performansta histogram varyantlarından daha iyi olsa da dönemler arası kararlılık production barajını geçmedi. Bu nedenle **4H aktif production sinyali olarak eklenmeyecek**. İstenirse Telegram/rapor tarafında `erken uyarı / research` etiketiyle ayrı gösterilebilir. Gelecekte yeni forward veri üzerinde yeniden değerlendirilecektir.

## Nihai tarama kimliği

`NE ARARSAN VAR` production adayı şu aşamada **1D + 1W momentum/trend taraması**dır. 4H aynı isim altında aktif sinyal üretmez; research katmanında tutulur.

Bu karar, görülmüş tarih üzerinde robustness araştırmasına dayanır. Gerçek nihai doğrulama yeni gelecek veride forward izleme ile devam etmelidir.
