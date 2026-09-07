# 9 - BulutKeser — LOCKED

Durum: **Araştırma tamamlandı / üretime aktarılabilir spesifikasyon hazır.**

Nihai karar ve ayrıntılı metodoloji:

- `reports/final-decision.md`
- `locked-spec.json`

## Ana bulgu

Tenkan/Kijun bullish kesişiminin Kumo'ya göre konumu timeframe'e göre farklı anlam taşıyor:

- **1D ACTIVE:** Kumo **altında** erken toparlanma
- **1W ACTIVE:** Kumo **üstünde** trend devamı / teyit
- **4H ACTIVE_SECONDARY:** Kumo **içinde**, fakat edge'in önemli kısmı Kijun tabanlı risk yönetiminden geliyor
- 15m–2H: reject
- 1M: yetersiz örneklem

Kumo, Ichimoku'nun gerçek 26-bar displacement semantiğiyle ve look-ahead olmadan hesaplanır.

## Nihai üretim adayları

### 4H — ACTIVE_SECONDARY

Tenkan ↑ Kijun + Close Kumo içinde + ADX>20 + fiyat BB içinde + RVOL20>1.20. Kijun kaybında trailing sıkılaşır.

### 1D — ACTIVE

Tenkan ↑ Kijun + Close Kumo altında + ADX20–35 + BB Basis<Close<Upper + RVOL20>1.50.

### 1W — ACTIVE

Tenkan ↑ Kijun + Close Kumo üstünde + ADX20–35 + RVOL20>1.50. Bollinger filtresi yok.

TP1 sonrası break-even üçünde de kullanılmaz.

> Geçmiş veri artık gözlenmiştir. Gerçek bağımsız doğrulama gelecekte oluşacak yeni barlardır.
