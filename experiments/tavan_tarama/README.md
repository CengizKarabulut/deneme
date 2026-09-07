# 8 - TavanTarama — LOCKED

Araştırma tamamlandı. Production'a aktarılacak kesin kurallar `locked-spec.json`, ayrıntılı karar ve test özeti `reports/final-decision.md` içindedir.

## Nihai karar

- 15m / 30m / 45m / 1H / 2H: REJECT
- 4H: RESEARCH_SECONDARY
- 1D: ACTIVE
- 1W: ACTIVE
- 1M: RESEARCH_FORWARD_WATCH

## DMI kararı

İki yöntem test edildi:

1. Orijinal: `+DI > -DI` ve `+DI` ADX'i aşağıdan yukarı keser.
2. Alternatif: `+DI` `-DI`'yi aşağıdan yukarı keser ve ADX yükselir.

1D ve 1W'de orijinal yöntem açık biçimde daha kararlı çıktı. 4H'de alternatif toplam PF/expectancy olarak daha yüksek olsa da daha küçük örneklem ve daha kötü negatif fold üretti; bu nedenle 4H research referansı da orijinal olarak tutuldu.

## ACTIVE girişler

### 1D

- +DI > -DI
- +DI fresh crosses above ADX
- RSI14: 50-70
- StochRSI K fresh crosses above D
- RVOL20 > 1.50

### 1W

- +DI > -DI
- +DI fresh crosses above ADX
- RSI14: 40-70
- StochRSI K > D
- RVOL20 > 1.50

RVOL20 mevcut bar / önceki 20 aynı-timeframe bar ortalamasıdır; mevcut bar referans ortalamaya dahil değildir.

## SAT

- 1D: 9-bar swing -0.25 ATR, 1.1/2.2/3.3R, TP2 sonrası 2.0 ATR trail; ADX iki bar üst üste düşerse trail 1.5 ATR'ye sıkılaşır; hard DMI/ADX SAT yok; max 40 bar; NO-BE.
- 1W: 11-bar swing -0.15 ATR, 1.1/2.2/3.3R, TP2 sonrası 2.1 ATR trail; hard DMI/ADX SAT yok; max 80 bar; NO-BE.

Nihai performans:

- 1D: 1,030 işlem, PF 1.766, +0.215R, 4/4 pozitif, en kötü fold +0.131R.
- 1W: 1,104 işlem, PF 3.301, +0.839R, 4/4 pozitif, en kötü fold +0.257R.

Gerçek bağımsız doğrulama bundan sonra oluşacak yeni barlardır.
