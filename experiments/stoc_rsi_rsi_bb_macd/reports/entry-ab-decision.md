# 11 - Stoc.RSI & RSI & BB & MACD — A/B Giris Karari

Run: `34169205526`

A = RSI14>30 + StochRSI fresh K>D + Close fresh crosses above BB20 Basis + MACD fresh crosses above Signal + RVOL20>1.50.

B = RSI14>30 + Close fresh crosses above BB20 Basis + StochRSI K>D + MACD>Signal + RVOL20>1.50.

Her iki model ayni yapisal SAT kontrolu, ayni maliyetler ve kendi sinyal zamanlarindan olusan 4 kronolojik pencere ile test edildi.

| TF | A trades | A PF | A E(R) | A folds | B trades | B PF | B E(R) | B folds | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 15m | 3456 | 0.235 | -0.927 | 0/4 | 14994 | 0.246 | -0.905 | 0/4 | REJECT |
| 30m | 3343 | 0.381 | -0.602 | 0/4 | 15543 | 0.403 | -0.572 | 0/4 | REJECT |
| 45m | 3730 | 0.499 | -0.429 | 0/4 | 16591 | 0.541 | -0.382 | 0/4 | REJECT |
| 1H | 1588 | 0.528 | -0.391 | 0/4 | 7612 | 0.559 | -0.359 | 0/4 | REJECT |
| 2H | 2466 | 0.853 | -0.100 | 1/4 | 12367 | 0.913 | -0.057 | 1/4 | REJECT |
| 4H | 1267 | 1.309 | +0.153 | 2/4 | 6043 | 1.250 | +0.125 | 3/4 | B SAT research |
| 1D | 629 | 1.150 | +0.080 | 3/4 | 3971 | 1.328 | +0.165 | 4/4 | B wins |
| 1W | 209 | 2.507 | +0.590 | 4/4 | 1241 | 2.989 | +0.714 | 4/4 | B wins |
| 1M | 0 completed | — | — | — | 37 | 2.987 | +0.638 | 2/4 | insufficient/research |

## Fold detayi

4H B: `+0.292R, +0.014R, +0.301R, -0.202R`.

1D B: `+0.347R, +0.065R, +0.184R, +0.011R`.

1W B: `+0.417R, +1.085R, +0.795R, +0.531R`.

## Karar

Production arastirmasina B modeli tasinir. A ayni barda uc fresh crossover gerektirdigi icin 1D/1W'de daha az sinyal ve daha dusuk stitched edge uretmistir. 1W'de A yine de tarihsel olarak gucludur; ancak B hem daha genis orneklem hem daha yuksek PF/expectancy/worst-fold vermistir.

15m-2H production arastirmasindan elenir. 4H B yalniz 3/4 oldugu icin SAT ile 4/4'e tasinabilirse secondary olabilir. 1D ve 1W B aktif adaydir. 1M orneklem yetersizdir.

Gecmis veri gozlenmistir; gercek bagimsiz dogrulama gelecekteki yeni barlardir.
