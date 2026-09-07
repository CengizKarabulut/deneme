# 8 - TavanTarama

Araştırma alanı. Production kodu değildir.

## Orijinal fikir

- DMI(14) +DI > -DI
- +DI, ADX(14)'i yukarı keser
- RSI(14) 30-70
- StochRSI(3,3,14,14) K, D'yi yukarı keser
- RVOL20 > 1.20

## Ana karşılaştırma

A - Orijinal DMI tetik:
`+DI > -DI AND +DI[t] > ADX[t] AND +DI[t-1] <= ADX[t-1]`

B - Alternatif yön tetik:
`+DI[t] > -DI[t] AND +DI[t-1] <= -DI[t-1] AND ADX[t] > ADX[t-1]`

İki tetik aynı çıkış iskeleti altında doğrudan karşılaştırılır.

## Kontrollü filtre varyantları

- RSI: 30-70, 40-70, 50-70
- StochRSI: fresh K>D crossover veya yalnız K>D teyidi
- RVOL20: >1.20 veya >1.50

RVOL20 = `Volume[t] / mean(Volume[t-1]..Volume[t-20])`; mevcut bar ortalamaya dahil değildir ve her timeframe kendi barlarını kullanır.

## Metodoloji

- 15m, 30m, 45m, 1H, 2H, 4H, 1D, 1W, 1M
- yalnız tamamlanmış bar
- giriş referansı t+1 open
- 10 bps komisyon + 10 bps slippage her yön
- aynı OHLC barda stop ve hedef birlikte görünürse STOP öncelikli
- her giriş varyantı kendi sinyal zamanlarından dört kronolojik pencereye bölünür
- ilk aşamada bütün girişler aynı yapısal SAT ile test edilir
- güçlü timeframe'lerde giriş dondurulduktan sonra DMI/ADX SAT aileleri ve TP1 BE/no-BE test edilir
