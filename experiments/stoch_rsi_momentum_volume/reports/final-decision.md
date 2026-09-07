# StochRSI / Momentum / Hacim — Nihai Araştırma Kararı

Tarih: 2026-09-07

Bu belge ikinci taramanın giriş, hacim ve SAT araştırmasını kilitler. Sonuçlar gelecekteki yeni repo entegrasyonunda referans alınacaktır.

## 1. Değişmeyen temel kurallar

### Hacim

Her timeframe kendi barlarıyla hesaplanır:

```text
Volume[t] > mean(Volume[t-1] ... Volume[t-10])
```

Mevcut bar 10-bar ortalamasına dahil edilmez. MTF sayısal karşılaştırma yoktur.

### Sinyal / execution

- Sinyal yalnız tamamlanmış mumda oluşur.
- Giriş referansı sonraki mum açılışıdır (`t+1 Open`).
- Look-ahead kullanılmaz.
- Tarihsel araştırmada 10 bps komisyon + 10 bps slippage / taraf kullanılmıştır.
- Aynı OHLC barda stop ve hedef birlikte görülürse STOP önce değerlendirilir.

## 2. Timeframe kararı

| TF | Karar | Giriş modeli |
|---|---|---|
| 15m | REJECT | — |
| 30m | REJECT | — |
| 45m | REJECT | — |
| 1H | REJECT | — |
| 2H | REJECT | — |
| 4H | RESEARCH / erken uyarı | production değil |
| **1D** | **ACTIVE ADAYI — LOCKED** | **Stoch trigger** |
| **1W** | **ACTIVE ADAYI — LOCKED** | **Momentum trigger** |
| **1M** | **ACTIVE + FORWARD WATCH — LOCKED** | **Momentum trigger** |

İlk walk-forward sonuçları güçlü timeframe'lerde 4/4 pozitif dönem üretmiştir; 4H yalnız 2/4 pozitif olduğundan production'a alınmamıştır.

## 3. Nihai giriş kuralları

### 1D

```text
StochRSI(3,3,14,14) K crosses above D
AND MOM(10) > 0
AND Volume[t] > mean(previous 10 daily bars)
```

### 1W

```text
MOM(10) crosses above 0
AND StochRSI(3,3,14,14) K > D
AND Volume[t] > mean(previous 10 weekly bars)
```

### 1M

```text
MOM(10) crosses above 0
AND StochRSI(3,3,14,14) K > D
AND Volume[t] > mean(previous 10 monthly bars)
```

## 4. Dar SAT robustness sonucu

Girişler sabit tutuldu. Önceden sonuçlar görülmeden belirlenen iki aşamalı test kullanıldı:

1. 27 aday: swing penceresi × ATR buffer × trailing komşuluğu.
2. 9 aday: seçilen platonun çevresinde TP ailesi × maksimum taşıma.

Seçim tek maksimuma göre değil; dört kronolojik dönemde pozitiflik, en kötü dönem expectancy'si ve plato merkezi ile yapıldı. Baseline ancak `+0.03R expectancy` veya `+0.10 PF` gibi önceden belirlenen maddi iyileşme eşiği aşılırsa değiştirildi.

### 1D — KEEP BASELINE

Baseline:

- swing: 7 bar
- buffer: 0.20 ATR
- trailing: 2.20 ATR
- max hold: 40 bar
- TP: 1R / 2R / 3R

Robustness pencerelerinde:

- 10,108 işlem
- PF: **1.576**
- expectancy: **+0.276R**
- kazanma: **%46.74**
- dönem expectancy: `+0.595R / +0.212R / +0.145R / +0.163R`

Komşuluk adayı (9 swing, 48 bar hold, 1.1/2.2/3.3R) expectancy'yi +0.026R ve PF'yi +0.036 artırdı; fakat önceden belirlenen maddi değişiklik eşiğini aşmadığı için **baseline korunmuştur**.

### 1W — KEEP BASELINE

Baseline:

- swing: 9 bar
- buffer: 0.15 ATR
- trailing: 2.30 ATR
- max hold: 60 bar
- TP: 1R / 2R / 3R

Robustness pencerelerinde:

- 4,324 işlem
- PF: **2.689**
- expectancy: **+0.644R**
- kazanma: **%56.71**
- dönem expectancy: `+0.284R / +1.046R / +0.782R / +0.415R`

Komşuluk adayı toplam expectancy'yi yalnız +0.0006R artırırken PF'yi düşürdü. **Baseline korunmuştur.**

### 1M — ADOPT NARROW OPTIMIZED

Eski baseline:

- swing 9
- buffer 0.15 ATR
- trailing 2.50 ATR
- max hold 36 bar
- TP 1R / 2R / 3R

Nihai profil:

- **swing: 7 bar**
- **buffer: 0.15 ATR**
- **trailing: 2.70 ATR**
- **max hold: 36 bar**
- **TP: 1.1R / 2.2R / 3.3R**

Nihai profil robustness pencerelerinde:

- 606 işlem
- PF: **4.382**
- expectancy: **+0.998R**
- kazanma: **%63.20**
- dönem expectancy: `+0.633R / +1.668R / +1.654R / +0.294R`

Eski baseline'a göre expectancy **+0.059R** ve en kötü dönem **+0.029R** iyileşti. PF 4.441'den 4.382'ye hafif geriledi; maddi ve dönemler arası tutarlı expectancy iyileşmesi nedeniyle dar optimize profil kabul edildi.

> Not: Bu SAT robustness tablosundaki işlem sayıları önceki sabit-giriş tablosuyla birebir aynı olmak zorunda değildir; burada kronolojik sınırlar yalnız kilitlenmiş giriş modelinin sinyal zamanlarından kurulmuştur. Karşılaştırmalar aynı koşu içindeki baseline vs aday arasında yapılmıştır.

## 5. TP1 break-even A/B — nihai karar: KULLANMA

Üç model test edildi:

- `no_be`: TP1 sonrası stop değiştirilmez.
- `entry_be`: TP1 sonrası, sonraki bardan itibaren stop en az giriş fiyatına çekilir.
- `cost_be`: stop komisyon + slippage dahil gerçek maliyet fiyatına çekilir (test varsayımında yaklaşık giriş × 1.004008).

| TF | No-BE E(R) | En iyi BE E(R) | No-BE PF | En iyi BE PF | Karar |
|---|---:|---:|---:|---:|---|
| 1D | **+0.276R** | +0.244R | **1.576** | 1.568 | **NO-BE** |
| 1W | **+0.644R** | +0.530R | **2.689** | 2.579 | **NO-BE** |
| 1M | **+0.998R** | +0.802R | **4.382** | 4.104 | **NO-BE** |

BE modelleri kazanma oranını yükseltti ancak expectancy'yi ve büyük hareketlerden alınan payı düşürdü. Bu tarama için TP1 sonrası break-even **production kuralı değildir**.

## 6. Nihai SAT yaşam döngüsü

Tüm güçlü timeframe'lerde:

- Başlangıç stopu yapısal swing-low tabanlıdır.
- Ham risk 0.60 ATR ile 2.60 ATR arasında sınırlandırılır.
- Swing stop geçersizse ATR fallback kullanılır.
- TP1: pozisyonun %30'u.
- TP2: %30; **buradan sonra ATR trailing aktif olur**.
- TP3: %20.
- Runner: %20 ve trailing ile devam eder.
- **TP1 sonrası break-even yoktur.**
- StochRSI/Momentum hard-SAT yoktur.
- Aynı bar stop + hedef belirsizliğinde stop önceliklidir.

Fallback stop ATR katsayısı:

- 1D: 1.25 ATR
- 1W: 1.30 ATR
- 1M: 1.30 ATR

## 7. Nihai sınıflandırma

**1D:** ACTIVE adayı; giriş ve SAT profili kilitli.

**1W:** ACTIVE adayı; en güçlü ve en istikrarlı timeframe'lerden biri; profil kilitli.

**1M:** ACTIVE + forward-watch; güçlü sonuç, ancak doğal olarak daha küçük örneklem nedeniyle yeni aylık veriler geldikçe izlenmeli.

**4H:** research/erken uyarı; production başarı barajını geçmedi.

**15m–2H:** bu tarama ailesi için kullanılmayacak.

Bu aşamayla ikinci taramanın tarihsel giriş/SAT araştırması tamamlanmıştır. Yeni repo entegrasyonunda burada kilitlenen kurallar değiştirilmeden taşınmalı; yeni veriyle yalnız forward doğrulama yapılmalıdır.
