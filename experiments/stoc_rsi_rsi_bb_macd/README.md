# 11 - Stoc.RSI & RSI & BB & MACD

Bu klasor 11 numarali taramanin A/B izole giris deneyidir. Production kodu degildir.

## A - Orijinal

- RSI(14) > 30
- StochRSI(3,3,14,14) K, D'yi ayni barda fresh bullish keser
- Close, BB(20) Basis'i ayni barda fresh yukari keser
- MACD(12,26,9) Level, Signal'i ayni barda fresh bullish keser
- RVOL20 > 1.50

## B - BB reclaim ana tetikleyici

- RSI(14) > 30
- Close, BB(20) Basis'i fresh yukari keser
- StochRSI K > D
- MACD Level > Signal
- RVOL20 > 1.50

## Ortak metodoloji

- 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W, 1M
- yalniz tamamlanmis bar
- giris referansi t+1 open
- RVOL20 = Volume[t] / mean(Volume[t-1]..Volume[t-20]); mevcut bar ortalamaya dahil degil
- her varyant kendi sinyal zamanlarindan dort kronolojik pencereye ayrilir
- A ve B ayni yapisal SAT kontrol profiliyle test edilir
- 10 bps komisyon + 10 bps slippage her yon
- ayni OHLC barinda stop ve hedef birlikte gorunurse STOP once
- gecmis veri gozlenmis veridir; gercek bagimsiz dogrulama gelecekteki yeni barlardir
