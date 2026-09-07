# 10 - HO/Volatilite — EMA A/B İzole Deney Sonucu

Run: `34165330490`

Bu aşamada yalnız EMA davranışı değiştirildi. Diğer orijinal koşullar sabit tutuldu:

- Volume Change(TF) > Volume Change(1H)
- prior completed daily AvgVol10 > AvgVol30
- Volatility(TF) > Volatility(1H)
- Momentum14 > 0
- StochRSI(3,3,14,14) fresh K>D cross
- MACD Level > 0

A = `Close > EMA21 > EMA55`

B = `Close > EMA21` ve EMA21'in EMA55'i aynı sinyal barında fresh bullish kesmesi.

| TF | A trades | A PF | A E(R) | A folds | B trades | B PF | B E(R) | B folds | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 15m | 84 | 0.236 | -0.925 | 0/4 | 10 | 0.313 | -0.865 | yetersiz | İkisi de başarısız |
| 30m | 66 | 0.254 | -0.779 | 0/4 | 4 | 0.000 | -1.209 | yetersiz | İkisi de başarısız |
| 45m | 1511 | 0.595 | -0.322 | 0/4 | 41 | 0.340 | -0.596 | 0/4 | İkisi de başarısız |
| 1H | 0 | — | — | — | 0 | — | — | — | Orijinal strict 1H>1H MTF koşulu matematiksel olarak sinyal üretmez |
| 2H | 1930 | 0.851 | -0.097 | 1/4 | 43 | 0.735 | -0.202 | 1/4 | İkisi de başarısız |
| 4H | 1398 | 0.854 | -0.087 | 2/4 | 52 | 1.055 | +0.026 | 2/4 | B hafif pozitif ama kararsız; production değil |
| 1D | 483 | 0.524 | -0.327 | 0/4 | 55 | 0.982 | -0.010 | yetersiz | B nötre yakın ama yetersiz; A başarısız |
| 1W | 52 | 0.580 | -0.203 | 2/4 | 5 | 1.507 | +0.207 | yetersiz | B örneklem çok küçük |
| 1M | 63 | 0.931 | -0.026 | yetersiz | 0 | — | — | — | Yetersiz / edge yok |

## Ana bulgu

Bu sabit koşullar altında **A veya B'den hiçbiri production kazananı değildir**.

A modeli geniş örneklem üretmesine rağmen hemen tüm timeframe'lerde negatif expectancy verir. B modeli trendin yeni hizalandığı barı çok seçici biçimde aradığı için sinyal sayısını dramatik azaltır; 4H'de yalnız hafif pozitif fakat 2/4, haftalıkta ise sadece 5 işlem vardır.

4H B fold expectancy değerleri yaklaşık `+0.333R, +0.372R, -0.242R, -0.496R` şeklindedir. Bu nedenle stitched PF>1 sonucu rejim kararlılığı anlamına gelmez.

## Araştırma kararı

EMA seçimini burada zorla yapmıyoruz. İlk tur, asıl problemin yalnız EMA sırası olmadığını gösteriyor. Sonraki mantıklı izolasyon, EMA A'yı geniş kontrol grubu olarak koruyup **cross-timeframe Volume Change / Volatility koşullarının gerçekten katkı sağlayıp sağlamadığını** ayrı ayrı ölçmektir. B'nin 'aynı barda EMA cross + StochRSI cross' yapısı da aşırı seyrek olduğu için ancak `EMA cross son 3/5 bar içinde` gibi ayrı bir research varyantı olarak ele alınmalıdır; bu mevcut A/B sonucunun yerine geçmez.

Bu tarihsel veri artık gözlenmiştir; gerçek bağımsız doğrulama gelecekte oluşacak yeni barlardır.
