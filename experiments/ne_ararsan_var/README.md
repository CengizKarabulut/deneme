# NE ARARSAN VAR — Araştırma Kaydı

Bu klasör, “Ne Ararsan Var” taramasının production’a alınmadan önce yapılan bütün araştırmalarını toplar.

## Güncel ortak trend iskeleti

Production adayı 1D ve 1W için:

```text
Close > EMA5 > EMA8 > EMA13
AND 30 < RSI14 < 60
AND RVOL20 > 1.50
AND MACD_HIST[t] > MACD_HIST[t-1] > MACD_HIST[t-2]
```

Bilinçli olarak kaldırılanlar:
- CCI yok
- StochRSI yok
- MACD crossover zorunluluğu yok
- Histogramın pozitif/negatif olması zorunlu değil

Histogram işareti yalnız rapor bağlamı olarak kullanılabilir:
- `H < 0 ve yükseliyor` → erken momentum toparlanması
- `H > 0 ve yükseliyor` → teyitli momentum güçlenmesi

## Deney özeti

### 1) İlk crossover baseline + SAT optimizasyonu

İlk sürümde MACD bullish crossover kullanıldı. Yapısal stop, 1R/2R/3R kademeli kâr alma, runner, ATR trailing ve teknik SAT kombinasyonları araştırıldı.

İlk OOS çalışmalarında 4H/1D/1W pozitif; 15m–1H zayıf, 2H sınırda, 1M örneklem yetersizdi.

### 2) Timeframe’e özel SAT walk-forward

15m, 30m, 45m, 1H ve 2H için ayrı SAT aileleri test edildi. Ayrıntılar `reports/tf-exit-summary.md` içindedir.

Ana ders:
- timeframe’e göre farklı SAT mantığı gereklidir,
- fakat 15m–1H yalnız SAT değiştirerek kurtarılamadı,
- 2H araştırmaya değer kaldı.

### 3) MACD histogram AL + SAT walk-forward

Histogram eğimi girişte, histogram tabanlı hard-exit/adaptif trailing ise SAT tarafında test edildi. Ayrıntılar `reports/histogram-summary.md` içindedir.

Ana sonuç:
- 1D: güçlü walk-forward
- 1W: çok güçlü walk-forward
- 4H: pozitif ama rejim kararsız
- 2H: histogram, eski crossover araştırmasından zayıf
- 15m–1H: reddedildi
- 1M: umut verici ama örneklem yetersiz

Histogram hard-SAT kuralları güçlü timeframe’lerde yapısal SAT’ın üzerine güvenilir katkı sağlamadı.

### 4) 1D/1W sabit-kural histogram robustness

Altı giriş varyantı dört kronolojik pencerede sabit tutuldu. Ayrıntılar `reports/histogram-robustness-summary.md` içindedir.

#### 1D production adayı

- İşlem: `5,320`
- PF: `1.512`
- Expectancy: `+0.242R`
- Pozitif pencere: `4/4`

SAT:
- son 7 mum swing low − `0.20 ATR`
- TP1 `+1R` → %30
- TP2 `+2R` → %30
- TP3 `+3R` → %20
- runner %20
- TP1 sonrası otomatik break-even yok
- TP2 sonrası `2.3 ATR` trailing
- maksimum 40 mum
- histogram hard-SAT yok

#### 1W production adayı

- İşlem: `1,964`
- PF: `3.163`
- Expectancy: `+0.743R`
- Pozitif pencere: `4/4`

SAT:
- son 9 mum swing low − `0.15 ATR`
- TP1 `+1R` → %30
- TP2 `+2R` → %30
- TP3 `+3R` → %20
- runner %20
- TP1 sonrası otomatik break-even yok
- TP2 sonrası `2.3 ATR` trailing
- maksimum 80 mum
- histogram hard-SAT yok

### 5) 4H nihai sabit-kural karşılaştırması

Sadeleştirilmiş ortak iskelet üzerinde CCI ve StochRSI olmadan dört MACD tetikleyicisi aynı 4H SAT ile karşılaştırıldı.

Sabit 4H SAT:
- son 9 mum swing low − `0.15 ATR`
- 1R / 2R / 3R (%30 / %30 / %20)
- %20 runner
- TP2 sonrası `1.7 ATR` trailing
- maksimum 40 mum

#### MACD bullish crossover

- İşlem: `1,025`
- PF: `1.459`
- Expectancy: `+0.222R`
- Kazanma: `%48.0`
- Pozitif pencere: `2/4`
- Fold expectancy: `-0.035R / +0.441R / +0.431R / -0.143R`

#### Negatif histogram yükselişi

- İşlem: `734`
- PF: `1.296`
- Expectancy: `+0.152R`
- Pozitif pencere: `2/4`
- Fold expectancy: `-0.099R / +0.404R / +0.106R / -0.114R`

Sonuç: crossover toplam performansta daha iyi olsa da 4H’de dönemler arası kararlılık production barajını geçmedi.

## Nihai karar

- **1D: ACTIVE production adayı**
- **1W: ACTIVE production adayı**
- **4H: RESEARCH / erken uyarı; production sinyali değil**
- **2H: RESEARCH**
- **15m / 30m / 45m / 1H: REJECT**
- **1M: RESEARCH / örneklem yetersiz**

Bu nedenle `NE ARARSAN VAR` şu aşamada production tarafında yalnız **1D + 1W** olarak eklenmelidir. 4H aynı isim altında aktif tarama sonucu üretmemeli; istenirse araştırma/erken-uyarı katmanında ayrıca gösterilebilir.

Nihai kararın ayrıntılı kaydı: `reports/final-decision.md`.

## Metodoloji notu

Önceki final holdout bir kez görüldükten sonra sonraki çalışmalar aynı tarihi tekrar “dokunulmamış OOS” diye adlandırmadı. Son aşamalar sabit-kural robustness ve kronolojik pencere testleriyle yürütüldü. Gerçek son doğrulama gelecekte gelecek yeni veride forward izleme ile sürmelidir.
