# 11 - Stoc.RSI & RSI & BB & MACD — Nihai Karar

Tarih: 2026-09-08

## Giris A/B karsilastirmasi

### A — Orijinal

- RSI14 > 30
- StochRSI(3,3,14,14) K, D'yi fresh bullish keser
- Close, BB(20) Basis'i fresh yukari keser
- MACD(12,26,9) Level, Signal'i fresh bullish keser
- RVOL20 > 1.50

### B — Kazanan production adayi

- RSI14 > 30
- Close, BB(20) Basis'i fresh yukari keser
- StochRSI K > D
- MACD Level > Signal
- RVOL20 > 1.50

A ve B ayni yapisal SAT kontrol profili, ayni maliyet modeli ve her varyantin kendi sinyal zamanlarindan olusan dort kronolojik pencereyle test edildi.

| TF | A trades | A PF | A E(R) | A fold | B trades | B PF | B E(R) | B fold | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 15m | 3456 | 0.235 | -0.927 | 0/4 | 14994 | 0.246 | -0.905 | 0/4 | REJECT |
| 30m | 3343 | 0.381 | -0.602 | 0/4 | 15543 | 0.403 | -0.572 | 0/4 | REJECT |
| 45m | 3730 | 0.499 | -0.429 | 0/4 | 16591 | 0.541 | -0.382 | 0/4 | REJECT |
| 1H | 1588 | 0.528 | -0.391 | 0/4 | 7612 | 0.559 | -0.359 | 0/4 | REJECT |
| 2H | 2466 | 0.853 | -0.100 | 1/4 | 12367 | 0.913 | -0.057 | 1/4 | REJECT |
| 4H | 1267 | 1.309 | +0.153 | 2/4 | 6043 | 1.250 | +0.125 | 3/4 | B SAT research |
| 1D | 629 | 1.150 | +0.080 | 3/4 | 3971 | 1.328 | +0.165 | 4/4 | B wins |
| 1W | 209 | 2.507 | +0.590 | 4/4 | 1241 | 2.989 | +0.714 | 4/4 | B wins |
| 1M | yetersiz | — | — | — | 37 | 2.987 | +0.638 | 2/4 | RESEARCH / insufficient |

Ana sonuc: A'daki uc fresh crossover'in ayni barda zorunlu olmasi 1D/1W'de gerekli olmayan bir zamanlama kisiti yaratmistir. B, BB Basis reclaim'i ana tetikleyici yapip StochRSI ve MACD'yi mevcut momentum teyidi olarak kullandiginda daha genis orneklem ve daha iyi robust edge uretmistir.

## 4H — ACTIVE_SECONDARY

Nihai giris B:

- RSI14 > 30
- Close[t] > BB Basis[t] ve Close[t-1] <= BB Basis[t-1]
- StochRSI K > D
- MACD Level > Signal
- RVOL20 > 1.50

Ham B girisi: 6043 islem, PF 1.250, +0.125R, 3/4 pozitif; worst-fold -0.202R.

BB Basis kaybini hard-SAT yapmak yerine trailing'i sikilastirmak cok daha iyi calisti. Final SAT:

- ilk stop: son 9 adet 4H swing low - 0.25 ATR
- ilk risk 0.60–2.60 ATR arasinda sinirlanir
- TP1 = 1.1R, %30
- TP2 = 2.2R, %30
- TP3 = 3.3R, %20
- runner = %20
- TP2 sonrasi normal trailing = 1.8 ATR
- Close < BB Basis olursa trailing = 1.0 ATR olur ve tekrar gevsemez
- Basis kaybi tight trailing'i TP2'den once de aktive edebilir
- teknik hard exit yok
- maksimum tasima = 40 adet 4H bar
- TP1 sonrasi break-even yok

Final: **7016 islem, PF 2.693, +0.346R, %53.38 kazanma, 4/4 pozitif, worst-fold +0.134R.**

Ham giris 3/4 iken risk yonetimiyle 4/4'e ciktigi icin 4H PRIMARY degil, **ACTIVE_SECONDARY** tutulur.

## 1D — ACTIVE

Nihai giris B aynidir.

Ham B girisi: 3971 islem, PF 1.328, +0.165R, 4/4 pozitif; worst-fold +0.011R.

Final SAT:

- ilk stop: son 7 gunluk swing low - 0.25 ATR
- TP1 = 1.1R, %30
- TP2 = 2.2R, %30
- TP3 = 3.3R, %20
- runner = %20
- TP2 sonrasi normal trailing = 2.0 ATR
- Close < BB Basis olursa trailing = 1.0 ATR olur ve tekrar gevsemez
- Basis kaybi tight trailing'i TP2'den once de aktive edebilir
- teknik hard exit yok
- maksimum tasima = 60 gunluk bar
- TP1 sonrasi break-even yok

Tight katsayisi 1.6'dan 1.0'a dogru azaltildikca PF, expectancy ve worst-fold birlikte ve monoton bicimde iyilesti. 1.0 ATR production alt siniri olarak kabul edildi; daha asagisi backtest optimumunu kovalamamak icin test edilmedi/adopte edilmedi.

Final: **4480 islem, PF 2.690, +0.346R, %51.76 kazanma, 4/4 pozitif, worst-fold +0.278R.**

## 1W — ACTIVE

Nihai giris yine B'dir.

Ham B girisi: 1241 islem, PF 2.989, +0.714R, 4/4 pozitif; worst-fold +0.417R.

Haftalikta BB Basis veya MACD tabanli teknik cikislar toplam edge'i dusurdu. Yapısal aile kazandi.

Final SAT:

- ilk stop: son 11 haftalik swing low - 0.20 ATR
- TP1 = 1.1R, %30
- TP2 = 2.2R, %30
- TP3 = 3.3R, %20
- runner = %20
- TP2 sonrasi 2.3 ATR trailing
- teknik hard exit yok
- maksimum tasima = 80 haftalik bar
- TP1 sonrasi break-even yok

2.1 / 2.3 / 2.5 ATR trail komsulugu birlikte guclu kaldigi icin 2.3 ATR merkezi plateau degeri secildi; tek bir sinir optimumu kovalanmadi.

Final: **1202 islem, PF 3.164, +0.790R, %57.65 kazanma, 4/4 pozitif, worst-fold +0.519R.**

## TP1 break-even final kontrolu

| TF | NO-BE E(R) | Entry-BE E(R) | Cost-BE E(R) | Karar |
|---|---:|---:|---:|---|
| 4H | +0.346 | +0.273 | +0.267 | NO-BE |
| 1D | +0.346 | +0.280 | +0.278 | NO-BE |
| 1W | +0.790 | +0.644 | +0.646 | NO-BE |

BE kazanma oranini bir miktar artirsa da expectancy ve worst-fold avantajini belirgin azaltmistir. TP1 sonrasi stop giris veya maliyet seviyesine tasinmaz.

## Nihai timeframe kararlari

- 15m / 30m / 45m / 1H / 2H: **REJECT**
- 4H: **ACTIVE_SECONDARY**
- 1D: **ACTIVE**
- 1W: **ACTIVE**
- 1M: **INSUFFICIENT_SAMPLE / RESEARCH**

## Ortak uygulama semantigi

- sinyal yalniz tamamlanmis barda hesaplanir
- giris referansi bir sonraki bar acilisidir
- RSI(14) > 30
- BB Basis = 20 bar basit hareketli ortalama
- BB reclaim = Close[t] > Basis[t] ve Close[t-1] <= Basis[t-1]
- StochRSI(3,3,14,14): K > D final B teyidi
- MACD(12,26,9): Level > Signal final B teyidi
- RVOL20 = Volume[t] / mean(Volume[t-1]..Volume[t-20]); mevcut bar ortalamaya dahil degil
- komisyon 10 bps her yon
- slippage 10 bps her yon
- ayni OHLC barinda stop ve hedef birlikte gorunurse STOP once
- ayni sembolde acik pozisyon varken yeni sinyal yeni islem baslatmaz
- gecmis veri gozlenmistir; gercek bagimsiz dogrulama gelecekteki yeni barlardir

## Run ID'leri

- Entry A/B: `34169205526`
- SAT robustness genis: `34169446265`
- SAT compact kontrol: `34169635503`
- Tight plateau: `34169929644`
- TP1 BE final: `34170112684`
