# NE ARARSAN VAR — 10-Bar Hacim A/B Sonucu

Tarih: 2026-09-07

## Test edilen ek şart

Mevcut final girişe şu koşul eklenmiştir:

```text
Volume[t] > mean(Volume[t-1] ... Volume[t-10])
```

- Her timeframe kendi barlarını kullanır.
- Mevcut bar 10-bar referans ortalamasına dahil edilmez.
- Mevcut `RVOL20 > 1.50` şartı korunmuştur.
- 1D ve 1W final yapısal SAT profilleri sabit tutulmuştur.
- Dört kronolojik pencerede A/B karşılaştırması yapılmıştır.

## 1D

| Model | İşlem | PF | E(R) | Kazanma | Pozitif pencere |
|---|---:|---:|---:|---:|---:|
| Mevcut final kural | 5,105 | 1.4126 | +0.20031R | 44.84% | 4/4 |
| + 10-bar hacim | 5,100 | 1.4116 | +0.19985R | 44.82% | 4/4 |

Fark:
- yalnız 5 işlem elendi
- PF `-0.0010`
- expectancy `-0.00046R`
- kazanma oranı `-0.015 puan`

## 1W

| Model | İşlem | PF | E(R) | Kazanma | Pozitif pencere |
|---|---:|---:|---:|---:|---:|
| Mevcut final kural | 1,987 | 3.0795 | +0.72781R | 59.89% | 4/4 |
| + 10-bar hacim | 1,986 | 3.0840 | +0.72869R | 59.92% | 4/4 |

Fark:
- yalnız 1 işlem elendi
- PF `+0.0045`
- expectancy `+0.00088R`
- kazanma oranı `+0.030 puan`

## Karar

10-bar hacim filtresi `NE ARARSAN VAR` için **production kuralına eklenmeyecek**.

Nedeni: mevcut `RVOL20 > 1.50` filtresi zaten bu daha zayıf hacim şartını neredeyse tamamen kapsıyor. Ek koşul 1D'de 5, 1W'de yalnız 1 sinyal değiştirdi ve performansa maddi katkı sağlamadı. Gereksiz/redundant filtre olarak tutulmaması daha sade ve açıklanabilir bir production kuralı sağlar.

Bu karar ikinci taramadaki 10-bar hacim kullanımını etkilemez; ikinci taramada RVOL şartı bulunmadığı için 10-bar hacim filtresi bağımsız ve anlamlı bir katılım filtresidir.
