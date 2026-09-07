# 7 - BB Daralması

**Durum: LOCKED**

Bu klasör tarama #7'nin araştırma geçmişini ve kilitli production spesifikasyonunu içerir. Deney kodları `deneme` reposunda kalır; production'a aktarılacak kesin kurallar `locked-spec.json` dosyasındadır.

## Orijinal fikir

- Bollinger Bands(20,2) dar: Upper-Lower farkı %0-%10
- Volume[t] > önceki 10 aynı-timeframe bar ortalaması
- MACD(12,26,9) bullish crossover
- MACD Level > 0

## Araştırmada test edilen giriş ailesi

BB Width:

`BB Width % = 100 * (Upper - Lower) / Basis`

- `abs10`: BB Width <= %10
- `abs5`: BB Width <= %5
- `relative20`: mevcut genişlik, mevcut bar hariç önceki 120 gözlemin %20 persentilinin altında/eşit
- `release20`: önceki bar relative20 squeeze içindeydi ve mevcut barda bant genişliği artmaya başladı

MACD:

- `cross`: fresh bullish crossover + MACD Level > 0
- `hist_rise2`: `H[t] > H[t-1] > H[t-2]` + MACD Level > 0; yalnız yeni başlayan epizot sinyaldir

Hacim:

`Volume[t] > mean(Volume[t-1] ... Volume[t-10])`

Mevcut bar ortalamaya katılmaz; her timeframe kendi barlarını kullanır.

## Nihai sınıflandırma

| TF | Durum | Kilitli giriş |
|---|---|---|
| 15m | REJECT | — |
| 30m | REJECT | — |
| 45m | REJECT | — |
| 1H | REJECT | — |
| 2H | REJECT | — |
| 4H | ACTIVE_SECONDARY | relative20 squeeze + MACD bullish crossover + MACD>0 + 10-bar hacim |
| 1D | ACTIVE | BB Width<=%10 + histogram iki bar güçleniyor + MACD>0 + 10-bar hacim |
| 1W | ACTIVE | release20 + histogram iki bar güçleniyor + MACD>0 + 10-bar hacim |
| 1M | RESEARCH_FORWARD_WATCH | release20 + histogram iki bar güçleniyor + MACD>0 + 10-bar hacim |

## Kilitli doğrulama özeti

- 4H: 1,967 işlem · PF 1.530 · E +0.183R · 4/4 pozitif — secondary, çünkü en kötü fold marjı yalnız +0.003R.
- 1D: 2,716 işlem · PF 1.715 · E +0.335R · 4/4 pozitif.
- 1W: 1,597 işlem · PF 2.680 · E +0.657R · 4/4 pozitif.
- 1M: 82 işlem · PF 2.077 · E +0.407R · 3/4 pozitif — production dışı.

TP1 sonrası break-even 4H/1D/1W/1M'nin tamamında expectancy'yi düşürdüğü için **NO-BE** kilitlendi.

## Dosyalar

- `reports/final-decision.md` — insan-okunur nihai araştırma raporu
- `locked-spec.json` — ana repoya aktarılacak makine-okunur kesin kurallar
- `bb_squeeze_entry_stage.py` — giriş kalitesi araştırması
- `bb_squeeze_sat_robustness.py` — SAT ailesi ve dar parametre robustness
- `bb_squeeze_be_final.py` — materyal-gate sonrası nihai BE doğrulaması

Araştırma run ID'leri: entry `34157171006`, SAT `34157449047`, final BE `34158149944`.

Geçmiş veri gözlenmiştir; bundan sonraki gerçekten bağımsız doğrulama gelecekte oluşacak yeni barlardır.
