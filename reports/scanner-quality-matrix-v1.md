# Tarama Kalite Matrisi ve Final Promotion Kararı — v1

Tarih: 2026-09-08  
Durum: **FROZEN RESEARCH PROMOTION POLICY**

Bu belge `deneme` reposunda tamamlanan tarama araştırmalarını tek bir başarı standardında toplar. Amaç, hangi tarama + timeframe çiftlerinin gelecekte `taramabot` production katmanına hangi ağırlıkla taşınacağını sabitlemektir.

> Bu sonuçların dayandığı tarihsel veri araştırma sırasında defalarca görülmüştür. Buradaki sınıflandırma tarihsel robustness kararıdır; gerçek bağımsız doğrulama bundan sonra oluşacak yeni barlarla yapılacaktır.

## 1. Ortak kabul barajı

Bir tarama + timeframe çiftinin normal production adayı olabilmesi için birlikte şu şartları sağlamasını istiyoruz:

- 4/4 kronolojik dönemde pozitif expectancy
- en kötü fold expectancy > 0
- PF >= 1.25
- expectancy >= +0.10R
- en az 300 tamamlanmış işlem
- final/locked araştırmada production-active olması
- 1M olmaması

Bu barajı geçen ancak girişinin kendisi yeterince robust olmayıp özel/adaptif SAT sayesinde 4/4'e ulaşan modeller **SECONDARY** olarak tutulur. Aylık modeller tarihsel rakamları ne kadar yüksek olursa olsun ortak politikada **FORWARD_WATCH** olarak harmonize edilir.

## 2. Quality Score v1

Quality Score yalnız sıralama yardımcısıdır; kabul barajının yerine geçmez.

| Bileşen | Ağırlık |
|---|---:|
| 4-fold robustness | 25 |
| Worst-fold expectancy | 20 |
| Toplam expectancy | 20 |
| Profit Factor | 15 |
| Örneklem büyüklüğü | 15 |
| Giriş bağımsızlığı / SAT bağımlılığı | 5 |

Hesap:

```text
Fold:
4/4 = 25
3/4 = 15
2/4 = 5
aksi = 0

Worst-fold:
20 * clamp(worst_fold_R, 0, 0.40) / 0.40

Expectancy:
20 * clamp(E_R, 0, 0.80) / 0.80

PF:
15 * clamp(PF - 1, 0, 2) / 2

Sample:
15 * min(log10(trades) / 4, 1)

Independence:
ACTIVE = 5
ACTIVE_SECONDARY = 2
RESEARCH/WATCH = 0
```

Kabul barajı geçildikten sonra ve explicit management-dependence yoksa:

- **CORE:** score >= 75
- **ACTIVE:** score < 75
- **SECONDARY:** locked araştırma özel risk yönetimine bağımlı diyorsa score yüksek olsa bile secondary kalır.

## 3. Tüm taramaların timeframe matrisi

Kısaltmalar: `CORE`, `ACTIVE`, `SEC` = Secondary, `WATCH` = Forward Watch, `RES` = Research, `REJ` = Reject.

| Tarama | 15m | 30m | 45m | 1H | 2H | 4H | 1D | 1W | 1M |
|---|---|---|---|---|---|---|---|---|---|
| NE ARARSAN VAR | REJ | REJ | REJ | REJ | RES | RES | ACTIVE | **CORE** | WATCH |
| StochRSI / Momentum / Hacim | REJ | REJ | REJ | REJ | REJ | RES | ACTIVE | **CORE** | WATCH |
| BB & SMA | REJ | REJ | REJ | REJ | **ACTIVE** | **ACTIVE** | **ACTIVE** | **CORE** | WATCH |
| RSI & MACD - RVOL | REJ | REJ | REJ | REJ | REJ | SEC | ACTIVE | **CORE** | WATCH |
| 7 - BB Daralması | REJ | REJ | REJ | REJ | REJ | SEC | ACTIVE | **CORE** | WATCH |
| 8 - TavanTarama | REJ | REJ | REJ | REJ | REJ | RES | ACTIVE | **CORE** | WATCH |
| 9 - BulutKeser | REJ | REJ | REJ | REJ | REJ | SEC | ACTIVE | **CORE** | WATCH |
| 10 - HO/Volatilite | REJ | REJ | REJ | REJ | REJ | REJ | REJ | REJ | REJ |
| 11 - Stoc.RSI & RSI & BB & MACD | REJ | REJ | REJ | REJ | REJ | SEC | **CORE** | **CORE** | WATCH |
| 13 - MACD YenidenHareket | REJ | REJ | REJ | REJ | REJ | SEC | **CORE** | **CORE** | WATCH |
| 14 - MACD DipDönüşü | REJ | REJ | REJ | REJ | REJ | SEC | SEC | **CORE** | WATCH |

## 4. CORE sıralaması

| # | Tarama | TF | Score | İşlem | PF | E(R) | Worst Fold |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | 11 - Stoc.RSI & RSI & BB & MACD | 1W | **96.3** | 1,202 | 3.164 | +0.790 | +0.519 |
| 2 | 14 - MACD DipDönüşü | 1W | **95.2** | 2,890 | 3.590 | +0.687 | +0.404 |
| 3 | RSI & MACD - RVOL | 1W | **95.0** | 1,069 | 3.376 | +0.810 | +0.373 |
| 4 | 9 - BulutKeser | 1W | **94.1** | 401 | 4.102 | +0.993 | +0.386 |
| 5 | 13 - MACD YenidenHareket | 1D | **93.4** | 13,705 | 4.296 | +0.536 | +0.448 |
| 6 | NE ARARSAN VAR | 1W | **91.7** | 1,964 | 3.163 | +0.743 | +0.315 |
| 7 | 8 - TavanTarama | 1W | **89.3** | 1,104 | 3.301 | +0.839 | +0.257 |
| 8 | 13 - MACD YenidenHareket | 1W | **88.5** | 1,949 | 3.021 | +0.707 | +0.270 |
| 9 | 7 - BB Daralması | 1W | **87.7** | 1,597 | 2.680 | +0.657 | +0.334 |
| 10 | StochRSI / Momentum / Hacim | 1W | **86.6** | 4,324 | 2.689 | +0.644 | +0.284 |
| 11 | BB & SMA | 1W | **81.7** | 1,572 | 2.726 | +0.677 | +0.196 |
| 12 | 11 - Stoc.RSI & RSI & BB & MACD | 1D | **78.9** | 4,480 | 2.690 | +0.346 | +0.278 |

Buradaki ilk büyük bulgu açıktır: **mevcut araştırma setinin en güçlü ve en geniş production katmanı 1W'dir.** CORE modellerin büyük çoğunluğu haftalıkta oluşmuştur.

## 5. ACTIVE production çiftleri

Bunlar kabul barajını geçiyor ancak CORE skor eşiğinin altında kalıyor.

| Tarama | TF | Score | İşlem | PF | E(R) | Worst Fold |
|---|---|---:|---:|---:|---:|---:|
| 9 - BulutKeser | 1D | 69.6 | 320 | 1.927 | +0.408 | +0.260 |
| StochRSI / Momentum / Hacim | 1D | 63.5 | 10,108 | 1.576 | +0.276 | +0.145 |
| 7 - BB Daralması | 1D | 63.0 | 2,716 | 1.715 | +0.335 | +0.127 |
| 8 - TavanTarama | 1D | 59.0 | 1,030 | 1.766 | +0.215 | +0.131 |
| NE ARARSAN VAR | 1D | 58.8 | 5,320 | 1.512 | +0.242 | +0.099 |
| BB & SMA | 1D | 58.1 | 3,098 | 1.636 | +0.206 | +0.102 |
| BB & SMA | 4H | 55.7 | 4,995 | 1.416 | +0.138 | +0.106 |
| RSI & MACD - RVOL | 1D | 54.2 | 8,668 | 1.366 | +0.183 | +0.043 |
| BB & SMA | 2H | 53.0 | 7,483 | 1.302 | +0.106 | +0.072 |

Özellikle **BB & SMA 2H**, mevcut araştırma setinde 2H production barajını geçen tek modeldir.

## 6. SECONDARY çiftler

Bu modellerin nihai sonuçları 4/4 pozitif olsa da giriş kalitesi / edge önemli ölçüde özel risk yönetimine bağlıdır. Bu yüzden yüksek PF/score görsek bile normal ACTIVE gibi sunmayacağız.

| Tarama | TF | Score | Final PF | Final E(R) | Worst Fold | Secondary nedeni |
|---|---|---:|---:|---:|---:|---|
| 13 - MACD YenidenHareket | 4H | 87.7 | 3.453 | +0.446 | +0.390 | Ham giriş 3/4; MACD tighten final 4/4'ü oluşturuyor |
| 14 - MACD DipDönüşü | 1D | 71.4 | 2.387 | +0.421 | +0.170 | Ham giriş 3/4; fail-tighten gerekli |
| 11 - Stoc.RSI & RSI & BB & MACD | 4H | 69.5 | 2.693 | +0.346 | +0.134 | Ham giriş 3/4; BB Basis-loss tighten gerekli |
| 14 - MACD DipDönüşü | 4H | 66.2 | 2.163 | +0.360 | +0.156 | Ham giriş 3/4; fail-tighten gerekli |
| 9 - BulutKeser | 4H | 56.7 | 1.889 | +0.240 | +0.145 | Giriş tek başına robust değil; Kijun-loss tighten gerekli |
| RSI & MACD - RVOL | 4H | 53.8 | 1.572 | +0.145 | +0.103 | Locked araştırma ACTIVE_SECONDARY |
| 7 - BB Daralması | 4H | 48.0 | 1.530 | +0.183 | +0.003 | Worst-fold marjı çok ince |

Önemli örnek: **MACD YenidenHareket 4H numeric score olarak çok yüksek olsa da CORE yapılmıyor.** Çünkü score, girişin özel yönetim olmadan yalnız 3/4 olduğunu ortadan kaldırmaz. Promotion gate burada skoru bilinçli olarak override eder.

## 7. RESEARCH / REJECT kararları

Production'a taşınmayacak ama araştırma katmanında tutulabilecek başlıca modeller:

- TavanTarama 4H: 3/4; worst fold yaklaşık -0.006R.
- NE ARARSAN VAR 2H ve 4H: final araştırma raporu production dışı tutuyor; 4H en iyi sabit tetikleyici yalnız 2/4.
- StochRSI / Momentum / Hacim 4H: yalnız 2/4.
- Bütün 1M modeller: **FORWARD_WATCH**; normal production sinyali değildir.
- HO/Volatilite: mevcut haliyle **family-level REJECT**. A/B EMA deneyi dahil anlamlı, kararlı production edge üretmedi; 1H orijinal strict MTF tasarımı ayrıca matematiksel olarak sinyal üretemiyor.

## 8. Family-level final eleme

Toplam 11 araştırma ailesinden:

- **10 aile** en az bir production timeframe'e sahip olduğu için gelecekte `taramabot`a taşınmaya değer.
- **1 aile — HO/Volatilite — mevcut tasarımıyla elendi.** Yeniden ele alınacaksa bu, aynı taramayı optimize etmek değil cross-timeframe volume/volatility mantığını yeniden tasarlayan yeni bir research işi olmalıdır.

Production'a taşınacak aileler:

```text
NE ARARSAN VAR
StochRSI / Momentum / Hacim
BB & SMA
RSI & MACD - RVOL
7 - BB Daralması
8 - TavanTarama
9 - BulutKeser
11 - Stoc.RSI & RSI & BB & MACD
13 - MACD YenidenHareket
14 - MACD DipDönüşü
```

## 9. Timeframe bazında final mimari

### 15m / 30m / 45m / 1H

Mevcut yeni tarama araştırma setinden **hiçbir production model yok.** Bu timeframe'lerde taramaları sırf boş kalmasın diye zorlamıyoruz.

### 2H

Yalnız **BB & SMA ACTIVE**.

### 4H

- BB & SMA = normal ACTIVE.
- MACD YenidenHareket, MACD DipDönüşü, Scan11, BulutKeser, RSI-MACD-RVOL, BB Daralması = SECONDARY.
- TavanTarama, NE ARARSAN VAR ve StochRSI/Momentum/Hacim = RESEARCH.

Bu nedenle 4H katmanı gelecekte Telegram'da **ana sinyal + erken uyarı** şeklinde iki seviyeli sunulmalıdır.

### 1D

Ana production katmanlarından biridir. MACD YenidenHareket ve Scan11 CORE; diğer sağlam modeller ACTIVE. MACD DipDönüşü ise özel SAT bağımlılığı nedeniyle SECONDARY.

### 1W

**En güçlü katman.** On production ailesinin tamamı haftalıkta CORE seviyesinde veya güçlü production sınıfında yer alıyor. Haftalık sinyaller gelecekte tarama güven puanında en yüksek timeframe ağırlığını hak ediyor.

### 1M

**Forward-watch only.** Yüksek PF/E rakamları küçük ve dengesiz örneklemler nedeniyle production kararı değildir.

## 10. `taramabot` entegrasyon politikası

Gelecekte production'a taşırken taramanın kendi `locked-spec` / final raporundaki giriş-SAT kuralları **değiştirilmeden** uygulanmalıdır.

Önerilen routing:

```text
CORE
→ ana tarama sonucu
→ en yüksek güven ağırlığı

ACTIVE
→ normal production sonucu

SECONDARY
→ erken uyarı / destekleyici sinyal
→ CORE ile aynı güven seviyesinde gösterilmez

FORWARD_WATCH
→ sinyal + sonuç kaydı tutulur
→ normal Telegram alert akışına girmez

RESEARCH
→ yalnız research/diagnostic katmanı

REJECT
→ production engine'e dahil edilmez
```

## 11. Aynı hissede birden fazla tarama geldiğinde kritik kural

**Quality Score'ları kör biçimde toplamamalıyız.** Tarayıcıların önemli kısmı MACD, RSI, Bollinger, StochRSI ve hacim gibi ortak girdiler kullanıyor. Dolayısıyla örneğin aynı MACD hareketinden türeyen üç taramanın aynı anda sinyal vermesi üç bağımsız kanıt değildir.

Gelecekte hisse güven puanı oluştururken şunlar ayrıca hesaplanmalıdır:

- tarama sinyallerinin tarihsel overlap oranı
- aynı bar / yakın bar beraber çalışma oranı
- getiri serisi korelasyonu
- aynı gösterge ailesine bağımlılık
- timeframe çeşitliliği
- trend / momentum / volatilite / dönüş gibi farklı sinyal ailelerinden bağımsız teyit sayısı

Böylece `3 tarama geldi = 3 kat güçlü` yerine **bağımsız bilgi miktarı** ölçülür.

## 12. Ortak execution / risk ilkeleri

Araştırma setinde standardize edilen temel yaklaşım korunmalıdır:

- sinyal tamamlanmış bar üzerinden
- giriş referansı sonraki bar açılışı
- look-ahead yok
- 10 bps komisyon + 10 bps slippage / taraf
- aynı OHLC barda stop ve hedef birlikte görünürse STOP önce
- ilk risk tipik olarak 0.60–2.60 ATR sınırında
- TP1/TP2/TP3 + runner yaşam döngüsü
- tarama bazlı SAT profili
- TP1 sonrası break-even yalnız veri destekliyorsa; tamamlanan yeni setin büyük bölümünde final karar **NO-BE**

## 13. Bundan sonraki aşama

Tarama araştırmasının bu turu burada kapanmıştır. Sonraki production çalışması iki parçadır:

1. Bu registry'deki `CORE / ACTIVE / SECONDARY` çiftlerini `taramabot` tarama motoruna locked kurallarla taşımak.
2. `taramabot`un mevcut hisse bazlı tarihsel profil sistemini **teknik parmak izi** seviyesine yükseltmek: her hisse için hangi tarama / timeframe / gösterge ailesinin gerçekten daha iyi çalıştığını ayrı skorlamak.

Bu belge değiştirilmiş geçmiş üzerinde tekrar tekrar optimum kovalamak için değil, **promotion kararını dondurmak** için vardır.
