# Borsapp Scanner Audit

Bu klasor borsapp taramalarini ayri bir alanda incelemek ve backtest etmek icin kullanilir.

Kurallar:
- Mevcut deneme dosyalari degistirilmez.
- Borsapp production kodu degistirilmez.
- Yeni audit calismalari yalnizca bu klasor altinda tutulur.
- Her tarama once mevcut haliyle olculur, sonra parametre ve timeframe testleri yapilir.

Varsayilan zaman dilimleri: 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W, 1M.

Ilk calisma: technical.volume_spike.
