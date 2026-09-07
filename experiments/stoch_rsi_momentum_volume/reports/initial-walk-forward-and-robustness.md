# StochRSI / Momentum / Hacim — İlk Walk-Forward + Sabit-Kural Robustness

Tarih: 2026-09-07

## Sabit hacim tanımı

Bütün timeframe'lerde:

```text
Volume[t] > mean(Volume[t-1] ... Volume[t-10])
```

Mevcut mum referans ortalamasına dahil edilmez. 15m'de önceki 10 adet 15m bar; 1D'de önceki 10 günlük bar; 1W'de önceki 10 haftalık bar kullanılır.

## Giriş adayları

- **A — Original double cross:** `MOM10 ↑ 0 AND StochRSI K ↑ D`
- **B — Stoch trigger:** `StochRSI K ↑ D AND MOM10 > 0`
- **C — Momentum trigger:** `MOM10 ↑ 0 AND StochRSI K > D`

Tüm modeller 10-bar hacim şartını içerir.

## İlk expanding walk-forward sonucu

Maliyet: 10 bps komisyon + 10 bps slippage / taraf. Giriş sonraki mum açılışıdır.

| TF | WF işlem | PF | E(R) | Kazanma | Pozitif fold | Sınıf |
|---|---:|---:|---:|---:|---:|---|
| 15m | 31,338 | 0.285 | -0.795R | 28.44% | 0/4 | REJECT |
| 30m | 32,694 | 0.453 | -0.469R | 32.20% | 0/4 | REJECT |
| 45m | 35,367 | 0.584 | -0.335R | 34.17% | 0/4 | REJECT |
| 1H | 15,929 | 0.598 | -0.317R | 32.76% | 0/4 | REJECT |
| 2H | 16,158 | 0.812 | -0.129R | 35.98% | 0/4 | REJECT |
| 4H | 5,727 | 1.171 | +0.092R | 42.85% | 2/4 | POSITIVE / UNSTABLE |
| 1D | 10,233 | 1.540 | +0.262R | 46.14% | 4/4 | STRONG |
| 1W | 4,198 | 2.598 | +0.620R | 55.76% | 4/4 | STRONG |
| 1M | 677 | 3.364 | +0.738R | 60.86% | 4/4 | STRONG; sample caution |

## Sabit-kural robustness

Adaptive fold seçiminin sonucu şişirmediğini kontrol etmek için A/B/C girişlerinin her biri aynı yapısal SAT ile dört kronolojik pencerede sabit tutuldu.

### 1D

| Giriş | İşlem | PF | E(R) | Kazanma | Pozitif fold | Karar |
|---|---:|---:|---:|---:|---:|---|
| **B — Stoch trigger** | **10,233** | **1.540** | **+0.262R** | **46.14%** | **4/4** | ROBUST_STRONG |
| C — Momentum trigger | 11,233 | 1.414 | +0.206R | 44.63% | 4/4 | ROBUST_STRONG |
| A — Double cross | 3,789 | 1.445 | +0.220R | 44.76% | 3/4 | ROBUST_PROMISING |

**1D ana giriş adayı:**

```text
StochRSI K crosses above D
AND MOM(10) > 0
AND Volume[t] > mean(previous 10 same-TF bars)
```

### 1W

| Giriş | İşlem | PF | E(R) | Kazanma | Pozitif fold | Karar |
|---|---:|---:|---:|---:|---:|---|
| **C — Momentum trigger** | **4,198** | **2.598** | **+0.620R** | **55.76%** | **4/4** | ROBUST_STRONG |
| A — Double cross | 1,342 | 2.305 | +0.547R | 52.53% | 4/4 | ROBUST_STRONG |
| B — Stoch trigger | 4,007 | 2.322 | +0.547R | 52.58% | 4/4 | ROBUST_STRONG |

**1W ana giriş adayı:**

```text
MOM(10) crosses above 0
AND StochRSI K > D
AND Volume[t] > mean(previous 10 same-TF bars)
```

### 1M

| Giriş | İşlem | PF | E(R) | Kazanma | Pozitif fold | Karar |
|---|---:|---:|---:|---:|---:|---|
| **C — Momentum trigger** | **515** | **3.686** | **+0.776R** | **61.94%** | **4/4** | ROBUST_STRONG |
| A — Double cross | 167 | 3.278 | +0.745R | 59.28% | 4/4 | ROBUST_STRONG |
| B — Stoch trigger | 789 | 3.254 | +0.746R | 59.32% | 4/4 | ROBUST_STRONG |

**1M ana giriş adayı:** C — Momentum trigger. Sonuç güçlüdür; aylık frekansta 515 işlem olduğu için 1D/1W'ye göre örneklem daha küçüktür ve yeni forward veri ile izlenmelidir.

### 4H

| Giriş | İşlem | PF | E(R) | Kazanma | Pozitif fold | Karar |
|---|---:|---:|---:|---:|---:|---|
| A — Double cross | 5,727 | 1.171 | +0.092R | 42.85% | 2/4 | POSITIVE_UNSTABLE |
| C — Momentum trigger | 13,354 | 1.141 | +0.075R | 42.44% | 2/4 | POSITIVE_UNSTABLE |
| B — Stoch trigger | 12,387 | 1.105 | +0.058R | 41.56% | 2/4 | POSITIVE_UNSTABLE |

4H production barajını geçmez; research/erken uyarı olarak tutulabilir.

## SAT tarafındaki ilk sonuç

Güçlü 1D/1W/1M walk-forward koşularının tamamında **structural_control** seçildi. Stoch aşağı kesişimi, MOM sıfır altına kesişimi, ikisinin birlikte zayıflaması ve adaptive teknik çıkışlar kalıcı üstünlük göstermedi.

İlk güçlü yapısal profiller:

### 1D
- son 7 mum swing low - 0.20 ATR
- TP1 1R / %30
- TP2 2R / %30
- TP3 3R / %20
- runner %20
- TP2 sonrası 2.20 ATR trailing
- maksimum 40 mum
- hard Stoch/MOM SAT yok

### 1W
- son 9 mum swing low - 0.15 ATR
- TP1 1R / %30
- TP2 2R / %30
- TP3 3R / %20
- runner %20
- TP2 sonrası 2.30 ATR trailing
- maksimum 60 mum
- hard Stoch/MOM SAT yok

### 1M
- son 9 mum swing low - 0.15 ATR
- TP1 1R / %30
- TP2 2R / %30
- TP3 3R / %20
- runner %20
- TP2 sonrası 2.50 ATR trailing
- maksimum 36 mum
- hard Stoch/MOM SAT yok

## Şu anki karar

- **1D:** güçlü production adayı; B giriş modeli.
- **1W:** güçlü production adayı; C giriş modeli.
- **1M:** güçlü araştırma/production adayı; C giriş modeli, örneklem nedeniyle forward izleme gerekli.
- **4H:** research / erken uyarı.
- **15m / 30m / 45m / 1H / 2H:** bu tarama ailesi için reject.

Tarama tamamen kilitlenmeden önce 1D/1W/1M için yapısal SAT parametrelerinin dar ve mantıklı bir komşulukta robustness/optimizasyon testi yapılmalıdır. Giriş kurallarının ana yönü ise sabit-kural testinde doğrulanmıştır.
