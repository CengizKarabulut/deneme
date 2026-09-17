# Remaining scanner parallel audit

Bu klasor, `borsapp` production koduna dokunmadan kalan scanner'larin toplu audit calismasi icindir.

## Kapsam

15 pending scanner x 8 timeframe = 120 baseline hucre.

Timeframe matrisi: `15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W`.

Her job tum mevcut BIST SQLite evrenini kullanir; watchlist secimi yapmaz.

## Standart ciktilar

Her scanner/timeframe icin:

- DB'deki sembol sayisi
- yeterli gecmise sahip sembol sayisi
- event sayisi
- fresh event orani
- +1/+3/+5/+10/+20 ileri getiri
- medyan mutlak getiri
- MFE / MAE
- ATR normalize range
- production parametreleri ile baseline
- scanner tipine uygun yon / state metrikleri
- kronolojik research / holdout ozeti

Production repo degistirilmez. Sonuclar yalniz `research/borsapp-scanner-audit` branch'inde tutulur.
