# Ortak Audit Metrikleri

Her scanner ayni temel rapor iskeletiyle degerlendirilir.

## Zorunlu timeframe matrisi
Her scanner, production tarafinda o timeframe acik olsun veya olmasin, arastirma amaciyla su 8 zaman diliminde ayri ayri olculur:

- 15m
- 30m
- 45m
- 1H
- 2H
- 4H
- 1D
- 1W

Ilk geciste scanner kurali ve parametreleri timeframe'e gore degistirilmez. Bu baseline/parity kosusudur. Sonraki asamada timeframe'e ozel sorunlar ve aday duzeltmeler ayri deney olarak olculur.

## Tum scannerlar
- event/sinyal sayisi
- kapsanan sembol sayisi
- veri kapsama suresi ve yeterli warmup orani
- tekrar eden sinyal orani / fresh event orani
- +1, +3, +5, +10, +20 bar ileri getiri
- MFE
- MAE
- ATR normalize hareket
- piyasa donemi/rejim bazli dagilim
- timeframe bazli dagilim
- likidite segmenti bazli dagilim
- in-sample / out-of-sample karsilastirmasi
- parametre komsuluk istikrari

## Yonsuz event scannerlari
Ornek: technical.volume_spike
- mutlak ileri hareket
- sonraki bar range genislemesi
- yukari ve asagi excursion ayri olculur
- hacim devamligi
- yeni high / yeni low olusumu
- hareketsiz event orani

## Yonlu scannerlar
- ileri getiri
- pozitif/negatif sonuc orani
- MFE / MAE
- expectancy
- profit factor (islem simulasyonu tanimlandiginda)
- maksimum drawdown (islem simulasyonu tanimlandiginda)

## Timeframe eksik analizi
Her timeframe icin ayrica su sorular cevaplanir:
- Veri ve warmup yeterli mi?
- Sinyal sayisi cok az veya asiri fazla mi?
- Ayni setup ardisik barlarda tekrar ediyor mu?
- Likidite esigi timeframe ile anlamsizlasiyor mu?
- Intraday saat etkisi var mi?
- Indikator/esik ayni anlamini koruyor mu?
- Forward edge komsu ufuklarda tutarli mi?
- MFE/MAE dengesi bozuluyor mu?
- Sonuc belirli bir piyasa donemine bagimli mi?

## Parametre testi ilkesi
Tek bir en iyi deger secilmez. Parametrenin komsu degerlerde ve farkli piyasa donemlerinde istikrarli olup olmadigi kontrol edilir. Holdout sonucu gorulmeden production degisikligi onerilmez.
