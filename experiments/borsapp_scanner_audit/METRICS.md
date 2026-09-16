# Ortak Audit Metrikleri

Her scanner ayni temel rapor iskeletiyle degerlendirilir.

## Tum scannerlar
- event/sinyal sayisi
- kapsanan sembol sayisi
- tekrar eden sinyal orani
- +1, +3, +5, +10, +20 bar ileri getiri
- MFE
- MAE
- ATR normalize hareket
- donem bazli dagilim
- timeframe bazli dagilim
- likidite segmenti bazli dagilim
- in-sample / out-of-sample karsilastirmasi

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

## Parametre testi ilkesi
Tek bir en iyi deger secilmez. Parametrenin komsu degerlerde de istikrarli olup olmadigi kontrol edilir.

## Timeframe matrisi
15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W, 1M.
