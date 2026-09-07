# BB & SMA — Araştırma Laboratuvarı

Üçüncü tarama: Bollinger Basis / SMA trend devamı.

## Orijinal TradingView mantığı

- Fiyat, BB(20) Basis'i yukarı keser.
- Fiyat > SMA20.
- SMA20 > SMA50 > SMA200.

BB(20) Basis varsayılan olarak SMA20 olduğundan `Fiyat > SMA20` ayrı bir bilgi değildir. Araştırmada çekirdek tetik `Close crosses above SMA20` olarak kullanılır.

## Giriş adayları

- A — Saf reclaim: `Close ↑ SMA20 AND SMA20>SMA50>SMA200`
- B — Eğim teyitli: A + `SMA20>SMA20[1]`
- C — Hacim teyitli: A + `Volume[t] > mean(previous 10 same-TF bars)`
- D — Eğim + hacim: B + hacim

Hacim filtresi her timeframe'in kendi barlarıyla hesaplanır ve mevcut bar referans ortalamasına dahil edilmez.

## İlk SAT adayları

- Yapısal kontrol: swing/ATR stop + 1R/2R/3R + runner + TP2 sonrası ATR trailing
- Close < SMA20
- 2 ardışık Close < SMA20
- Close < SMA50
- SMA20, SMA50'yi aşağı keser
- Adaptif: SMA20 kaybında trailing sıkılaştır; SMA50 kaybında hard exit

## Araştırma kuralları

- 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W, 1M bağımsız test edilir.
- Sinyal yalnız tamamlanmış mumda oluşur.
- Giriş referansı bir sonraki mum açılışıdır.
- Look-ahead yoktur.
- Aynı OHLC barda stop ve hedef birlikte görülürse stop önceliklidir.
- İlk tur 4 expanding walk-forward fold kullanır.
- Maliyet varsayımı: alış ve satışta ayrı ayrı 10 bps komisyon + 10 bps slippage.

Bu klasör yalnız araştırma içindir; doğrulanmadan production reposuna taşınmaz.
