# 13 - MACD YenidenHareket

Durum: RESEARCH

## Giriş adayları

### A — Orijinal
- MACD(12,26,9) Level > 0
- MACD Level, Signal'ı fresh bullish keser

### B — Güçlü pozitif bölge
- MACD Level > 0
- MACD Signal > 0
- MACD Level, Signal'ı fresh bullish keser

### C — Yeniden ivmelenme
- MACD Level > 0
- MACD Level > Signal
- Histogram[t] > Histogram[t-1] > Histogram[t-2]
- Koşulun yalnız yeni başlayan epizodu sinyal sayılır

## Ortak metodoloji
- 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W, 1M
- yalnız tamamlanmış bar
- giriş referansı t+1 open
- A/B/C aynı yapısal SAT kontrol profiliyle karşılaştırılır
- her varyant kendi sinyal zamanlarından 4 kronolojik pencereye ayrılır
- 10 bps komisyon + 10 bps slippage her yön
- aynı OHLC barında stop ve hedef birlikte görünürse STOP önce
- geçmiş veri gözlenmiş veridir; gerçek bağımsız doğrulama gelecekteki yeni barlardır
