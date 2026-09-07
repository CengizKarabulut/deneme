# NE ARARSAN VAR — Araştırma Kaydı

Bu klasör, “Ne Ararsan Var” taramasının production’a alınmadan önce yapılan bütün araştırmalarını toplar.

## Ortak trend iskeleti

Güncel ana yapı:

- `Close > EMA5 > EMA8 > EMA13`
- `30 < RSI14 < 60`
- `RVOL20 > 1.50`
- Stoch RSI kaldırıldı
- CCI, son sabit-kural robustness testinden sonra 1D/1W histogram sürümlerinden kaldırıldı
- MACD crossover ve histogram eğimi timeframe bazında ayrı adaylar olarak tutuluyor

## Deneyler

### 1) İlk crossover baseline + SAT optimizasyonu

İlk sürümde MACD bullish crossover kullanıldı ve SAT; yapısal stop, 1R/2R/3R kademeli kâr alma, runner, ATR trailing ve teknik SAT kombinasyonlarıyla optimize edildi.

Öne çıkan ilk OOS adayları:

- 4H: PF yaklaşık `1.29`, pozitif expectancy
- 1D: PF yaklaşık `1.37`, pozitif expectancy
- 1W: PF yaklaşık `2.22`, güçlü sonuç
- 2H: sınırda / araştırma
- 15m–1H: zayıf
- 1M: örneklem yetersiz

### 2) Timeframe’e özel SAT walk-forward

15m, 30m, 45m, 1H ve 2H için ayrı SAT aileleri denendi. Sonuçlar `reports/tf-exit-summary.md` içindedir.

Ana ders:

- Her timeframe’in SAT mantığı farklı olabilir.
- 15m–1H yalnız SAT değiştirerek kurtarılamadı.
- 2H araştırmaya değer kaldı.

### 3) MACD histogram AL + SAT walk-forward

MACD crossover yerine histogram eğimi test edildi:

- `H[t] > H[t-1] > H[t-2]`
- aynı koşul histogram negatifken
- aynı koşul histogram pozitifken
- her biri CCI açık / kapalı

Histogram SAT tarafında da sert çıkış ve adaptif trailing varyantlarıyla test edildi.

Sonuçlar `reports/histogram-summary.md` içindedir.

Ana sonuç:

- 1D: güçlü walk-forward, PF `1.368`, expectancy `+0.181R`, 4/4 pozitif dönem
- 1W: çok güçlü, PF `2.982`, expectancy `+0.719R`, 4/4 pozitif dönem
- 4H: pozitif ama rejim kararsız
- 2H: histogram, eski crossover araştırmasından daha zayıf
- 15m–1H: reddedildi
- 1M: umut verici ama örneklem yetersiz

Histogramın en güçlü rolü giriş/momentum tespiti oldu. Sert histogram SAT kuralları çoğu güçlü koşuda seçilmedi; yapısal stop + 1R/2R/3R + runner + ATR trailing daha dayanıklı kaldı.

### 4) 1D/1W sabit-kural histogram robustness

Altı giriş varyantı fold bazında yeniden seçilmeden dört kronolojik pencerede sabit tutuldu. Ayrıntılar `reports/histogram-robustness-summary.md` içindedir.

Önemli sonuçlar:

#### 1D

- `H>0 + CCI yok`: PF `1.542`, expectancy `+0.254R`, 4/4 pozitif
- `işaret serbest + CCI yok`: PF `1.512`, expectancy `+0.242R`, 4/4 pozitif

Pozitif histogram filtresinin avantajı küçük kaldığı için daha sade ve rejime dayanıklı işaret-serbest sürüm production adayı seçildi.

#### 1W

- `işaret serbest + CCI yok`: PF `3.163`, expectancy `+0.743R`, 4/4 pozitif
- `H>0 + CCI yok`: PF `3.111`, expectancy `+0.727R`, 4/4 pozitif

Haftalıkta işaret filtresi açıkça gerekli değildir.

## Güncel araştırma kararı

### 1D — ana histogram adayı

```text
Close > EMA5 > EMA8 > EMA13
AND 30 < RSI14 < 60
AND RVOL20 > 1.50
AND MACD_HIST[t] > MACD_HIST[t-1] > MACD_HIST[t-2]
```

- CCI: yok
- StochRSI: yok
- MACD crossover zorunluluğu: yok
- histogram işareti zorunluluğu: yok

SAT:
- son 7 mum swing low − `0.20 ATR`
- TP1 `1R` / %30
- TP2 `2R` / %30
- TP3 `3R` / %20
- runner %20
- TP2 sonrası `2.3 ATR` trailing
- maksimum 40 mum
- histogram hard-SAT yok

### 1W — ana histogram adayı

Giriş 1D ile aynı:

```text
Close > EMA5 > EMA8 > EMA13
AND 30 < RSI14 < 60
AND RVOL20 > 1.50
AND MACD_HIST[t] > MACD_HIST[t-1] > MACD_HIST[t-2]
```

SAT:
- son 9 mum swing low − `0.15 ATR`
- TP1 `1R` / %30
- TP2 `2R` / %30
- TP3 `3R` / %20
- runner %20
- TP2 sonrası `2.3 ATR` trailing
- maksimum 80 mum
- histogram hard-SAT yok

### Diğer timeframe’ler

- **4H:** crossover ana aday; negatif bölgede yükselen histogram ek teyit/puan olabilir.
- **2H:** crossover araştırma modeli korunmalı.
- **15m–1H:** mevcut tarama mantığıyla production’a alınmamalı.
- **1M:** yalnız research/watchlist; örneklem henüz yeterli değil.

## Metodoloji notu

Önceki final holdout bir kez görüldükten sonra sonraki denemelerde aynı bölüm yeniden “dokunulmamış OOS” diye adlandırılmadı. Yeni çalışmalar expanding walk-forward ve sabit-kural robustness ile yürütülüyor. Nihai adayların gerçek son doğrulaması gelecekteki yeni veride forward olarak yapılmalıdır.
