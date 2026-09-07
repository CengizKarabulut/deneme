# 10 - HO/Volatilite

Araştırma alanıdır; production kodu değildir.

## Orijinal tarama — düzeltilmiş EMA sırası

- Hacim Değişimi(TF) > Hacim Değişimi(1H)
- Ortalama Hacim 10G > Ortalama Hacim 30G
- Volatilite(TF) > Volatilite(1H)
- **EMA21 > EMA55**
- Fiyat > EMA21
- Momentum(14) > 0
- StochRSI(3,3,14,14) K, D'yi yukarı yeni keser
- MACD(12,26) Level > 0

## İlk izole deney — yalnız EMA davranışı

Diğer bütün koşullar sabit tutulur. Yalnız aşağıdaki iki EMA modeli karşılaştırılır:

### A — aligned trend

`Close > EMA21 > EMA55`

Bu model, yükseliş trendi zaten hizalanmışken hacim/volatilite ve momentum tetiklerini arar.

### B — fresh EMA21/55 bullish cross

- `Close > EMA21`
- `EMA21[t] > EMA55[t]`
- `EMA21[t-1] <= EMA55[t-1]`

Bu model, trendin yeni bullish hizalandığı barı arar.

## Sabit koşul semantiği

- `Volume Change = Volume[t] - Volume[t-1]`.
- 1H karşılaştırmaları, hedef bar tamamlandığında mevcut olan son tamamlanmış 1H barına eşlenir; look-ahead kullanılmaz.
- Volatilite karşılaştırması için bar düzeyinde `TrueRange * 100 / abs(Low)` kullanılır; hedef TF ve 1H aynı formülle ölçülür.
- Ortalama Hacim 10G/30G filtresi, look-ahead riskini önlemek için önceki tamamlanmış günlük barların SMA10/SMA30 değerleriyle uygulanır.
- Momentum(14) = `Close[t] - Close[t-14]`.
- StochRSI: RSI14 üzerinde 14 bar stochastic, K=3 SMA, D=3 SMA; yalnız fresh K>D kesişimi olaydır.
- MACD Level = EMA12 - EMA26 ve `>0` olmalıdır.

Not: 1H hedef timeframe'inde `VolumeChange(1H) > VolumeChange(1H)` ve `Volatility(1H) > Volatility(1H)` matematiksel olarak mümkün değildir; bu nedenle orijinal MTF koşullarını aynen koruyan ilk turda 1H'in sıfır sinyal üretmesi beklenir.

## Backtest semantiği

- 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W, 1M
- yalnız tamamlanmış bar
- giriş referansı t+1 open
- aynı structural exit A ve B için aynen kullanılır
- 10 bps komisyon + 10 bps slippage her yön
- aynı OHLC barında stop ve hedef görülürse STOP önce
- ilk risk 0.60–2.60 ATR ile sınırlandırılır
- yeterli örneklemde girişe özel 4 kronolojik fold

Amaç: Bu turda yalnız **A mı B mi?** sorusunu cevaplamak. Hacim/volatilite MTF koşullarının kendisi ancak EMA kazananı dondurulduktan sonra ayrı robustness aşamasında sorgulanacaktır.
