# NE ARARSAN VAR — Araştırma Kaydı

Bu klasör, “Ne Ararsan Var” taramasının production’a alınmadan önce yapılan bütün araştırmalarını toplar.

## Ortak trend iskeleti

Son tartışılan ana yapı:

- `Close > EMA5 > EMA8 > EMA13`
- `30 < RSI14 < 60`
- `RVOL20 > 1.50`
- Stoch RSI kaldırıldı
- CCI sabit kabul edilmedi; timeframe’e göre `var/yok` test ediliyor
- MACD crossover ve histogram eğimi ayrı giriş aileleri olarak karşılaştırılıyor

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

## Şu anki araştırma kararı

- **1D:** histogram eğimi ana aday; CCI faydalı görünüyor.
- **1W:** histogram eğimi çok güçlü aday; histogramın pozitif/negatif işaretini sabitlemeden robustness testi yapılmalı.
- **4H:** crossover ana aday; negatif bölgede yükselen histogram ek teyit/puan olabilir.
- **2H:** crossover araştırma modeli korunmalı.
- **15m–1H:** bu taramanın mevcut mantığıyla production’a alınmamalı.
- **1M:** yalnız research/watchlist.

## Metodoloji notu

Önceki final holdout bir kez görüldükten sonra sonraki denemelerde aynı bölüm yeniden “dokunulmamış OOS” diye adlandırılmadı. Yeni çalışmalar expanding walk-forward ile yürütülüyor. Nihai adayların gerçek son doğrulaması gelecekteki yeni veride forward olarak yapılmalıdır.
