# Deneme — Tarama Araştırma Laboratuvarı

Bu repo yeni BIST taramalarını, AL/SAT kurallarını, zaman dilimi optimizasyonlarını ve walk-forward/backtest çalışmalarını **production repolarından ayrı** tutmak için kullanılır.

## Temel kural

- Yeni fikir önce burada araştırılır.
- Sonuca bakarak kural uydurmak yerine aday kurallar önceden tanımlanır.
- Giriş bir sonraki mum açılışından modellenir.
- Komisyon ve slippage dahil edilir.
- Aynı OHLC mumunda stop ve hedef birlikte görülürse muhafazakâr olarak stop önceliklidir.
- Mümkün olduğunda walk-forward / OOS kullanılır.
- Her zaman dilimi ayrı değerlendirilebilir; tek AL veya SAT reçetesi bütün timeframe'lere zorlanmaz.
- Yalnız yeterince kararlı ve doğrulanmış taramalar daha sonra production reposuna taşınır.

## Klasör yapısı

`experiments/<tarama_adi>/`

Her taramada mümkün olduğunca şu kayıtlar tutulur:

- taramanın güncel giriş şartları,
- denenmiş alternatifler,
- SAT / risk yönetimi adayları,
- test metodolojisi ve maliyet varsayımları,
- timeframe bazında sonuçlar,
- kabul / ret / araştırma kararı,
- sonraki deney planı.

## Ortak kalite / promotion registry

İlk tarama araştırma turunun ortak final elemesi tamamlandı.

- İnsan-okunur final matris: [`reports/scanner-quality-matrix-v1.md`](reports/scanner-quality-matrix-v1.md)
- Makine-okunur registry: [`reports/scanner-quality-registry-v1.json`](reports/scanner-quality-registry-v1.json)

Ortak routing politikası:

- `CORE` → ana production taraması / en yüksek güven ağırlığı
- `ACTIVE` → normal production taraması
- `SECONDARY` → erken uyarı / destekleyici sinyal
- `FORWARD_WATCH` → ileri veriyle performans kaydı; normal production alarmı değil
- `RESEARCH` → laboratuvarda kalır
- `REJECT` → production'a taşınmaz

Aylık (`1M`) modeller ortak registry'de tarihsel rakamları yüksek olsa bile `FORWARD_WATCH` olarak tutulur. Birden fazla taramanın aynı hissede sinyal vermesi halinde quality score'lar doğrudan toplanmaz; ortak indikatör ve sinyal overlap/korelasyonu gelecekteki birleşik güven puanında ayrıca cezalandırılacaktır.

> `taramabot` production ve doğrulanmış altyapı için temiz tutulacaktır. Yeni tarama denemeleri burada yapılır; yalnız ortak promotion registry'de kabul edilen locked kurallar production entegrasyonuna adaydır.
