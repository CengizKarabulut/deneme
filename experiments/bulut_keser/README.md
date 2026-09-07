# 9 - BulutKeser

Araştırma alanı. Production kodu değildir.

## Orijinal fikir

- ADX(14): 20–40
- Fiyat BB(20,2) Lower ile Upper arasında
- RVOL20 > 1.20
- Ichimoku(9,26,52,26): Tenkan / Conversion Line, Kijun / Base Line'ı yukarı yeni keser

## İlk ana deney — Kumo konumu

Orijinal koşullar aynen korunur. Yalnız Tenkan-Kijun bullish cross barındaki fiyatın mevcut grafikte görünen Kumo'ya göre konumu ayrılır:

- `all`: Kumo filtresi yok; orijinal kontrol grubu
- `above`: Close > Kumo top
- `inside`: Kumo bottom <= Close <= Kumo top
- `below`: Close < Kumo bottom

Ichimoku Kumo, gerçek grafik semantiğiyle hesaplanır. Senkou A/B ham değerleri 26 bar ileri çizildiği için, mevcut bardaki görünen Kumo değerleri `raw_span.shift(26)` ile elde edilir. Böylece yalnız geçmiş bilgi kullanılır; look-ahead yoktur.

## Sabit ortak koşullar

- `20 <= ADX14 <= 40`
- `BB Lower < Close < BB Upper`
- `RVOL20 > 1.20`
- fresh bullish Tenkan/Kijun cross

RVOL20 = `Volume[t] / mean(Volume[t-1]..Volume[t-20])`; mevcut bar ortalamaya dahil değildir ve her timeframe kendi barlarını kullanır.

## Metodoloji

- 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W, 1M
- yalnız tamamlanmış bar
- giriş referansı t+1 open
- 10 bps komisyon + 10 bps slippage her yön
- aynı OHLC barda stop ve hedef birlikte görünürse STOP öncelikli
- dört Kumo konum varyantı aynı yapısal SAT altında test edilir
- her varyant kendi sinyal zamanlarından dört kronolojik pencereye bölünür
- güçlü timeframe ve Kumo sınıfı belli olduktan sonra BB/ADX/RVOL ve SAT robustness ikinci aşamada ele alınır
