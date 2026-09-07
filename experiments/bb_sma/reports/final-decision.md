# BB & SMA — Nihai Araştırma Kararı

Tarih: 2026-09-07

Bu belge üçüncü taramanın tarihsel araştırmasını kilitler. Yeni production repo entegrasyonunda ACTIVE olarak işaretlenen kurallar değiştirilmeden taşınmalı; bundan sonraki iyileştirme yalnız yeni veriyle forward doğrulama üzerinden yapılmalıdır.

## 1. Taramanın sadeleştirilmiş mantığı

TradingView ekranındaki `BB(20) Basis` varsayılan olarak `SMA20` ile aynıdır. Bu nedenle `Fiyat > BB Basis` ve ayrıca `Fiyat > SMA20` ayrı koşullar değildir.

Temel trend/reclaim olayı:

```text
Close[t] > SMA20[t]
AND Close[t-1] <= SMA20[t-1]
AND SMA20 > SMA50 > SMA200
```

Bu tarama bir **yükselen ana trend içinde SMA20/Bollinger orta bant geri kazanımı (trend continuation / pullback reclaim)** taramasıdır.

## 2. Ortak araştırma kuralları

- Sinyal yalnız tamamlanmış mumda oluşur.
- Giriş referansı sonraki mum açılışıdır (`t+1 Open`).
- Look-ahead kullanılmaz.
- Tarihsel test maliyeti: 10 bps komisyon + 10 bps slippage / taraf.
- Hacim filtresi kullanıldığı TF'lerde:

```text
Volume[t] > mean(Volume[t-1] ... Volume[t-10])
```

  Mevcut bar ortalamaya dahil edilmez ve her timeframe kendi barlarını kullanır.
- Aynı OHLC barda stop ve hedef birlikte görünürse STOP önceliklidir.
- İlk risk 0.60 ATR ile 2.60 ATR arasında sınırlandırılır.

## 3. 15m–1M ilk walk-forward özeti

| TF | İşlem | PF | E(R) | Pozitif fold | İlk karar |
|---|---:|---:|---:|---:|---|
| 15m | 11,059 | 0.292 | -0.722 | 0/4 | REJECT |
| 30m | 10,111 | 0.473 | -0.414 | 0/4 | REJECT |
| 45m | 8,260 | 0.616 | -0.264 | 0/4 | REJECT |
| 1H | 3,329 | 0.983 | -0.007 | 1/4 | REJECT |
| 2H | 7,539 | 1.310 | +0.108 | 4/4 | aday |
| 4H | 3,646 | 1.394 | +0.134 | 4/4 | aday |
| 1D | 3,495 | 1.379 | +0.194 | 3/4 | aday |
| 1W | 1,633 | 2.830 | +0.685 | 4/4 | güçlü aday |
| 1M | 115 | 3.484 | +0.764 | 2/4 | kararsız |

İlk turdan sonra 2H/4H/1D/1W/1M için her giriş+SAT kombinasyonu dört kronolojik pencerede sabit tutularak yeniden test edildi. Daha sonra kilitli giriş ve çıkış ailesi için dar SAT komşuluk testi yapıldı.

## 4. Nihai timeframe sınıflandırması

| TF | Nihai durum |
|---|---|
| 15m | REJECT |
| 30m | REJECT |
| 45m | REJECT |
| 1H | REJECT |
| **2H** | **ACTIVE — LOCKED** |
| **4H** | **ACTIVE — LOCKED** |
| **1D** | **ACTIVE — LOCKED** |
| **1W** | **ACTIVE — LOCKED** |
| 1M | RESEARCH / FORWARD-WATCH — production değil |

## 5. Nihai giriş kuralları

### 2H — ACTIVE

```text
Close crosses above SMA20
AND SMA20 > SMA50 > SMA200
AND SMA20[t] > SMA20[t-1]
AND Volume[t] > mean(previous 10 x 2H bars)
```

### 4H — ACTIVE

```text
Close crosses above SMA20
AND SMA20 > SMA50 > SMA200
AND Volume[t] > mean(previous 10 x 4H bars)
```

SMA20 eğim filtresi 4H'de production şartı değildir.

### 1D — ACTIVE

```text
Close crosses above SMA20
AND SMA20 > SMA50 > SMA200
AND SMA20[t] > SMA20[t-1]
AND Volume[t] > mean(previous 10 daily bars)
```

### 1W — ACTIVE

```text
Close crosses above SMA20
AND SMA20 > SMA50 > SMA200
AND Volume[t] > mean(previous 10 weekly bars)
```

SMA20 eğim filtresi 1W'de production şartı değildir.

### 1M — RESEARCH ONLY

```text
Close crosses above SMA20
AND SMA20 > SMA50 > SMA200
```

Hacim ve SMA20 eğimi aylık araştırma modelinin şartı değildir. Ancak girişe özgü kronolojik sınırlarla yapılan son SAT robustness testinde yalnız 2/4 dönem pozitif kaldığı için production'a alınmaz.

## 6. Nihai SAT profilleri

### 2H — KEEP BASELINE

Giriş: `D_slope_volume`

- Başlangıç stop: son **7 bar swing low - 0.18 ATR**
- TP1: **+1R**, %30
- TP2: **+2R**, %30
- TP3: **+3R**, %20
- Runner: %20
- Normal trailing: **1.90 ATR**
- Fiyat SMA20 altına kapanırsa: trailing **1.40 ATR**'ye sıkılaşır
- Fiyat SMA50 altına kapanırsa: kalan pozisyon teknik olarak kapanır
- Maksimum taşıma: **40 adet 2H bar**
- TP1 sonrası break-even: **YOK**

Dar SAT robustness:

- 7,483 işlem
- PF **1.302**
- expectancy **+0.106R**
- kazanma **%42.96**
- **4/4 pozitif dönem**
- en kötü dönem **+0.072R**

Komşuluk adayı yalnız +0.019R expectancy / +0.060 PF iyileştirdi; maddi değişiklik eşiğini geçmedi. Baseline korundu.

### 4H — KEEP BASELINE

Giriş: `C_volume`

- Başlangıç stop: son **7 bar swing low - 0.20 ATR**
- TP1 / TP2 / TP3: **1R / 2R / 3R**, dağılım %30 / %30 / %20
- Runner: %20
- Normal trailing: **2.00 ATR**
- SMA20 kaybında trailing: **1.50 ATR**
- SMA50 kaybında teknik çıkış
- Maksimum taşıma: **40 adet 4H bar**
- TP1 sonrası break-even: **YOK**

Dar SAT robustness:

- 4,995 işlem
- PF **1.416**
- expectancy **+0.138R**
- kazanma **%42.44**
- **4/4 pozitif dönem**
- en kötü dönem **+0.106R**

Alternatif yalnız +0.019R expectancy / +0.071 PF getirdi; baseline korundu.

### 1D — KEEP BASELINE

Giriş: `D_slope_volume`

- Başlangıç stop: son **7 günlük bar swing low - 0.20 ATR**
- TP1 / TP2 / TP3: **1R / 2R / 3R**, dağılım %30 / %30 / %20
- Runner: %20
- Normal trailing: **2.20 ATR**
- SMA20 kaybında trailing: **1.65 ATR**
- SMA50 kaybında teknik çıkış
- Maksimum taşıma: **40 günlük bar**
- TP1 sonrası break-even: **YOK**

Dar SAT robustness:

- 3,098 işlem
- PF **1.636**
- expectancy **+0.206R**
- kazanma **%43.74**
- **4/4 pozitif dönem**
- en kötü dönem **+0.102R**

Komşuluk adayı +0.021R expectancy / +0.072 PF sağladı; maddi değişiklik eşiğini geçmedi. Baseline korundu.

### 1W — ADOPT NARROW OPTIMIZED

Giriş: `C_volume`

- Başlangıç stop: son **11 haftalık bar swing low - 0.15 ATR**
- TP1: **+1.1R**, %30
- TP2: **+2.2R**, %30
- TP3: **+3.3R**, %20
- Runner: %20
- TP2 sonrası trailing: **2.10 ATR**
- Teknik SMA20/SMA50 hard-exit: **YOK**
- Maksimum taşıma: **60 haftalık bar**
- TP1 sonrası break-even: **YOK**

Dar SAT robustness:

- 1,572 işlem
- PF **2.726**
- expectancy **+0.677R**
- kazanma **%55.34**
- **4/4 pozitif dönem**
- dönem expectancy: `+0.923R / +0.902R / +0.581R / +0.196R`

Eski baseline PF 2.633 / +0.631R idi. Yeni profil PF'yi +0.093 ve expectancy'yi +0.046R artırırken en kötü dönemi +0.0195R iyileştirdi. Bu nedenle dar optimize profil kabul edildi.

### 1M — RESEARCH / FORWARD-WATCH

Araştırma profili:

- giriş: saf SMA20 reclaim + SMA20>SMA50>SMA200
- stop: 9 bar swing - 0.15 ATR
- TP: 1R / 2R / 3R
- trailing: 2.50 ATR
- max hold: 36 aylık bar
- teknik çıkış: SMA20, SMA50'yi aşağı keserse
- TP1 sonrası BE: kullanılmaz

Girişe özgü kronolojik pencerelerde:

- 229 işlem
- PF **3.936**
- expectancy **+0.801R**
- fakat yalnız **2/4 pozitif dönem**
- en kötü dönem **-0.199R**

Bu nedenle yüksek toplam rakama rağmen production için yeterince kararlı değildir.

## 7. TP1 break-even A/B — nihai karar

Düzeltilmiş A/B testi, fold sınırını aşan işlemleri önceki SAT robustness ile aynı şekilde dışarıda bıraktı.

| TF | No-BE E(R) | En iyi BE E(R) | No-BE PF | Karar |
|---|---:|---:|---:|---|
| 2H | **+0.106** | +0.063 | **1.302** | **NO-BE** |
| 4H | **+0.138** | +0.105 | **1.416** | **NO-BE** |
| 1D | **+0.206** | +0.168 | **1.636** | **NO-BE** |
| 1W | **+0.677** | +0.579 | **2.726** | **NO-BE** |

Break-even modelleri kazanma oranını yükseltti ancak expectancy'yi ve büyük trendlerden kalan pozisyonla alınan payı düşürdü. Bu nedenle ACTIVE timeframe'lerin tamamında TP1 sonrası stop giriş/maliyet fiyatına çekilmez.

## 8. Nihai pozisyon yaşam döngüsü

ACTIVE timeframe'lerde ortak mantık:

1. Sinyal tamamlanmış barda oluşur, giriş referansı `t+1 Open`.
2. İlk stop swing-low + ATR buffer ile hesaplanır; risk 0.60–2.60 ATR aralığına sıkıştırılır.
3. TP1'de %30 azaltılır; **stop break-even'a taşınmaz**.
4. TP2'de %30 azaltılır ve normal ATR trailing aktif olur.
5. TP3'te %20 azaltılır.
6. Son %20 runner olarak trailing ile devam eder.
7. 2H/4H/1D adaptif modellerde SMA20 kaybı riski sıkılaştırır; SMA50 kaybı kalan pozisyonu kapatır.
8. 1W'de teknik hard-exit kullanılmaz; yapısal stop + hedef + runner/trailing korunur.

## 9. Kilit kararı

**Production adayları:** 2H, 4H, 1D, 1W.

**Reject:** 15m, 30m, 45m, 1H.

**Research/forward-watch:** 1M.

Bu tarihsel veri artık defalarca görülmüştür; bundan sonra aynı tarih üzerinde yeni parametre aramak gerçek OOS sayılmaz. ACTIVE kurallar yeni repo entegrasyonunda burada yazıldığı haliyle taşınmalı ve yalnız gelecekte oluşan yeni barlarla forward performansı izlenmelidir.
