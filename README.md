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

## Aktif çalışma

İlk araştırma paketi: [`experiments/ne_ararsan_var/`](experiments/ne_ararsan_var/)

> `taramabot` production ve doğrulanmış altyapı için temiz tutulacaktır. Bundan sonraki yeni tarama denemeleri bu repoda yapılacaktır.
