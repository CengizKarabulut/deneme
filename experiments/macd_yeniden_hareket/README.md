# 13 - MACD YenidenHareket

Durum: **LOCKED**

Nihai makine-okunur tanım: `locked-spec.json`  
Nihai araştırma raporu: `reports/final-decision.md`

## Giriş adayları

### A — Orijinal
- MACD(12,26,9) Level > 0
- MACD Level, Signal'ı fresh bullish keser

### B — Güçlü pozitif bölge
- MACD Level > 0
- MACD Signal > 0
- MACD Level, Signal'ı fresh bullish keser
- finalde kullanılmıyor; A'ya karşı anlamlı ve kalıcı ek avantaj üretmedi

### C — Yeniden ivmelenme
- MACD Level > 0
- MACD Level > Signal
- Histogram[t] > Histogram[t-1] > Histogram[t-2]
- koşulun yalnız yeni başlayan epizodu sinyal sayılır

## Nihai timeframe seçimi

| TF | Durum | Giriş |
|---|---|---|
| 15m | REJECT | — |
| 30m | REJECT | — |
| 45m | REJECT | — |
| 1H | REJECT | — |
| 2H | REJECT | — |
| 4H | ACTIVE_SECONDARY | C |
| 1D | ACTIVE | C |
| 1W | ACTIVE | A |
| 1M | RESEARCH_FORWARD_WATCH | A |

4H ve 1D'de MACD Level < Signal olduğunda sticky **0.5 ATR tight trailing** kullanılır. 1W ve 1M yapısal yönetimde kalır. 4H/1D/1W/1M için final TP1 break-even kararı **NO-BE**'dir.

## Ortak metodoloji
- yalnız tamamlanmış bar
- giriş referansı t+1 open
- aynı sembolde açık pozisyon varken yeni sinyal yeni işlem başlatmaz
- 4 kronolojik fold
- 10 bps komisyon + 10 bps slippage her yön
- aynı OHLC barında stop ve hedef birlikte görünürse STOP önce
- ilk risk 0.60–2.60 ATR arasında sınırlandırılır
- geçmiş veri gözlenmiş veridir; gerçek bağımsız doğrulama gelecekteki yeni barlardır
