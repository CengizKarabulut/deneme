# Batch status

Kalan 15 scanner icin 8-timeframe paralel audit matrisi TEK BATCH olarak tetiklendi.

Toplam temel hucre: 15 scanner x 8 timeframe = 120 job.

Timeframe matrisi: 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W.

Calisma politikasi:
- Tum 15 scanner ayni workflow matrix icinde birlikte calisir.
- fail-fast kapali; bir hucrenin hatasi digerlerini durdurmaz.
- max-parallel: 24.
- Production `CengizKarabulut/borsapp` koduna dokunulmaz.
- Tum audit calismasi yalniz `research/borsapp-scanner-audit` branch'inde tutulur.
- Sonuclar production-parity kontrolunden gecmeden nihai karar olarak isaretlenmez.

Trigger: 2026-09-17 Europe/Istanbul.
