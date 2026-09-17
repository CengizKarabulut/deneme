# Audit assumptions and parity notes

Bu batch, production davranisini audit spesifikasyonundan yeniden kurar.

- `technical.failed_breakout`, `decision_zone`, `trend_continuation`, `exhaustion` production kurallarina en yakin yeniden kurulumdur.
- Signal scanner'lari dokumante edilen RSI/MACD/SMI/MA/volume kosullariyla yeniden kurulur.
- `ma.near_zone` ve `decision.panel_v645` icin batch sonucu **research proxy** olarak etiketlenir; nihai karardan once production engine ile parity dogrulamasi zorunludur.
- Tüm barlar tarihsel SQLite'dan gelir; ileri barlar yalnız outcome olcumunde kullanilir.
- Holdout, scanner/timeframe event zaman siralamasinin son %20'sidir.
- Directional scanner'larda yon-duzeltilmis ileri getiri ve MFE/MAE raporlanir.
