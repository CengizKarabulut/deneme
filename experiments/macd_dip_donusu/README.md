# 14 - MACD DipDönüşü

Durum: **LOCKED**

Nihai makine-okunur tanım: `locked-spec.json`  
Nihai araştırma raporu: `reports/final-decision.md`

## Giriş adayları

### A — Saf Dip Dönüşü
- MACD(12,26,9) Level < 0
- MACD Level fresh bullish crosses Signal
- RVOL filtresi yok

### B — Orijinal
- MACD Level < 0
- MACD Level fresh bullish crosses Signal
- RVOL20 > 1.20

### C — Güçlü Hacim
- MACD Level < 0
- MACD Level fresh bullish crosses Signal
- RVOL20 > 1.50

RVOL20 = Volume[t] / mean(Volume[t-1] ... Volume[t-20]); mevcut bar kendi ortalamasına dahil edilmez.

## Nihai timeframe seçimi

| TF | Durum | Giriş |
|---|---|---|
| 15m | REJECT | — |
| 30m | REJECT | — |
| 45m | REJECT | — |
| 1H | REJECT | — |
| 2H | REJECT | — |
| 4H | ACTIVE_SECONDARY | C / RVOL>1.50 |
| 1D | ACTIVE_SECONDARY | A / RVOL yok |
| 1W | ACTIVE | A / RVOL yok |
| 1M | RESEARCH_FORWARD_WATCH | A |

4H ve 1D'de MACD tekrar Signal altına düşerken MACD hâlâ negatifse sticky **0.8 ATR** tight trailing kullanılır. 1W'de aynı başarısız dönüş koşulu **1.2 ATR** tight trailing kullanır. TP1 sonrası break-even hiçbir production timeframe'de kullanılmaz.

## Ortak metodoloji
- yalnız tamamlanmış bar
- giriş referansı t+1 open
- aynı sembolde açık pozisyon varken yeni sinyal yeni işlem başlatmaz
- 4 kronolojik fold
- 10 bps komisyon + 10 bps slippage her yön
- aynı OHLC barında stop ve hedef birlikte görünürse STOP önce
- ilk risk 0.60–2.60 ATR arasında sınırlandırılır
- geçmiş veri gözlenmiş veridir; gerçek bağımsız doğrulama gelecekteki yeni barlardır
