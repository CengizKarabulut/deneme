# technical.volume_spike Audit

## Production baseline
- Closed bars only
- Relative volume threshold: 3.0
- Relative volume baseline: previous 20 closed bars
- Minimum price: 1.0 TL
- Minimum average turnover: 20,000,000 TL
- Direction: neutral event

## First-pass audit questions
1. RVOL 3.0 esigi hangi timeframe'lerde anlamli?
2. RVOL 1.5, 2.0, 2.5, 3.0, 4.0 ve 5.0 esikleri nasil davraniyor?
3. Sinyalden sonra +1, +3, +5, +10 ve +20 barda mutlak hareket artiyor mu?
4. MFE ve MAE dagilimi nasil?
5. Sonraki barlarda range/ATR genislemesi oluyor mu?
6. Hacim devam ediyor mu yoksa tek barlik mi?
7. Mevcut 20M turnover filtresi timeframe bazinda evreni bozuyor mu?
8. Turnover hesabindan event bari cikarilinca sonuc nasil degisiyor?
9. Intraday zaman dilimlerinde seans-saati etkisi var mi?
10. Sonuclar kronolojik holdout doneminde korunuyor mu?

## Test matrix
- Timeframes: 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W, 1M
- RVOL thresholds: 1.5, 2.0, 2.5, 3.0, 4.0, 5.0
- Forward horizons: 1, 3, 5, 10, 20 bars

## Interpretation
Bu scanner yonsuz bir aktivite/event scanneridir. Basari klasik long win-rate ile tek basina olculmeyecek. Ana odak mutlak ileri hareket, volatilite genislemesi, MFE/MAE, hacim devamligi ve yukari/asagi kirilim dagilimidir.
