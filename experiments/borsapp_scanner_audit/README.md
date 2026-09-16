# Borsapp Scanner Audit

Bu klasor borsapp taramalarini ayri bir alanda incelemek ve backtest etmek icin kullanilir.

Kurallar:
- Mevcut deneme dosyalari degistirilmez.
- Borsapp production kodu degistirilmez.
- Yeni audit calismalari yalnizca bu klasor altinda tutulur.
- Her tarama once mevcut haliyle olculur; production kurali baseline kosusunda degistirilmez.
- Her scanner zorunlu olarak 15m, 30m, 45m, 1H, 2H, 4H, 1D ve 1W zaman dilimlerinde ayri ayri test edilir.
- Production'da desteklenmeyen timeframe'ler de arastirma amaciyla test edilir ve sonuc 'research-only' olarak etiketlenir.
- Baseline sonucundan sonra timeframe'e ozel eksikler, parametre hassasiyeti ve aday duzeltmeler ayri deneylerde olculur.
- Holdout verisi production kural secmek icin erken kullanilmaz.

Standart zaman dilimleri: 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W.

Ilk calisma: technical.volume_spike.
