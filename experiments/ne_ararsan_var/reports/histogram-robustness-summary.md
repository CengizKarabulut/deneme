# NE ARARSAN VAR — Histogram Fixed-Rule Robustness

Run: `34136277109`

## Amaç

1D ve 1W için şu iki belirsizliği kapatmak:

1. MACD histogramın pozitif/negatif olması production giriş şartı olmalı mı?
2. `-100 < CCI20 < 100` filtresi gerçekten değer katıyor mu?

Bu turda fold bazında kural seçilmedi. Altı giriş varyantının her biri dört kronolojik pencerede **sabit** tutuldu. Çıkış da sabit `control_123` yapısal modeliydi. Bu çalışma daha önce görülmüş tarih üzerinde robustness araştırmasıdır; yeni untouched holdout değildir.

Ortak giriş:
- `Close > EMA5 > EMA8 > EMA13`
- `30 < RSI14 < 60`
- `RVOL20 > 1.50`
- `H[t] > H[t-1] > H[t-2]`
- StochRSI yok

Maliyet:
- 10 bps komisyon / taraf
- 10 bps slippage / taraf
- giriş: sonraki mum açılışı

## 1D sonuçları

| Varyant | İşlem | PF | E(R) | Kazanma | Pozitif Fold | En Kötü Fold E(R) |
|---|---:|---:|---:|---:|---:|---:|
| H>0, CCI yok | 4,908 | 1.542 | +0.254R | 46.74% | 4/4 | +0.103R |
| İşaret serbest, CCI yok | 5,320 | 1.512 | +0.242R | 46.28% | 4/4 | +0.099R |
| H<0, CCI var | 439 | 1.490 | +0.243R | 43.28% | 4/4 | +0.061R |
| H>0, CCI var | 1,753 | 1.423 | +0.205R | 45.52% | 4/4 | +0.088R |
| İşaret serbest, CCI var | 2,136 | 1.434 | +0.211R | 45.04% | 4/4 | +0.109R |
| H<0, CCI yok | 566 | 1.362 | +0.183R | 42.05% | 4/4 | +0.076R |

### 1D yorumu

Pozitif histogram + CCI yok istatistiksel olarak birinci olsa da, işaret-serbest + CCI-yok sürümüne göre fark küçüktür:
- PF farkı yaklaşık `+0.03`
- expectancy farkı yaklaşık `+0.012R`
- en kötü fold farkı yaklaşık `+0.004R`

Buna karşılık işaret-serbest sürüm daha basit, daha fazla sinyal üretir ve negatif histogramdan toparlanan trend-içi düzeltmeleri de yakalar. Bu nedenle production için işaret filtresini hard-code etmek yerine histogram eğimini ana bilgi olarak kullanmak daha savunulabilir.

## 1W sonuçları

| Varyant | İşlem | PF | E(R) | Kazanma | Pozitif Fold | En Kötü Fold E(R) |
|---|---:|---:|---:|---:|---:|---:|
| H>0, CCI yok | 1,658 | 3.111 | +0.727R | 60.37% | 4/4 | +0.343R |
| İşaret serbest, CCI yok | 1,964 | **3.163** | **+0.743R** | 60.44% | 4/4 | +0.315R |
| H<0, CCI var | 375 | 3.286 | +0.808R | 59.47% | 4/4 | +0.065R |
| H>0, CCI var | 721 | 3.251 | +0.750R | 61.58% | 4/4 | +0.342R |
| H<0, CCI yok | 413 | 3.321 | +0.809R | 59.81% | 4/4 | +0.115R |
| İşaret serbest, CCI var | 1,043 | 3.218 | +0.757R | 60.79% | 4/4 | +0.279R |

### 1W yorumu

Haftalıkta histogram işaretini zorunlu tutmak gereksizdir. İşaret-serbest / CCI-yok sürüm hem çok geniş örnekleme sahiptir hem de dört foldun tamamında pozitiftir. Negatif/pozitif alt grupların bazı ortalama metrikleri daha yüksek görünse de örneklem küçülür ve en kötü fold dayanıklılığı düşebilir.

## Nihai giriş kararı — 1D ve 1W

Production adayı ortak ve sade olsun:

```text
Close > EMA5 > EMA8 > EMA13
AND 30 < RSI14 < 60
AND RVOL20 > 1.50
AND MACD_HIST[t] > MACD_HIST[t-1] > MACD_HIST[t-2]
```

### Bilinçli olarak kaldırılanlar

```text
CCI filtresi: YOK
StochRSI: YOK
MACD crossover zorunluluğu: YOK
Histogram > 0 zorunluluğu: YOK
Histogram < 0 zorunluluğu: YOK
```

Histogram işareti tarama filtresi değil, rapor bağlamı olarak kullanılabilir:
- `H < 0 ve yükseliyor` → erken momentum toparlanması
- `H > 0 ve yükseliyor` → teyitli momentum güçlenmesi

## SAT — sabitlenen yapı

### 1D
- ilk stop: son 7 mum swing low − `0.20 ATR`
- TP1: `+1R`, %30
- TP2: `+2R`, %30
- TP3: `+3R`, %20
- runner: %20
- TP2 sonrası trailing: `2.3 ATR`
- maksimum taşıma: 40 mum
- histogram hard-SAT: yok

### 1W
- ilk stop: son 9 mum swing low − `0.15 ATR`
- TP1: `+1R`, %30
- TP2: `+2R`, %30
- TP3: `+3R`, %20
- runner: %20
- TP2 sonrası trailing: `2.3 ATR`
- maksimum taşıma: 80 mum
- histogram hard-SAT: yok

## Karar

1D ve 1W için CCI kaldırıldı. Histogramın işareti filtre olmaktan çıkarıldı. Ana momentum şartı yalnızca histogramın ardışık iki adım güçlenmesidir.

Bu kural tarihsel robustness açısından güçlüdür; yeni repo promotion aşamasında yeni veri üzerinde forward doğrulama izlenmelidir.
