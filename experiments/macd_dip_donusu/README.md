# 14 - MACD DipDönüşü

Durum: **RESEARCH**

## Giriş deneyi

Amaç: negatif MACD bölgesindeki fresh bullish MACD/Signal kesişiminde RVOL filtresinin gerçekten katkı sağlayıp sağlamadığını izole etmek.

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

RVOL20 = Volume[t] / mean(Volume[t-1] ... Volume[t-20]); mevcut bar kendi ortalamasına dahil edilmez.

## Ortak metodoloji
- 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W, 1M
- yalnız tamamlanmış bar
- giriş referansı t+1 open
- A/B/C aynı yapısal SAT kontrol profiliyle karşılaştırılır
- her varyant kendi sinyal zamanlarından 4 kronolojik pencereye ayrılır
- aynı sembolde açık pozisyon varken yeni sinyal yeni işlem başlatmaz
- 10 bps komisyon + 10 bps slippage her yön
- aynı OHLC barında stop ve hedef birlikte görünürse STOP önce
- geçmiş veri gözlenmiş veridir; gerçek bağımsız doğrulama gelecekteki yeni barlardır
